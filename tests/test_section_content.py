"""Task 4: section content engine.

A Section Teacher will (Task 5) be able to add a module that belongs only to
their own section, and add exercises to it — or to a shared course module —
exactly like a School Admin adds course exercises. This suite proves the
data/engine layer behaves correctly for such rows created directly in the
database, with no UI yet: `Module.section_id` / `ModuleExercise.section_id`
(physical column `class_id`) is NULL for course content, or a section's own
id for that section's own content.

Self-contained, mirroring test_hidden_content.py's pattern exactly: an
autouse per-test schema fixture, tiny id-based factories, and a client_as(uid)
helper backed by _Client — one fresh app context per request, so that two
different sections' students in the same test genuinely run as themselves
and not as whichever user made the first request (Flask-Login caches the
loaded user on the app context's `g`; see _Client's docstring).
"""
import re
from urllib.parse import urlsplit

import pytest

from app import app
from models import (db, User, School, SchoolMembership, Course, Module,
                     ModuleExercise, Section, Melody, SectionModuleExercise,
                     ModuleCompletion, UserAttempt)


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


def module_exercise(module_id, name, exercise_id, order=0, section_id=None):
    me = ModuleExercise(module_id=module_id, exercise_type='melody',
                        exercise_id=exercise_id, name=name, order=order,
                        section_id=section_id)
    db.session.add(me)
    db.session.commit()
    return me


class _Client:
    """A test client whose every request runs in its own, fresh app context.

    The autouse `ctx` fixture holds one app context open for the whole test.
    Flask reuses an already-pushed app context for each request, and
    Flask-Login caches the loaded user on that context's `g` — so without
    this, once one user's helper makes a request, every later request "as"
    a different user silently runs as the first one. A fresh context per
    request gives each one its own `g`, and so its own user. Copied verbatim
    from tests/test_hidden_content.py.
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


def _redirect_path(resp):
    return urlsplit(resp.headers['Location']).path


def world():
    """One school, two courses (Course A / Course B), one admin_teacher who
    owns everything, and two sections (Sec A / Sec B) both following Course A
    — each with its own single student.

    Course A has one shared module ("Shared Module") with one shared exercise
    ("Course Exercise"). Section A additionally owns:
      - a module of its own ("Section A Module", tied to Course A — the
        course it was made for) holding one exercise of its own
        ("Section A Own Exercise"), and
      - an exercise of its own added directly onto the *shared* module
        ("Section A Exercise On Shared Module") — proving section ownership
        is tracked per-row, not just per-module.

    Every exercise has a real backing Melody so a launch that isn't blocked
    actually redirects into a drill (302 to /exercise/<id>), not just any
    302. Course B starts empty and exists only for the course-switch test.
    """
    s = school('SecCon')
    at = user('admin_teacher', 'at@seccon.com')
    member(s, at, 'admin_teacher')

    stu_a = user('student', 'stua@seccon.com')
    stu_b = user('student', 'stub@seccon.com')
    member(s, stu_a, 'student')
    member(s, stu_b, 'student')

    crs = course(s, 'Course A')
    crs2 = course(s, 'Course B')

    m_course = module(crs.id, 'Shared Module', 0)
    mel_course = melody('CourseMel')
    ex_course = module_exercise(m_course.id, 'Course Exercise', mel_course.id, order=0)

    sec_a = Section(name='Sec A', join_code='SECA001', teacher_id=at.id, course_id=crs.id)
    sec_a.members.append(stu_a)
    db.session.add(sec_a)
    db.session.commit()

    sec_b = Section(name='Sec B', join_code='SECB001', teacher_id=at.id, course_id=crs.id)
    sec_b.members.append(stu_b)
    db.session.add(sec_b)
    db.session.commit()

    # Section A's own module, tied to the course it was made for.
    m_a = module(crs.id, 'Section A Module', 1, section_id=sec_a.id)
    mel_a = melody('SectionAMel')
    ex_a_own = module_exercise(m_a.id, 'Section A Own Exercise', mel_a.id,
                               order=0, section_id=sec_a.id)

    # Section A's own exercise, added directly onto the SHARED course module.
    mel_a2 = melody('SectionAOnSharedMel')
    ex_a_on_shared = module_exercise(m_course.id, 'Section A Exercise On Shared Module',
                                     mel_a2.id, order=1, section_id=sec_a.id)

    return {'school': s.id, 'at': at.id, 'stu_a': stu_a.id, 'stu_b': stu_b.id,
            'course': crs.id, 'course2': crs2.id,
            'm_course': m_course.id, 'ex_course': ex_course.id,
            'sec_a': sec_a.id, 'sec_b': sec_b.id,
            'm_a': m_a.id, 'ex_a_own': ex_a_own.id,
            'ex_a_on_shared': ex_a_on_shared.id}


# ── A section's own module: visible and launchable for its own section ────

def test_section_own_module_visible_and_launchable_for_its_own_section():
    w = world()
    body = client_as(w['stu_a']).get(f'/section/{w["sec_a"]}/modules').data.decode()
    assert 'Section A Module' in body, \
        "a section's own module must appear in its own students' module list"

    detail = client_as(w['stu_a']).get(f'/section/{w["sec_a"]}/modules/{w["m_a"]}')
    assert detail.status_code == 200, \
        "a section's own module detail page must render for its own students"
    assert 'Section A Own Exercise' in detail.data.decode()

    launch = client_as(w['stu_a']).get(
        f'/section/{w["sec_a"]}/module_exercise/{w["ex_a_own"]}/start')
    assert launch.status_code == 302 and _redirect_path(launch).startswith('/exercise/'), \
        "a section's own exercise on its own module must be launchable by its own students"


# ── A section's own module: invisible to a different section, same course ─

def test_section_own_module_invisible_to_a_different_section_on_the_same_course():
    w = world()
    body = client_as(w['stu_b']).get(f'/section/{w["sec_b"]}/modules').data.decode()
    assert 'Section A Module' not in body, \
        "section A's own module must not appear to section B's students, " \
        "even though both sections follow the same course"

    # stu_b requests through THEIR OWN section's URL (sec_b), asking for a
    # module that belongs to sec_a — this is the ownership check, not the
    # section-membership check (which would 403 before ever reaching it).
    detail = client_as(w['stu_b']).get(f'/section/{w["sec_b"]}/modules/{w["m_a"]}')
    assert detail.status_code == 404, \
        "section A's own module must 404 when a different section (even on " \
        "the same course) asks for its detail page"

    launch = client_as(w['stu_b']).get(
        f'/section/{w["sec_b"]}/module_exercise/{w["ex_a_own"]}/start')
    assert launch.status_code == 404, \
        "section A's own exercise must 404 when launched through a different section"


# ── A section's own exercise on a SHARED module: per-row ownership ────────

def test_section_own_exercise_on_shared_module_visible_only_to_its_own_section():
    w = world()
    body_a = client_as(w['stu_a']).get(f'/section/{w["sec_a"]}/modules/{w["m_course"]}').data.decode()
    assert 'Section A Exercise On Shared Module' in body_a, \
        "section A's own exercise added to the shared course module must " \
        "appear to section A's own students"

    body_b = client_as(w['stu_b']).get(f'/section/{w["sec_b"]}/modules/{w["m_course"]}').data.decode()
    assert 'Course Exercise' in body_b, 'the shared course exercise must still show for section B'
    assert 'Section A Exercise On Shared Module' not in body_b, \
        "section A's own exercise on the shared module must not appear to " \
        "section B's students, even on the very same module"

    launch_b = client_as(w['stu_b']).get(
        f'/section/{w["sec_b"]}/module_exercise/{w["ex_a_on_shared"]}/start')
    assert launch_b.status_code == 404, \
        "section A's own exercise on the shared module must 404 for section B's launcher"

    launch_a = client_as(w['stu_a']).get(
        f'/section/{w["sec_a"]}/module_exercise/{w["ex_a_on_shared"]}/start')
    assert launch_a.status_code == 302 and _redirect_path(launch_a).startswith('/exercise/'), \
        "section A's own exercise on the shared module must launch for section A"


# ── Course-level (School Admin) pages exclude section content ─────────────

def test_admin_courses_page_module_count_excludes_section_owned_modules():
    w = world()
    body = client_as(w['at']).get(f'/admin/schools/{w["school"]}/courses').data.decode()
    m = re.search(r'Course A</a></td>\s*<td>\s*(\d+)', body)
    assert m is not None, 'could not find the Course A row on the admin courses page'
    assert m.group(1) == '1', \
        f"Course A physically has 2 modules (1 course-owned, 1 section-owned) " \
        f"but the admin courses page must count only section_id-NULL modules " \
        f"— showed {m.group(1)}"


def test_admin_modules_page_excludes_section_owned_modules_and_exercise_counts():
    w = world()
    body = client_as(w['at']).get(f'/admin/courses/{w["course"]}/modules').data.decode()
    assert 'Shared Module' in body
    assert 'Section A Module' not in body, \
        "a section's own module must not be listed on the course's admin modules page"

    m = re.search(r'Shared Module</a></td>\s*<td>(\d+)</td>', body)
    assert m is not None, 'could not find the Shared Module row'
    assert m.group(1) == '1', \
        f"Shared Module physically has 2 exercises (1 course-owned, 1 " \
        f"section-owned) but the admin modules page must count only " \
        f"section_id-NULL exercises — showed {m.group(1)}"


def test_admin_module_exercises_page_excludes_section_owned_exercises():
    w = world()
    body = client_as(w['at']).get(f'/admin/modules/{w["m_course"]}/exercises').data.decode()
    assert 'Course Exercise' in body
    assert 'Section A Exercise On Shared Module' not in body, \
        "a section's own exercise on a shared course module must not be " \
        "listed on that module's admin exercises page"


def test_duplicate_course_excludes_section_content():
    w = world()
    resp = client_as(w['at']).post(f'/admin/courses/{w["course"]}/duplicate')
    assert resp.status_code == 302

    dup = Course.query.filter_by(name='Course A (copy)').first()
    assert dup is not None, 'duplicate course was not created'

    dup_module_names = {m.name for m in Module.query.filter_by(course_id=dup.id).all()}
    assert dup_module_names == {'Shared Module'}, \
        f"duplicating a course must copy only its course-owned modules, not " \
        f"section-owned ones — copied {dup_module_names}"

    dup_shared = Module.query.filter_by(course_id=dup.id, name='Shared Module').first()
    dup_ex_names = {e.name for e in ModuleExercise.query.filter_by(module_id=dup_shared.id).all()}
    assert dup_ex_names == {'Course Exercise'}, \
        f"duplicating a course must copy only course-owned exercises on a " \
        f"shared module, not a section's own addition — copied {dup_ex_names}"


def test_deleting_course_with_section_owned_content_does_not_crash():
    w = world()
    # Task 6: deleting only happens on a step=3 POST — the three-step confirm
    # this test doesn't otherwise care about. Posting step=3 keeps this
    # test's original intent: a course with section-owned modules/exercises
    # attached must delete cleanly, not 500.
    resp = client_as(w['at']).post(f'/admin/courses/{w["course"]}/delete',
                                   data={'step': '3'})
    assert resp.status_code == 302, \
        "deleting a course that has section-owned modules/exercises attached " \
        "must not crash — cascade cleanup of section content must handle it"
    assert Course.query.get(w['course']) is None, \
        "a step=3 POST must actually delete the course"


# ── Section content is tied to its course ──────────────────────────────────

def test_section_content_dormant_when_section_switches_course_then_restored():
    w = world()
    pre = client_as(w['stu_a']).get(f'/section/{w["sec_a"]}/modules').data.decode()
    assert 'Section A Module' in pre

    sec_a = Section.query.get(w['sec_a'])
    sec_a.course_id = w['course2']
    db.session.commit()

    during_body = client_as(w['stu_a']).get(f'/section/{w["sec_a"]}/modules').data.decode()
    assert 'Section A Module' not in during_body, \
        "switching the section to a different course must hide its own " \
        "module (tied to the original course) from the module list"

    detail_during = client_as(w['stu_a']).get(f'/section/{w["sec_a"]}/modules/{w["m_a"]}')
    assert detail_during.status_code == 404, \
        "a section's own module must 404 once the section has switched to a " \
        "different course"

    sec_a2 = Section.query.get(w['sec_a'])
    sec_a2.course_id = w['course']
    db.session.commit()

    after_body = client_as(w['stu_a']).get(f'/section/{w["sec_a"]}/modules').data.decode()
    assert 'Section A Module' in after_body, \
        "switching the section back to its original course must restore its own module"

    detail_after = client_as(w['stu_a']).get(f'/section/{w["sec_a"]}/modules/{w["m_a"]}')
    assert detail_after.status_code == 200, \
        "a section's own module detail page must render again after switching back"


# ── Section-facing management pages ────────────────────────────────────────

def test_edit_section_page_lists_own_module_only_for_its_own_section():
    """Task 5 moved module/exercise management off the section Edit page
    (now a short card linking to Curriculum) onto the new Curriculum list
    page — this checks the same per-section scoping invariant there."""
    w = world()
    body_a = client_as(w['at']).get(f'/teacher/section/{w["sec_a"]}/curriculum').data.decode()
    assert 'Section A Module' in body_a, \
        "section A's Curriculum page must list its own module"

    body_b = client_as(w['at']).get(f'/teacher/section/{w["sec_b"]}/curriculum').data.decode()
    assert 'Shared Module' in body_b
    assert 'Section A Module' not in body_b, \
        "section B's Curriculum page must not list section A's own module, even " \
        "though both sections share the same course"


def test_me_page_shows_progress_for_a_sections_own_module():
    w = world()
    body = client_as(w['stu_a']).get('/me').data.decode()
    assert 'Section A Module' in body, \
        "the My Progress page must include a section's own module in that " \
        "section's module-progress list"


# ── Forged completion: sharing a course is not enough ──────────────────────

def test_forged_section_id_on_another_sections_own_exercise_does_not_record_completion():
    w = world()
    me = ModuleExercise.query.get(w['ex_a_on_shared'])
    attempt = UserAttempt(melody_id=me.exercise_id, user_notes_json='[]',
                          overall_score=100.0, user_id=w['stu_b'])
    db.session.add(attempt)
    db.session.commit()

    # stu_b is legitimately a member of sec_b, and sec_b follows the same
    # course as sec_a — so a forged me_id belonging to sec_a's own exercise
    # (sitting on the shared module) must still be rejected.
    resp = client_as(w['stu_b']).get(
        f'/results/{attempt.id}?section_id={w["sec_b"]}&me_id={w["ex_a_on_shared"]}')
    assert resp.status_code == 200

    mc = ModuleCompletion.query.filter_by(
        user_id=w['stu_b'], section_id=w['sec_b'],
        module_exercise_id=w['ex_a_on_shared']).first()
    assert mc is None, \
        "a forged section_id must not let a student record progress against " \
        "another section's own exercise, even one sitting on a shared course module"


# ── Course-level admin routes refuse section-owned content (follow-up) ────
#
# Concern #2 from the first pass: a School Admin could reach a section's own
# module through the course editor by typing its id
# (/admin/modules/<section_module_id>/exercises) and add a course-level
# exercise inside it. The ownership model shouldn't be bendable that way —
# section content is Task 5's territory. Each of these five routes must 404
# when the module or exercise it targets is section-owned, and must still
# work normally for course content (positive control, same School Admin).

def test_admin_module_exercises_404s_for_a_section_owned_module():
    w = world()
    get_blocked = client_as(w['at']).get(f'/admin/modules/{w["m_a"]}/exercises')
    assert get_blocked.status_code == 404, \
        "a School Admin must not reach a section-owned module's exercise " \
        "page through the course editor"

    post_blocked = client_as(w['at']).post(f'/admin/modules/{w["m_a"]}/exercises', data={
        'exercise_type': 'melody', 'name': 'Should Not Exist', 'order': '0',
    })
    assert post_blocked.status_code == 404, \
        "a School Admin must not be able to add a course-level exercise " \
        "into a section-owned module"
    assert ModuleExercise.query.filter_by(name='Should Not Exist').first() is None, \
        "the blocked POST must not have created an exercise"

    # Positive control: same admin, same route shape, a course-owned module.
    get_ok = client_as(w['at']).get(f'/admin/modules/{w["m_course"]}/exercises')
    assert get_ok.status_code == 200, \
        "the route itself must still work for a course-owned module (control)"

    post_ok = client_as(w['at']).post(f'/admin/modules/{w["m_course"]}/exercises', data={
        'exercise_type': 'melody', 'name': 'New Course Exercise', 'order': '0',
    })
    assert post_ok.status_code == 302, \
        "adding an exercise to a course-owned module must still succeed (control)"
    assert ModuleExercise.query.filter_by(
        name='New Course Exercise', module_id=w['m_course']).first() is not None


def test_admin_delete_module_404s_for_a_section_owned_module():
    w = world()
    blocked = client_as(w['at']).post(f'/admin/modules/{w["m_a"]}/delete')
    assert blocked.status_code == 404, \
        "a School Admin must not be able to delete a section-owned module " \
        "through the course editor"
    assert Module.query.get(w['m_a']) is not None, \
        "the blocked delete must not have removed the module"

    ok = client_as(w['at']).post(f'/admin/modules/{w["m_course"]}/delete')
    assert ok.status_code == 302, \
        "deleting a course-owned module must still succeed (control)"
    assert Module.query.get(w['m_course']) is None


def test_admin_edit_module_exercise_404s_for_a_section_owned_exercise():
    w = world()
    blocked = client_as(w['at']).post(
        f'/admin/module_exercises/{w["ex_a_own"]}/edit', data={'name': 'Hacked'})
    assert blocked.status_code == 404, \
        "a School Admin must not be able to edit a section-owned exercise " \
        "through the course editor"
    assert ModuleExercise.query.get(w['ex_a_own']).name == 'Section A Own Exercise', \
        "the blocked edit must not have changed the exercise"

    ok = client_as(w['at']).post(
        f'/admin/module_exercises/{w["ex_course"]}/edit', data={'name': 'Renamed'})
    assert ok.status_code == 302, \
        "editing a course-owned exercise must still succeed (control)"
    assert ModuleExercise.query.get(w['ex_course']).name == 'Renamed'


def test_admin_delete_module_exercise_404s_for_a_section_owned_exercise():
    w = world()
    blocked = client_as(w['at']).post(f'/admin/module_exercises/{w["ex_a_own"]}/delete')
    assert blocked.status_code == 404, \
        "a School Admin must not be able to delete a section-owned exercise " \
        "through the course editor"
    assert ModuleExercise.query.get(w['ex_a_own']) is not None, \
        "the blocked delete must not have removed the exercise"

    ok = client_as(w['at']).post(f'/admin/module_exercises/{w["ex_course"]}/delete')
    assert ok.status_code == 302, \
        "deleting a course-owned exercise must still succeed (control)"
    assert ModuleExercise.query.get(w['ex_course']) is None


def test_admin_duplicate_module_exercise_404s_for_a_section_owned_exercise():
    w = world()
    blocked = client_as(w['at']).post(f'/admin/module_exercises/{w["ex_a_own"]}/duplicate')
    assert blocked.status_code == 404, \
        "a School Admin must not be able to duplicate a section-owned " \
        "exercise through the course editor"
    assert ModuleExercise.query.filter_by(name='Section A Own Exercise (copy)').first() is None

    ok = client_as(w['at']).post(f'/admin/module_exercises/{w["ex_course"]}/duplicate')
    assert ok.status_code == 302, \
        "duplicating a course-owned exercise must still succeed (control)"
    assert ModuleExercise.query.filter_by(name='Course Exercise (copy)').first() is not None
