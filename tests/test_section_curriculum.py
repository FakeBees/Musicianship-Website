"""Task 5: Section curriculum pages.

Section Teachers build their own section's curriculum with the same tools
School Admins use for a course: a Curriculum list page
(/teacher/section/<id>/curriculum) and a per-module page
(/teacher/section/<id>/curriculum/modules/<module_id>) that reuses Task 2's
full exercise editor.

Self-contained, mirroring test_section_content.py's pattern exactly: an
autouse per-test schema fixture, tiny id-based factories, and a
client_as(uid) helper backed by _Client — one fresh app context per request,
so two different section teachers (and a student) in the same test genuinely
run as themselves, not as whichever user made the first request (Flask-Login
caches the loaded user on the app context's `g`; see _Client's docstring).
"""
import re
from urllib.parse import urlsplit

import pytest

from app import app
from models import (db, User, School, SchoolMembership, Course, Module,
                     ModuleExercise, Section, Melody, HolisticExercise,
                     SectionModuleExercise, ModuleCompletion)
import curriculum as cur


@pytest.fixture(autouse=True)
def ctx():
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


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


def course(school, name='C1'):
    c = Course(name=name, school_id=school.id)
    db.session.add(c)
    db.session.commit()
    return c


def module(course_id, name, order, section_id=None):
    m = Module(name=name, course_id=course_id, order=order, section_id=section_id)
    db.session.add(m)
    db.session.commit()
    return m


def melody(name):
    m = Melody(name=name, midi_filename=f'{name}.mid', notes_json='[]',
               clef='treble', min_duration='q', time_signature='4/4', difficulty=1)
    db.session.add(m)
    db.session.commit()
    return m


def holistic(name):
    h = HolisticExercise(name=name, folder=f'holistic/{name}/')
    db.session.add(h)
    db.session.commit()
    return h


def module_exercise(module_id, name, exercise_id, order=0, section_id=None, exercise_type='melody'):
    me = ModuleExercise(module_id=module_id, exercise_type=exercise_type,
                        exercise_id=exercise_id, name=name, order=order,
                        section_id=section_id)
    db.session.add(me)
    db.session.commit()
    return me


class _Client:
    """A test client whose every request runs in its own, fresh app context.
    Copied verbatim from tests/test_hidden_content.py — see its docstring
    for why this matters: without it, Flask-Login's cached user on `g`
    leaks across clients sharing one app context.
    """

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


def world():
    """One school, one course with a shared module + exercise, and two
    sections following that course — Sec A (taught by ct) and Sec B (taught
    by ct2). A student is enrolled only in Sec A.

    ct2 exists specifically to prove cross-section ownership checks and the
    test-harness's per-request isolation: several tests act as ct on Sec A's
    own authorized URL but target an id that belongs to Sec B (or vice
    versa), and one test proves ct2 is genuinely refused Sec A's pages
    (not silently running as ct).
    """
    s = school('Curr')
    at = user('admin_teacher', 'at@curr.com')
    member(s, at, 'admin_teacher')

    ct  = user('class_teacher', 'ct@curr.com')
    ct2 = user('class_teacher', 'ct2@curr.com')
    member(s, ct, 'class_teacher')
    member(s, ct2, 'class_teacher')

    stu = user('student', 'stu@curr.com')
    member(s, stu, 'student')

    crs = course(s)
    m_course = module(crs.id, 'Shared Module', 0)
    mel_course = melody('CourseMel')
    ex_course = module_exercise(m_course.id, 'Course Exercise', mel_course.id, order=0)

    sec_a = Section(name='Sec A', join_code='CURRA01', teacher_id=at.id,
                    assigned_teacher_id=ct.id, course_id=crs.id)
    sec_a.members.append(stu)
    db.session.add(sec_a)
    db.session.commit()

    sec_b = Section(name='Sec B', join_code='CURRB01', teacher_id=at.id,
                    assigned_teacher_id=ct2.id, course_id=crs.id)
    db.session.add(sec_b)
    db.session.commit()

    return {'school': s.id, 'at': at.id, 'ct': ct.id, 'ct2': ct2.id, 'stu': stu.id,
            'course': crs.id, 'm_course': m_course.id, 'ex_course': ex_course.id,
            'sec_a': sec_a.id, 'sec_b': sec_b.id}


def _redirect_path(resp):
    return urlsplit(resp.headers['Location']).path


# ── Adding a module for this section only ──────────────────────────────────

def test_section_teacher_can_add_a_section_only_module():
    w = world()
    resp = client_as(w['ct']).post(f'/teacher/section/{w["sec_a"]}/curriculum',
                                   data={'name': 'My Own Module', 'order': '1'})
    assert resp.status_code == 302
    mod = Module.query.filter_by(name='My Own Module').first()
    assert mod is not None, 'the section-only module was not created'
    assert mod.section_id == w['sec_a']
    assert mod.course_id == w['course']
    assert mod.order == 1


def test_curriculum_page_marks_course_vs_own_modules_and_shows_counts():
    w = world()
    own = module(w['course'], 'Own Module', 1, section_id=w['sec_a'])
    mel = melody('CountMel')
    module_exercise(own.id, 'CountEx', mel.id, section_id=w['sec_a'])

    body = client_as(w['ct']).get(f'/teacher/section/{w["sec_a"]}/curriculum').data.decode()
    assert 'Shared Module' in body
    assert 'Own Module' in body
    assert 'From course' in body, 'a course module must be marked as such'
    assert 'This Section only' in body, "a section's own module must be marked as such"
    assert re.search(r'curriculum-count">1<', body), \
        'each module row must show its own exercise count for this section'


def test_curriculum_page_says_no_course_assigned():
    w = world()
    courseless = Section(name='Courseless', join_code='NOCURR1',
                         teacher_id=w['at'], assigned_teacher_id=w['ct'])
    db.session.add(courseless)
    db.session.commit()
    body = client_as(w['ct']).get(f'/teacher/section/{courseless.id}/curriculum').data.decode()
    assert 'no course assigned' in body.lower()
    assert 'School Admin' in body


# ── Adding exercises: filter-based and holistic, to an own module and a course module ─

def test_section_teacher_can_add_a_filter_based_exercise_to_their_own_module():
    w = world()
    own = module(w['course'], 'Own Module', 1, section_id=w['sec_a'])
    resp = client_as(w['ct']).post(
        f'/teacher/section/{w["sec_a"]}/curriculum/modules/{own.id}',
        data={'exercise_type': 'melody', 'name': 'Filter Ex', 'order': '0'})
    assert resp.status_code == 302
    me = ModuleExercise.query.filter_by(name='Filter Ex').first()
    assert me is not None
    assert me.section_id == w['sec_a']
    assert me.module_id == own.id
    assert me.exercise_type == 'melody'


def test_section_teacher_can_add_a_holistic_exercise_to_a_course_module():
    w = world()
    hol = holistic('HolEx')
    resp = client_as(w['ct']).post(
        f'/teacher/section/{w["sec_a"]}/curriculum/modules/{w["m_course"]}',
        data={'exercise_type': 'holistic', 'exercise_id': str(hol.id), 'name': 'Hol Add'})
    assert resp.status_code == 302
    me = ModuleExercise.query.filter_by(name='Hol Add').first()
    assert me is not None
    assert me.section_id == w['sec_a'], \
        'adding an exercise to a shared course module must still tag it with this section'
    assert me.module_id == w['m_course']
    assert me.exercise_type == 'holistic'
    assert me.exercise_id == hol.id


def test_exercise_added_by_one_section_is_invisible_to_a_second_section_on_the_same_course():
    w = world()
    client_as(w['ct']).post(
        f'/teacher/section/{w["sec_a"]}/curriculum/modules/{w["m_course"]}',
        data={'exercise_type': 'melody', 'name': 'OnlyForA'})

    body_b = client_as(w['ct2']).get(
        f'/teacher/section/{w["sec_b"]}/curriculum/modules/{w["m_course"]}').data.decode()
    assert 'OnlyForA' not in body_b, \
        "Sec A's own addition to the shared module must not appear to Sec B's teacher"
    assert 'Course Exercise' in body_b


# ── Edit / duplicate / remove ───────────────────────────────────────────────

def test_section_teacher_can_edit_duplicate_and_remove_their_own_exercise():
    w = world()
    own = module(w['course'], 'Own Module', 1, section_id=w['sec_a'])
    mel = melody('EditMel')
    me = module_exercise(own.id, 'Editable', mel.id, section_id=w['sec_a'])
    me_id = me.id  # capture now — see the note in the module-delete test below

    edit_resp = client_as(w['ct']).post(
        f'/teacher/section/{w["sec_a"]}/curriculum/exercises/{me_id}/edit',
        data={'name': 'Renamed', 'order': '3'})
    assert edit_resp.status_code == 302
    # The edit ran in a separate request-scoped session (the _Client
    # pattern's fresh app context per request — see its docstring). This
    # test's own session still has `me` cached in its identity map from
    # creating it above, and Query.get() returns that cached object without
    # re-querying — expire_all() forces the next read to hit the DB.
    db.session.expire_all()
    updated = ModuleExercise.query.get(me_id)
    assert updated.name == 'Renamed' and updated.order == 3

    dup_resp = client_as(w['ct']).post(
        f'/teacher/section/{w["sec_a"]}/curriculum/exercises/{me_id}/duplicate')
    assert dup_resp.status_code == 302
    dup = ModuleExercise.query.filter_by(name='Renamed (copy)').first()
    assert dup is not None and dup.section_id == w['sec_a']

    remove_resp = client_as(w['ct']).post(
        f'/teacher/section/{w["sec_a"]}/curriculum/exercises/{me_id}/remove')
    assert remove_resp.status_code == 302
    # A plain filtered query, not .get(): .get() tries to REFRESH an
    # already-known instance by identity and raises ObjectDeletedError when
    # the row is genuinely gone, rather than returning None.
    assert ModuleExercise.query.filter_by(id=me_id).first() is None


def test_editing_a_holistic_exercise_cannot_change_which_exercise_it_is():
    w = world()
    own = module(w['course'], 'Own Module', 1, section_id=w['sec_a'])
    hol1 = holistic('Hol1')
    hol2 = holistic('Hol2')
    me = module_exercise(own.id, 'HolPick', hol1.id, section_id=w['sec_a'],
                         exercise_type='holistic')

    client_as(w['ct']).post(
        f'/teacher/section/{w["sec_a"]}/curriculum/exercises/{me.id}/edit',
        data={'name': 'Renamed Hol', 'exercise_id': str(hol2.id)})
    db.session.expire_all()  # see the note in the edit/duplicate/remove test above
    updated = ModuleExercise.query.get(me.id)
    assert updated.exercise_id == hol1.id, \
        'editing a holistic exercise must never change which exercise it points at'
    assert updated.name == 'Renamed Hol'


def test_removing_own_exercise_deletes_its_completion_rows():
    w = world()
    own = module(w['course'], 'Own Module', 1, section_id=w['sec_a'])
    mel = melody('CompMel')
    me = module_exercise(own.id, 'CompEx', mel.id, section_id=w['sec_a'])
    me_id = me.id  # capture now — see the note in the module-delete test below
    cur.record_attempt(w['stu'], w['sec_a'], module_exercise_id=me_id,
                       score=None, criterion={'attempts': 1})
    assert ModuleCompletion.query.filter_by(module_exercise_id=me_id).count() == 1

    client_as(w['ct']).post(
        f'/teacher/section/{w["sec_a"]}/curriculum/exercises/{me_id}/remove')
    # A plain filtered query, not .get(): .get() tries to REFRESH an
    # already-known instance by identity and raises ObjectDeletedError when
    # the row is genuinely gone (deleted by a different request-scoped
    # session — see the _Client docstring), rather than returning None.
    assert ModuleExercise.query.filter_by(id=me_id).first() is None
    assert ModuleCompletion.query.filter_by(module_exercise_id=me_id).count() == 0, \
        'removing an exercise must not orphan its completion rows'


def test_deleting_own_module_cascades_to_its_exercises_and_completions():
    w = world()
    own = module(w['course'], 'Own Module', 1, section_id=w['sec_a'])
    mel = melody('CascadeMel')
    me = module_exercise(own.id, 'CascadeEx', mel.id, section_id=w['sec_a'])
    # Capture plain ids now, before the delete: reading me.id fresh AFTER
    # its row is gone forces SQLAlchemy to try to refresh the (by-then
    # expired) ORM object by identity, which raises ObjectDeletedError
    # instead of just being unable to find a row — a different failure mode
    # than the plain "no such id" a fresh id-based query gives.
    own_id, me_id = own.id, me.id
    cur.record_attempt(w['stu'], w['sec_a'], module_exercise_id=me_id,
                       score=None, criterion={'attempts': 1})

    resp = client_as(w['ct']).post(
        f'/teacher/section/{w["sec_a"]}/curriculum/modules/{own_id}/delete')
    assert resp.status_code == 302
    assert Module.query.filter_by(id=own_id).first() is None
    assert ModuleExercise.query.filter_by(id=me_id).first() is None, \
        'deleting a module must delete its own exercises too'
    assert ModuleCompletion.query.filter_by(module_exercise_id=me_id).count() == 0, \
        'deleting a module must not orphan completion rows on its exercises'


# ── Ownership: ownership violations 404, not 403 (right role, wrong target) ─

def test_section_teacher_cannot_edit_another_sections_exercise():
    w = world()
    own_b = module(w['course'], 'B Own Module', 1, section_id=w['sec_b'])
    mel_b = melody('BMel')
    ex_b = module_exercise(own_b.id, 'B Own Ex', mel_b.id, section_id=w['sec_b'])

    resp = client_as(w['ct']).post(
        f'/teacher/section/{w["sec_a"]}/curriculum/exercises/{ex_b.id}/edit',
        data={'name': 'Hacked'})
    assert resp.status_code == 404, \
        "Sec A's teacher must not edit Sec B's own exercise, even through Sec A's own authorized URL"
    assert ModuleExercise.query.get(ex_b.id).name == 'B Own Ex'


def test_section_teacher_cannot_duplicate_or_remove_another_sections_exercise():
    w = world()
    own_b = module(w['course'], 'B Own Module', 1, section_id=w['sec_b'])
    mel_b = melody('BMel2')
    ex_b = module_exercise(own_b.id, 'B Own Ex 2', mel_b.id, section_id=w['sec_b'])

    dup = client_as(w['ct']).post(
        f'/teacher/section/{w["sec_a"]}/curriculum/exercises/{ex_b.id}/duplicate')
    assert dup.status_code == 404
    rem = client_as(w['ct']).post(
        f'/teacher/section/{w["sec_a"]}/curriculum/exercises/{ex_b.id}/remove')
    assert rem.status_code == 404
    assert ModuleExercise.query.get(ex_b.id) is not None, \
        'a blocked duplicate/remove must not have touched the other section\'s exercise'


def test_section_teacher_cannot_edit_a_course_exercise_through_the_section_route():
    w = world()
    resp = client_as(w['ct']).post(
        f'/teacher/section/{w["sec_a"]}/curriculum/exercises/{w["ex_course"]}/edit',
        data={'name': 'Hacked'})
    assert resp.status_code == 404, \
        'a course exercise (section_id NULL) must not be editable through the section route'
    assert ModuleExercise.query.get(w['ex_course']).name == 'Course Exercise'


def test_module_page_404s_for_another_sections_own_module():
    w = world()
    own_b = module(w['course'], 'B Own Module', 1, section_id=w['sec_b'])
    resp = client_as(w['ct']).get(f'/teacher/section/{w["sec_a"]}/curriculum/modules/{own_b.id}')
    assert resp.status_code == 404


def test_cannot_delete_a_course_module_through_the_section_route():
    w = world()
    resp = client_as(w['ct']).post(
        f'/teacher/section/{w["sec_a"]}/curriculum/modules/{w["m_course"]}/delete')
    assert resp.status_code == 404, \
        'a course module (section_id NULL) must not be deletable through the section route'
    assert Module.query.get(w['m_course']) is not None


def test_hide_module_404s_for_a_module_on_a_different_course():
    """Task 4 review's Minor finding: teacher_hide_module / teacher_restore_module
    used to skip the ownership check entirely."""
    w = world()
    other_school = school('Other')
    other_course = course(other_school, 'Other Course')
    foreign_module = module(other_course.id, 'Foreign', 0)

    resp = client_as(w['ct']).post(
        f'/teacher/sections/{w["sec_a"]}/modules/{foreign_module.id}/hide')
    assert resp.status_code == 404, \
        'hiding a module that belongs to a different course entirely must 404'


def test_restore_module_404s_for_a_module_on_a_different_course():
    w = world()
    other_school = school('Other2')
    other_course = course(other_school, 'Other Course 2')
    foreign_module = module(other_course.id, 'Foreign2', 0)

    resp = client_as(w['ct']).post(
        f'/teacher/sections/{w["sec_a"]}/modules/{foreign_module.id}/restore')
    assert resp.status_code == 404


# ── 403: role/authority failures (wrong caller entirely) ────────────────────

def test_student_cannot_reach_curriculum_pages():
    w = world()
    own = module(w['course'], 'Own Module', 1, section_id=w['sec_a'])
    assert client_as(w['stu']).get(f'/teacher/section/{w["sec_a"]}/curriculum').status_code == 403
    assert client_as(w['stu']).get(
        f'/teacher/section/{w["sec_a"]}/curriculum/modules/{own.id}').status_code == 403


def test_a_different_sections_teacher_is_forbidden_from_this_sections_curriculum():
    """ct2 is a legitimate Section Teacher — just not of Sec A. Asserting
    ct's own 200 first, on the exact same URL, is what makes the following
    403 a genuine proof rather than a lucky default: if the test harness's
    per-request isolation ever regressed (the documented Flask-Login
    g-caching trap), ct2's request would silently run as ct and this would
    wrongly pass with a 200 instead."""
    w = world()
    url = f'/teacher/section/{w["sec_a"]}/curriculum'
    assert client_as(w['ct']).get(url).status_code == 200, \
        'sanity check: the legitimate Section Teacher must reach their own Curriculum page'
    resp = client_as(w['ct2']).get(url)
    assert resp.status_code == 403, \
        "a different section's teacher (ct2, who legitimately teaches Sec B) must be " \
        "refused Sec A's Curriculum page"


# ── Launching what was added ─────────────────────────────────────────────────

def test_student_can_launch_a_newly_added_filter_exercise_and_holistic_exercise():
    w = world()
    own = module(w['course'], 'Own Module', 1, section_id=w['sec_a'])
    hol = holistic('LaunchHol')

    client_as(w['ct']).post(
        f'/teacher/section/{w["sec_a"]}/curriculum/modules/{own.id}',
        data={'exercise_type': 'melody', 'name': 'LaunchFilter'})
    filt_me = ModuleExercise.query.filter_by(name='LaunchFilter').first()

    client_as(w['ct']).post(
        f'/teacher/section/{w["sec_a"]}/curriculum/modules/{w["m_course"]}',
        data={'exercise_type': 'holistic', 'exercise_id': str(hol.id), 'name': 'LaunchHolistic'})
    hol_me = ModuleExercise.query.filter_by(name='LaunchHolistic').first()

    filt_launch = client_as(w['stu']).get(
        f'/section/{w["sec_a"]}/module_exercise/{filt_me.id}/start')
    assert filt_launch.status_code == 302 and _redirect_path(filt_launch).startswith('/exercise/'), \
        'a student must be able to launch a newly added filter-based exercise'

    hol_launch = client_as(w['stu']).get(
        f'/section/{w["sec_a"]}/module_exercise/{hol_me.id}/start')
    assert hol_launch.status_code == 302 and _redirect_path(hol_launch).startswith('/holistic/exercise/'), \
        'a student must be able to launch a newly added holistic exercise'


# ── Hide/restore wiring: buttons now live on the Curriculum pages ──────────

def test_hiding_a_course_module_redirects_to_curriculum_list_and_shows_hidden_badge():
    w = world()
    resp = client_as(w['ct']).post(
        f'/teacher/sections/{w["sec_a"]}/modules/{w["m_course"]}/hide')
    assert resp.status_code == 302
    assert _redirect_path(resp) == f'/teacher/section/{w["sec_a"]}/curriculum', \
        'hide/restore must return to the Curriculum list page, where its button now lives'
    body = client_as(w['ct']).get(f'/teacher/section/{w["sec_a"]}/curriculum').data.decode()
    assert 'Hidden' in body
    assert 'Restore module' in body


def test_hiding_a_course_exercise_redirects_to_the_module_detail_page():
    w = world()
    resp = client_as(w['ct']).post(
        f'/teacher/sections/{w["sec_a"]}/overrides/add',
        data={'action': 'hide', 'module_exercise_id': w['ex_course'], 'module_id': w['m_course']})
    assert resp.status_code == 302
    assert _redirect_path(resp) == f'/teacher/section/{w["sec_a"]}/curriculum/modules/{w["m_course"]}', \
        'hide/restore must return to the module page, where its button now lives'
    body = client_as(w['ct']).get(
        f'/teacher/section/{w["sec_a"]}/curriculum/modules/{w["m_course"]}').data.decode()
    assert 'Hidden' in body


# ── A section-own module's page has no "course exercises" section ──────────

def test_section_own_module_page_has_no_course_exercises_section():
    w = world()
    own = module(w['course'], 'Own Module', 1, section_id=w['sec_a'])
    body = client_as(w['ct']).get(
        f'/teacher/section/{w["sec_a"]}/curriculum/modules/{own.id}').data.decode()
    assert 'Course exercises' not in body


# ── Retirement of the old raw-ID form/route ─────────────────────────────────

def test_old_raw_id_add_route_is_retired():
    w = world()
    resp = client_as(w['ct']).post(
        f'/teacher/sections/{w["sec_a"]}/module_exercises/add',
        data={'module_id': w['m_course'], 'exercise_type': 'melody', 'exercise_id': 1})
    assert resp.status_code == 404


# ── Wiring: links to Curriculum from the edit page, roster, and dashboard ──

def test_edit_section_page_links_to_curriculum():
    w = world()
    body = client_as(w['ct']).get(f'/teacher/section/{w["sec_a"]}/edit').data.decode()
    assert f'href="/teacher/section/{w["sec_a"]}/curriculum"' in body


def test_roster_page_links_to_curriculum():
    w = world()
    body = client_as(w['ct']).get(f'/teacher/section/{w["sec_a"]}').data.decode()
    assert f'href="/teacher/section/{w["sec_a"]}/curriculum"' in body


def test_dashboard_card_links_to_curriculum():
    w = world()
    body = client_as(w['ct']).get('/teacher').data.decode()
    assert f'href="/teacher/section/{w["sec_a"]}/curriculum"' in body
