"""Task 6 (D19-D21): cascading deletes behind three confirmation pages.

Deleting a school or a user used to crash with a 500 — a NOT NULL foreign key
(SchoolMembership.user_id / .school_id, ModuleCompletion.user_id, etc.) blocked
the plain `db.session.delete(...)`, because nothing removed the dependent rows
first. Deleting a course silently deleted its students' progress while leaving
its sections stranded (course_id pointing at a row that no longer existed).

This file:
  * seeds one rich `world()` that carries every kind of dependent row the
    brief calls out — attempts in all four modes, completions reaching both
    ModuleCompletion FKs, overrides of every action, a section-owned module,
    a section's own addition onto a shared course module, an assigned
    Section Teacher — so the cascades and the orphan scan both get exercised
    for real;
  * `find_orphans()` is the generic checker: it walks every FK in the actual
    schema (not just the ones this task touches) and reports any non-NULL
    value that no longer exists in its target table;
  * proves the three-step confirm flow: step 1/2/3 all render with a
    distinct heading, a POST only deletes on step=3, step 2's itemised list
    names what step 3 then removes, and the permission check still runs
    before any step is even looked at (mirrors test_school_authority.py's
    protected 403 case, but for school/user delete, and with step=3 supplied
    explicitly).

Mirrors test_hidden_content.py's pattern: an autouse per-test schema fixture,
tiny id-based factories, and a client_as(uid) helper backed by _Client — one
fresh app context per request, since several tests act as more than one user.
"""
from urllib.parse import urlsplit

import pytest

from app import app
from models import (db, User, School, SchoolMembership, Course, Module,
                     ModuleExercise, Section, SectionModuleExercise,
                     ModuleCompletion, Melody, Rhythm, ChordProgression,
                     HolisticExercise, UserAttempt, RhythmAttempt,
                     HarmonicAttempt, HolisticAttempt)


@pytest.fixture(autouse=True)
def ctx():
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


# ── tiny id-based factories (test_school_authority.py's pattern) ───────────

def user(role, email):
    u = User(email=email, password_hash='x', role=role)
    db.session.add(u)
    db.session.commit()
    return u


def school(name):
    s = School(name=name, join_code=name[:6].upper())
    db.session.add(s)
    db.session.commit()
    return s


def member(school, user, role):
    m = SchoolMembership(school_id=school.id, user_id=user.id, role=role)
    db.session.add(m)
    db.session.commit()
    return m


def course(school, name='Theory'):
    c = Course(name=name, school_id=school.id)
    db.session.add(c)
    db.session.commit()
    return c


def module_row(course_id, name, order, section_id=None):
    m = Module(name=name, course_id=course_id, order=order, section_id=section_id)
    db.session.add(m)
    db.session.commit()
    return m


def module_exercise_row(module_id, name, exercise_id, section_id=None, order=0):
    me = ModuleExercise(module_id=module_id, exercise_type='melody', exercise_id=exercise_id,
                        name=name, order=order, section_id=section_id)
    db.session.add(me)
    db.session.commit()
    return me


def override(section_id, action, module_id=None, module_exercise_id=None):
    sme = SectionModuleExercise(section_id=section_id, action=action,
                                module_id=module_id, module_exercise_id=module_exercise_id)
    db.session.add(sme)
    db.session.commit()
    return sme


def completion(user_id, section_id, module_exercise_id=None, section_exercise_id=None):
    mc = ModuleCompletion(user_id=user_id, section_id=section_id,
                          module_exercise_id=module_exercise_id,
                          section_exercise_id=section_exercise_id,
                          attempt_count=1, passing_count=1, is_complete=True, best_score=90.0)
    db.session.add(mc)
    db.session.commit()
    return mc


def melody_row(name, school_id=None):
    m = Melody(name=name, midi_filename=f'{name}.mid', notes_json='[]', clef='treble',
              min_duration='q', time_signature='4/4', difficulty=1, school_id=school_id)
    db.session.add(m)
    db.session.commit()
    return m


def rhythm_row(name):
    r = Rhythm(name=name, notes_json='[]')
    db.session.add(r)
    db.session.commit()
    return r


def progression_row(name):
    p = ChordProgression(name=name, midi_filename=f'{name}.mid', chords_json='[]')
    db.session.add(p)
    db.session.commit()
    return p


def holistic_row(name):
    h = HolisticExercise(name=name, folder=f'holistic/{name}/')
    db.session.add(h)
    db.session.commit()
    return h


class _Client:
    """A test client whose every request runs in its own, fresh app context —
    see test_hidden_content.py's identical class for why this matters: with a
    single shared app context, Flask-Login caches the first request's user on
    `g` and every later request silently runs as them too."""

    def __init__(self, uid):
        self._client = app.test_client()
        with app.app_context(), self._client.session_transaction() as s:
            s['_user_id'] = str(uid)
            s['_fresh'] = True

    def get(self, *args, **kwargs):
        with app.app_context():
            return self._client.get(*args, **kwargs)

    def post(self, *args, **kwargs):
        with app.app_context():
            return self._client.post(*args, **kwargs)


def client_as(uid):
    app.config['TESTING'] = True
    return _Client(uid)


def find_orphans():
    """Walk every FK declared anywhere in the schema (not just the ones this
    task touches) and report any non-NULL value that no longer exists in its
    target table. Empty list == clean."""
    problems = []
    for table in db.metadata.sorted_tables:
        for fk in table.foreign_keys:
            col, target_col = fk.parent, fk.column
            values = {row[0] for row in db.session.query(col).filter(col.isnot(None)).all()}
            if not values:
                continue
            existing = {row[0] for row in
                        db.session.query(target_col).filter(target_col.in_(values)).all()}
            missing = values - existing
            if missing:
                problems.append(f'{table.name}.{col.name} -> '
                                f'{target_col.table.name}.{target_col.name}: {sorted(missing)}')
    return problems


def world():
    """A school with a course, a course-owned module+exercise, and a section
    following that course that has: its own module+exercise, an addition it
    made onto the shared course module, overrides of every action, a
    completion reaching each ModuleCompletion FK (including both at once),
    and — for the student and the section owner — one attempt in each of the
    four practice modes. One content-bank row is scoped to the school itself
    (Melody.school_id), to exercise that FK too. A site admin (not a member
    of the school) is included to act as the deleter."""
    admin = user('admin', 'root@site.com')

    s = school('Westfield')
    owner    = user('admin_teacher', 'owner@west.com')     # Sec1.teacher_id
    assigned = user('class_teacher', 'assigned@west.com')  # Sec1.assigned_teacher_id
    stu      = user('student', 'stu@west.com')
    member(s, owner, 'admin_teacher')
    member(s, assigned, 'class_teacher')
    member(s, stu, 'student')

    crs = course(s, 'Theory')

    mel  = melody_row('Mel1', school_id=s.id)
    rhy  = rhythm_row('Rhy1')
    prog = progression_row('Prog1')
    hol  = holistic_row('Hol1')

    m_course = module_row(crs.id, 'Course Module', 0)
    ce = module_exercise_row(m_course.id, 'Course Exercise', mel.id)

    sec = Section(name='Sec1', join_code='WEST01', teacher_id=owner.id,
                 assigned_teacher_id=assigned.id, course_id=crs.id)
    sec.members.append(stu)
    db.session.add(sec)
    db.session.commit()

    m_sec    = module_row(crs.id, 'Section Module', 1, section_id=sec.id)
    se_own   = module_exercise_row(m_sec.id, 'Section Own Exercise', mel.id, section_id=sec.id)
    se_added = module_exercise_row(m_course.id, 'Section Addition', mel.id, section_id=sec.id)

    ov_hide_module = override(sec.id, 'hide', module_id=m_course.id)
    ov_hide_ex     = override(sec.id, 'hide', module_exercise_id=ce.id)
    ov_remove      = override(sec.id, 'remove', module_exercise_id=se_added.id)
    ov_override    = override(sec.id, 'override', module_exercise_id=ce.id)
    ov_add         = override(sec.id, 'add', module_id=m_course.id)

    completion(stu.id, sec.id, module_exercise_id=ce.id)
    completion(stu.id, sec.id, section_exercise_id=ov_override.id)
    completion(owner.id, sec.id, module_exercise_id=se_own.id, section_exercise_id=ov_add.id)

    for u in (stu, owner):
        db.session.add(UserAttempt(melody_id=mel.id, user_id=u.id, user_notes_json='[]'))
        db.session.add(RhythmAttempt(rhythm_id=rhy.id, user_id=u.id, user_notes_json='[]'))
        db.session.add(HarmonicAttempt(progression_id=prog.id, user_id=u.id, user_chords_json='[]'))
        db.session.add(HolisticAttempt(exercise_id=hol.id, user_id=u.id))
    db.session.commit()

    return {'admin': admin.id, 'school': s.id, 'owner': owner.id, 'assigned': assigned.id,
            'stu': stu.id, 'course': crs.id, 'section': sec.id, 'm_course': m_course.id,
            'ce': ce.id, 'melody': mel.id}


def _redirect_path(resp):
    return urlsplit(resp.headers['Location']).path


# ── School delete (D19) ─────────────────────────────────────────────────

def test_school_delete_step3_with_members_succeeds_and_keeps_accounts():
    w = world()
    resp = client_as(w['admin']).post(f'/admin/schools/{w["school"]}/delete',
                                      data={'step': '3'})
    assert resp.status_code == 302
    assert School.query.get(w['school']) is None
    assert Course.query.get(w['course']) is None
    assert Section.query.get(w['section']) is None
    assert ModuleCompletion.query.filter_by(section_id=w['section']).count() == 0

    # Accounts survive; only the membership is gone.
    for uid in (w['owner'], w['assigned'], w['stu']):
        assert User.query.get(uid) is not None
    assert SchoolMembership.query.filter_by(school_id=w['school']).count() == 0

    # Roles recalculated: none of these three belong to any other school.
    assert User.query.get(w['owner']).role == 'student'
    assert User.query.get(w['assigned']).role == 'student'
    assert User.query.get(w['stu']).role == 'student'

    # Content-bank row scoped to the school is freed, not destroyed.
    mel = Melody.query.get(w['melody'])
    assert mel is not None
    assert mel.school_id is None


def test_school_delete_never_demotes_a_site_admin_member():
    s = school('Acme')
    admin_member = user('admin', 'admin-member@acme.com')
    member(s, admin_member, 'admin_teacher')
    site_admin = user('admin', 'root@site.com')

    resp = client_as(site_admin.id).post(f'/admin/schools/{s.id}/delete', data={'step': '3'})
    assert resp.status_code == 302
    assert User.query.get(admin_member.id).role == 'admin'


def test_school_delete_403s_for_non_admin_even_with_step_3():
    w = world()
    resp = client_as(w['owner']).post(f'/admin/schools/{w["school"]}/delete',
                                      data={'step': '3'})
    assert resp.status_code == 403
    assert School.query.get(w['school']) is not None


# ── User delete (D20) ───────────────────────────────────────────────────

def test_user_delete_of_a_student_removes_their_progress_but_not_the_section():
    w = world()
    resp = client_as(w['admin']).post(f'/admin/users/{w["stu"]}/delete', data={'step': '3'})
    assert resp.status_code == 302
    assert User.query.get(w['stu']) is None
    assert ModuleCompletion.query.filter_by(user_id=w['stu']).count() == 0
    assert UserAttempt.query.filter_by(user_id=w['stu']).count() == 0
    assert RhythmAttempt.query.filter_by(user_id=w['stu']).count() == 0
    assert HarmonicAttempt.query.filter_by(user_id=w['stu']).count() == 0
    assert HolisticAttempt.query.filter_by(user_id=w['stu']).count() == 0
    # The section itself, and its other people, are untouched.
    assert Section.query.get(w['section']) is not None


def test_user_delete_of_a_section_owner_cascades_their_section():
    w = world()
    resp = client_as(w['admin']).post(f'/admin/users/{w["owner"]}/delete', data={'step': '3'})
    assert resp.status_code == 302
    assert User.query.get(w['owner']) is None
    # Owning teacher_id is NOT NULL — the section they owned goes with them.
    assert Section.query.get(w['section']) is None
    # The course-owned module survives (it belongs to the course, not the section).
    assert Module.query.get(w['m_course']) is not None
    # But everyone else's account survives.
    assert User.query.get(w['assigned']) is not None
    assert User.query.get(w['stu']) is not None


def test_user_delete_of_an_assigned_teacher_unassigns_but_keeps_the_section():
    w = world()
    resp = client_as(w['admin']).post(f'/admin/users/{w["assigned"]}/delete', data={'step': '3'})
    assert resp.status_code == 302
    assert User.query.get(w['assigned']) is None
    sec = Section.query.get(w['section'])
    assert sec is not None
    assert sec.assigned_teacher_id is None


def test_cannot_delete_own_account_at_any_step():
    w = world()
    c = client_as(w['admin'])
    for step in (1, 2, 3):
        resp = c.get(f'/admin/users/{w["admin"]}/delete?step={step}')
        assert resp.status_code == 302
        assert _redirect_path(resp) == '/admin/users'
    resp = c.post(f'/admin/users/{w["admin"]}/delete', data={'step': '3'})
    assert resp.status_code == 302
    assert User.query.get(w['admin']) is not None


def test_user_delete_403s_for_non_admin_even_with_step_3():
    w = world()
    resp = client_as(w['owner']).post(f'/admin/users/{w["stu"]}/delete', data={'step': '3'})
    assert resp.status_code == 403
    assert User.query.get(w['stu']) is not None


# ── Course delete (D21) ─────────────────────────────────────────────────

def test_course_delete_step3_removes_its_sections_and_their_progress():
    w = world()
    resp = client_as(w['admin']).post(f'/admin/courses/{w["course"]}/delete',
                                      data={'step': '3'})
    assert resp.status_code == 302
    assert Course.query.get(w['course']) is None
    assert Section.query.get(w['section']) is None
    assert ModuleCompletion.query.filter_by(section_id=w['section']).count() == 0
    # The school and its members are untouched.
    assert School.query.get(w['school']) is not None
    assert User.query.get(w['owner']) is not None


def test_course_step2_overview_lists_the_section_step3_then_deletes():
    w = world()
    c = client_as(w['admin'])
    body = c.get(f'/admin/courses/{w["course"]}/delete?step=2').data.decode()
    assert 'Sec1' in body
    resp = c.post(f'/admin/courses/{w["course"]}/delete', data={'step': '3'})
    assert resp.status_code == 302
    assert Section.query.get(w['section']) is None


def test_course_delete_403s_for_another_schools_admin_even_with_step_3():
    """Mirrors test_school_authority.py:89's protected case — a School Admin
    of another school must still 403, and specifically with step=3 supplied,
    proving the permission check runs before step handling, not after."""
    mine, theirs = school('Mine'), school('Theirs')
    at = user('admin_teacher', 'at@mine.com')
    member(mine, at, 'admin_teacher')
    other_course = course(theirs, 'Not Yours')

    resp = client_as(at.id).post(f'/admin/courses/{other_course.id}/delete',
                                 data={'step': '3'})
    assert resp.status_code == 403
    assert Course.query.get(other_course.id) is not None


# ── The three-step flow itself, generically ─────────────────────────────

ENDPOINTS = [
    ('school',  lambda w: f'/admin/schools/{w["school"]}/delete', 'admin'),
    ('user',    lambda w: f'/admin/users/{w["stu"]}/delete',      'admin'),
    ('course',  lambda w: f'/admin/courses/{w["course"]}/delete', 'admin'),
]


@pytest.mark.parametrize('label,url_for_w,actor', ENDPOINTS, ids=[e[0] for e in ENDPOINTS])
def test_every_step_renders_200_with_its_own_heading(label, url_for_w, actor):
    w = world()
    c = client_as(w[actor])
    for step in (1, 2, 3):
        url = url_for_w(w)
        resp = c.get(f'{url}?step={step}')
        assert resp.status_code == 200, f'{label} step {step}: HTTP {resp.status_code}'
        body = resp.data.decode()
        assert f'Step {step} of 3' in body, \
            f'{label} step {step}: page does not say which step it is'


@pytest.mark.parametrize('label,url_for_w,actor', ENDPOINTS, ids=[e[0] for e in ENDPOINTS])
def test_delete_link_with_no_query_string_defaults_to_step_1(label, url_for_w, actor):
    w = world()
    resp = client_as(w[actor]).get(url_for_w(w))
    assert resp.status_code == 200
    assert b'Step 1 of 3' in resp.data


@pytest.mark.parametrize('label,url_for_w,actor', ENDPOINTS, ids=[e[0] for e in ENDPOINTS])
def test_post_without_step_3_deletes_nothing(label, url_for_w, actor):
    w = world()
    url = url_for_w(w)
    resp = client_as(w[actor]).post(url)  # no 'step' field at all
    assert resp.status_code == 302
    assert _redirect_path(resp) == urlsplit(url).path

    assert School.query.get(w['school']) is not None
    assert User.query.get(w['stu']) is not None
    assert Course.query.get(w['course']) is not None


# ── Orphan check: no cascade may leave a dangling FK anywhere ───────────

def test_no_orphans_after_school_delete():
    w = world()
    resp = client_as(w['admin']).post(f'/admin/schools/{w["school"]}/delete',
                                      data={'step': '3'})
    assert resp.status_code == 302
    assert find_orphans() == []


def test_no_orphans_after_course_delete():
    w = world()
    resp = client_as(w['admin']).post(f'/admin/courses/{w["course"]}/delete',
                                      data={'step': '3'})
    assert resp.status_code == 302
    assert find_orphans() == []


def test_no_orphans_after_user_delete_of_the_section_owner():
    """The deepest of the three: deleting the owner cascades their whole
    section (its own module, its addition onto the shared module, every
    override and completion, both ModuleCompletion FKs, both attempt rows)."""
    w = world()
    resp = client_as(w['admin']).post(f'/admin/users/{w["owner"]}/delete',
                                      data={'step': '3'})
    assert resp.status_code == 302
    assert find_orphans() == []


def test_world_itself_has_no_orphans():
    """Sanity check on the fixture: find_orphans() must be silent on a fresh,
    fully-seeded world — otherwise a false positive below would be the
    fixture's fault, not the cascade's."""
    world()
    assert find_orphans() == []


# ── Override routes (final-review finding) ─────────────────────────────────

def test_add_override_accepts_only_hide():
    """The only form that posts here sends action='hide'. Anything else used
    to be stored verbatim, so a request could create legacy 'add' / 'override'
    rows that the curriculum engine still honours."""
    w = world()
    before = SectionModuleExercise.query.filter_by(section_id=w['section']).count()
    resp = client_as(w['assigned']).post(
        f'/teacher/sections/{w["section"]}/overrides/add',
        data={'action': 'add', 'module_id': w['m_course']})
    assert resp.status_code == 400, 'an override action other than hide must be refused'
    db.session.expire_all()
    assert SectionModuleExercise.query.filter_by(section_id=w['section']).count() == before


def test_removing_an_override_never_orphans_a_completion():
    """teacher_delete_override deleted the row directly, bypassing
    _delete_overrides(), so a completion reaching it through
    section_exercise_id was left pointing at nothing."""
    w = world()
    ov_id = SectionModuleExercise.query.filter_by(
        section_id=w['section'], action='override').one().id
    assert ModuleCompletion.query.filter_by(section_exercise_id=ov_id).count() == 1, \
        'the fixture must give this override a completion, or the test proves nothing'
    client_as(w['assigned']).post(
        f'/teacher/sections/{w["section"]}/overrides/{ov_id}/delete')
    db.session.expire_all()
    assert SectionModuleExercise.query.filter_by(id=ov_id).first() is None
    assert find_orphans() == [], 'removing an override left a dangling completion'
