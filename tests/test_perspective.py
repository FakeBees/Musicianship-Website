"""Permission perspectives ("view as").

The security-critical property is that a perspective can only ever REDUCE
privileges. Most of these tests exist to prove escalation is impossible, by
whichever route someone might try it.
"""
import pytest

from app import app, ROLE_ORDER, role_rank
from models import db, User, Section, Course, School


@pytest.fixture(autouse=True)
def ctx():
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def make_user(role, email=None):
    u = User(email=email or f'{role}@test.com', password_hash='x', role=role)
    db.session.add(u)
    db.session.commit()
    return u


def client_for(user):
    app.config['TESTING'] = True
    c = app.test_client()
    with c.session_transaction() as s:
        s['_user_id'] = str(user.id)
        s['_fresh'] = True
    return c


# ── The hierarchy itself ─────────────────────────────────────────────────────

def test_role_order_is_ascending():
    assert ROLE_ORDER == ['student', 'class_teacher', 'admin_teacher', 'admin']
    assert role_rank('student') < role_rank('class_teacher') < \
           role_rank('admin_teacher') < role_rank('admin')


def test_unknown_role_ranks_below_everything():
    assert role_rank('nonsense') == -1


# ── Escalation is impossible ─────────────────────────────────────────────────

def test_student_cannot_select_a_higher_perspective():
    u = make_user('student')
    c = client_for(u)
    for higher in ('class_teacher', 'admin_teacher', 'admin'):
        assert c.get(f'/perspective/{higher}').status_code == 403


def test_class_teacher_cannot_reach_admin_perspective():
    u = make_user('class_teacher')
    c = client_for(u)
    assert c.get('/perspective/admin').status_code == 403
    assert c.get('/perspective/admin_teacher').status_code == 403
    assert c.get('/perspective/student').status_code == 302   # downward is fine


def test_forged_session_value_above_real_role_is_ignored_not_honoured():
    """The decisive test: writing a higher role straight into the session must
    not grant it. active_role() caps at the real role."""
    u = make_user('student')
    c = client_for(u)
    with c.session_transaction() as s:
        s['perspective'] = 'admin'
    assert c.get('/admin').status_code == 403
    # And the nav must not offer admin links either.
    assert b'/admin/users' not in c.get('/').data


def test_garbage_session_value_falls_back_to_real_role():
    u = make_user('admin')
    c = client_for(u)
    with c.session_transaction() as s:
        s['perspective'] = 'wizard'
    assert c.get('/admin').status_code == 200


def test_unknown_role_in_url_is_404():
    u = make_user('admin')
    assert client_for(u).get('/perspective/wizard').status_code == 404


# ── Downgrade actually restricts ─────────────────────────────────────────────

def test_admin_in_student_perspective_is_locked_out_of_admin():
    u = make_user('admin')
    c = client_for(u)
    assert c.get('/admin').status_code == 200          # before
    c.get('/perspective/student')
    assert c.get('/admin').status_code == 403          # after
    assert c.get('/teacher').status_code == 403


def test_admin_in_teacher_perspective_keeps_teacher_but_loses_admin():
    u = make_user('admin')
    c = client_for(u)
    c.get('/perspective/class_teacher')
    assert c.get('/teacher').status_code == 200
    assert c.get('/admin').status_code == 403


def test_returning_to_own_role_restores_access():
    u = make_user('admin')
    c = client_for(u)
    c.get('/perspective/student')
    assert c.get('/admin').status_code == 403
    c.get('/perspective/admin')
    assert c.get('/admin').status_code == 200


def test_switcher_stays_reachable_from_the_lowest_perspective():
    """You must never be able to strand yourself."""
    u = make_user('admin')
    c = client_for(u)
    c.get('/perspective/student')
    assert c.get('/perspective/admin').status_code == 302


# ── Per-section resolution ───────────────────────────────────────────────────

def _section(name, teacher_id=None, assigned_id=None, members=()):
    s = Section(name=name, join_code=name.upper()[:8],
                teacher_id=teacher_id or 999, assigned_teacher_id=assigned_id)
    for m in members:
        s.members.append(m)
    db.session.add(s)
    db.session.commit()
    return s


def _as(user, perspective=None):
    """Request context with `user` logged in and an optional perspective set."""
    from contextlib import contextmanager
    from flask import session as flask_session
    from flask_login import login_user

    @contextmanager
    def _ctx():
        with app.test_request_context('/'):
            login_user(user)
            if perspective:
                flask_session['perspective'] = perspective
            yield
    return _ctx()


def test_section_role_reflects_the_real_relationship():
    from app import section_role
    owner = make_user('admin_teacher', 'owner@t.com')
    assigned = make_user('class_teacher', 'assigned@t.com')
    student = make_user('student', 's@t.com')
    outsider = make_user('student', 'outsider@t.com')
    sec = _section('S1', teacher_id=owner.id, assigned_id=assigned.id, members=[student])

    assert section_role(sec, owner) == 'admin_teacher'
    assert section_role(sec, assigned) == 'class_teacher'
    assert section_role(sec, student) == 'student'
    assert section_role(sec, outsider) is None


@pytest.mark.parametrize('perspective,expected', [
    (None,            'admin_teacher'),   # no perspective — full relationship
    ('admin',         'admin_teacher'),   # perspective above what you hold: no change
    ('admin_teacher', 'admin_teacher'),   # exactly your level
    ('class_teacher', 'class_teacher'),   # capped down
    ('student',       'student'),         # capped all the way down
])
def test_effective_section_role_caps_at_the_perspective(perspective, expected):
    """The rule: the highest role you hold here that doesn't exceed the
    perspective you selected."""
    from app import effective_section_role
    owner = make_user('admin', 'owner2@t.com')       # real role high enough to pick any
    sec = _section('S2', teacher_id=owner.id)        # relationship here: admin_teacher
    with _as(owner, perspective):
        assert effective_section_role(sec) == expected


def test_effective_section_role_never_raises_a_plain_member():
    """A student member stays a student even under an admin perspective."""
    from app import effective_section_role
    admin = make_user('admin', 'a2@t.com')
    sec = _section('S3', teacher_id=999, members=[admin])
    # Real relationship is 'student'; perspective is 'admin'. min() wins.
    with _as(admin, 'admin'):
        assert effective_section_role(sec) == 'student'


def test_owner_viewing_as_student_gets_the_student_view_of_their_own_section():
    """The headline use case: roles are inclusive, so capping an owner down to
    student lets them walk their own section as a student would."""
    owner = make_user('admin_teacher', 'owner3@t.com')
    sec = _section('S4', teacher_id=owner.id)
    c = client_for(owner)

    c.get('/perspective/student')
    assert c.get(f'/section/{sec.id}').status_code == 200        # student view: in
    assert c.get(f'/teacher/section/{sec.id}').status_code == 403  # teacher view: out
    assert c.get('/teacher').status_code == 403


def test_owner_capped_to_class_teacher_keeps_teacher_screens():
    """An owner implicitly holds class_teacher over their own section, so
    capping to class_teacher must not lock them out of it."""
    owner = make_user('admin_teacher', 'owner4@t.com')
    sec = _section('S5', teacher_id=owner.id)   # owner, NOT assigned_teacher
    c = client_for(owner)
    c.get('/perspective/class_teacher')
    assert c.get(f'/teacher/section/{sec.id}').status_code == 200


def test_perspective_does_not_grant_access_to_unrelated_sections():
    """Capping down must never widen reach."""
    teacher = make_user('admin_teacher', 'owner5@t.com')
    other = _section('SomeoneElses', teacher_id=999)
    c = client_for(teacher)
    assert c.get(f'/section/{other.id}').status_code == 403
    c.get('/perspective/student')
    assert c.get(f'/section/{other.id}').status_code == 403


def test_site_admin_keeps_blanket_section_access_at_full_role():
    admin = make_user('admin', 'a9@t.com')
    other = _section('NotAdmins', teacher_id=999)
    c = client_for(admin)
    assert c.get(f'/teacher/section/{other.id}').status_code == 200
    # …but loses it the moment they drop below admin, having no relationship.
    c.get('/perspective/admin_teacher')
    assert c.get(f'/teacher/section/{other.id}').status_code == 403


# ── Scoping: only sections you actually belong to ────────────────────────────

def test_related_sections_excludes_sections_you_have_no_tie_to():
    from app import related_sections
    admin = make_user('admin', 'a3@t.com')
    _section('Mine', teacher_id=admin.id)
    _section('NotMine', teacher_id=999)
    with _as(admin):
        names = [s.name for s in related_sections()]
    assert names == ['Mine']


def test_student_perspective_home_lists_only_related_sections():
    admin = make_user('admin', 'a4@t.com')
    _section('Unrelated', teacher_id=999)
    c = client_for(admin)
    c.get('/perspective/student')
    body = c.get('/').get_data(as_text=True)
    assert 'Unrelated' not in body


# ── UI plumbing ──────────────────────────────────────────────────────────────

def test_banner_appears_only_while_in_a_perspective():
    u = make_user('admin', 'a5@t.com')
    c = client_for(u)
    assert b'Viewing as' not in c.get('/').data
    c.get('/perspective/student')
    assert b'Viewing as' in c.get('/').data


def test_student_account_gets_no_switcher():
    """Only one option means nothing to switch between."""
    u = make_user('student', 's2@t.com')
    c = client_for(u)
    assert b'View as' not in c.get('/').data


def test_admin_account_sees_all_four_options():
    u = make_user('admin', 'a6@t.com')
    body = client_for(u).get('/').get_data(as_text=True)
    assert 'View as' in body
    for label in ('Site Admin', 'School Admin', 'Section Teacher', 'Student'):
        assert label in body


def test_wording_follows_the_perspective():
    """A teacher previewing as a student should read 'classroom'."""
    u = make_user('admin', 'a7@t.com')
    c = client_for(u)
    assert b'Classroom' not in c.get('/').data
    c.get('/perspective/student')
    assert b'Classroom' in c.get('/').data


def test_debug_state_reports_the_perspective():
    u = make_user('admin', 'a8@t.com')
    c = client_for(u)
    assert c.get('/debug/state?endpoint=home').get_json()['perspective'] is None
    c.get('/perspective/student')
    data = c.get('/debug/state?endpoint=home').get_json()
    assert data['perspective'] == 'student'
    assert data['real_role'] == 'admin'
    assert 'Viewing as' in data['verdict']
