"""D12: hiding actually hides.

Teachers can hide a module or a single exercise for one section, and the
teacher's page says it worked — but curriculum.effective_exercises() never
read the 'hide' rows, so students still saw and could complete hidden work.

Self-contained, mirroring test_school_authority.py's pattern: an autouse
per-test schema fixture and tiny id-based factories, ending in a
client_as(uid) helper — one test client per user per test.
"""
from urllib.parse import urlsplit

import pytest

from app import app
from models import (db, User, School, SchoolMembership, Course, Module,
                     ModuleExercise, Section, Melody, SectionModuleExercise,
                     ModuleCompletion)
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


def module(course_id, name, order):
    m = Module(name=name, course_id=course_id, order=order)
    db.session.add(m)
    db.session.commit()
    return m


def melody(name):
    m = Melody(name=name, midi_filename=f'{name}.mid', notes_json='[]',
               clef='treble', min_duration='q', time_signature='4/4', difficulty=1)
    db.session.add(m)
    db.session.commit()
    return m


def module_exercise(module_id, name, exercise_id, order=0):
    me = ModuleExercise(module_id=module_id, exercise_type='melody',
                        exercise_id=exercise_id, name=name, order=order)
    db.session.add(me)
    db.session.commit()
    return me


class _Client:
    """A test client whose every request runs in its own, fresh app context.

    The autouse `ctx` fixture holds one app context open for the whole test.
    Flask reuses an already-pushed app context for each request, and
    Flask-Login caches the loaded user on that context's `g` — so without
    this, once the teacher helper makes a request, every later request "as
    the student" silently runs as the teacher. A fresh context per request
    gives each one its own `g`, and so its own user.
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
    """School + course + teacher (owns the section) + student, with two
    modules: M1 (Exercise A, Exercise B) for exercise-level hide tests, and
    M2 (Exercise C) kept separate so module-level hide tests have another,
    always-visible module to use as a control. Every module exercise has a
    real backing Melody so a launch that isn't blocked actually redirects
    into a drill (302 to /exercise/<id>), not just any 302."""
    s = school('Hide')
    at = user('admin_teacher', 'at@hide.com')
    member(s, at, 'admin_teacher')
    stu = user('student', 'stu@hide.com')
    member(s, stu, 'student')
    crs = course(s)

    m1 = module(crs.id, 'Module One', 0)
    mel_a = melody('MelA')
    mel_b = melody('MelB')
    ex_a = module_exercise(m1.id, 'Exercise A', mel_a.id, order=0)
    ex_b = module_exercise(m1.id, 'Exercise B', mel_b.id, order=1)

    m2 = module(crs.id, 'Module Two', 1)
    mel_c = melody('MelC')
    ex_c = module_exercise(m2.id, 'Exercise C', mel_c.id, order=0)

    sec = Section(name='Sec 1', join_code='HIDE01', teacher_id=at.id, course_id=crs.id)
    sec.members.append(stu)
    db.session.add(sec)
    db.session.commit()

    return {'school': s.id, 'at': at.id, 'stu': stu.id, 'course': crs.id,
            'm1': m1.id, 'ex_a': ex_a.id, 'ex_b': ex_b.id,
            'm2': m2.id, 'ex_c': ex_c.id, 'section': sec.id}


def hide_module(w, module_id):
    return client_as(w['at']).post(
        f'/teacher/sections/{w["section"]}/modules/{module_id}/hide')


def restore_module(w, module_id):
    return client_as(w['at']).post(
        f'/teacher/sections/{w["section"]}/modules/{module_id}/restore')


def hide_exercise(w, module_id, me_id):
    return client_as(w['at']).post(
        f'/teacher/sections/{w["section"]}/overrides/add',
        data={'action': 'hide', 'module_exercise_id': me_id, 'module_id': module_id})


def restore_exercise(w, me_id):
    sme = SectionModuleExercise.query.filter_by(
        section_id=w['section'], module_exercise_id=me_id, action='hide').first()
    return client_as(w['at']).post(
        f'/teacher/sections/{w["section"]}/overrides/{sme.id}/delete')


# ── Module-level hide ─────────────────────────────────────────────────────

def test_hidden_module_disappears_then_reappears_after_restore():
    w = world()
    hide_module(w, w['m2'])

    hidden_list = client_as(w['stu']).get(f'/section/{w["section"]}/modules').data.decode()
    assert 'Module One' in hidden_list, 'the untouched module must still be listed'
    assert 'Module Two' not in hidden_list, \
        'a module the teacher hid is still shown in the student module list'

    restore_module(w, w['m2'])

    restored_list = client_as(w['stu']).get(f'/section/{w["section"]}/modules').data.decode()
    assert 'Module Two' in restored_list, \
        'a restored module must reappear in the student module list'


def test_hidden_module_detail_404s_then_200s_after_restore():
    w = world()
    hide_module(w, w['m2'])
    resp = client_as(w['stu']).get(f'/section/{w["section"]}/modules/{w["m2"]}')
    assert resp.status_code == 404, \
        "a hidden module's detail page must 404 for a student, not render"

    restore_module(w, w['m2'])
    resp2 = client_as(w['stu']).get(f'/section/{w["section"]}/modules/{w["m2"]}')
    assert resp2.status_code == 200, \
        "a restored module's detail page must render again for a student"


def test_exercise_in_hidden_module_blocks_launch_and_restoring_module_allows_it():
    w = world()
    hide_module(w, w['m2'])

    blocked = client_as(w['stu']).get(
        f'/section/{w["section"]}/module_exercise/{w["ex_c"]}/start')
    assert blocked.status_code == 404, \
        'launching an exercise that belongs to a hidden module must 404, ' \
        'not redirect into the drill'

    restore_module(w, w['m2'])

    launched = client_as(w['stu']).get(
        f'/section/{w["section"]}/module_exercise/{w["ex_c"]}/start')
    assert launched.status_code == 302, \
        'once the module is restored, its exercises must be launchable again'


def test_hiding_module_twice_writes_only_one_row():
    w = world()
    hide_module(w, w['m2'])
    hide_module(w, w['m2'])

    rows = SectionModuleExercise.query.filter_by(
        section_id=w['section'], module_id=w['m2'],
        module_exercise_id=None, action='hide').all()
    assert len(rows) == 1, \
        f'hiding the same module twice must stay idempotent (one module-level ' \
        f'row with module_exercise_id NULL), found {len(rows)} matching rows'


def test_restoring_module_does_not_unhide_an_individually_hidden_exercise():
    w = world()
    hide_exercise(w, w['m1'], w['ex_b'])   # exercise-level hide, independent
    hide_module(w, w['m1'])                # then hide the whole module too
    restore_module(w, w['m1'])             # ...and restore just the module

    resp = client_as(w['stu']).get(f'/section/{w["section"]}/modules/{w["m1"]}')
    assert resp.status_code == 200
    body = resp.data.decode()
    assert 'Exercise A' in body
    assert 'Exercise B' not in body, \
        'restoring the module must not resurrect an exercise that was ' \
        'hidden individually before the module-level hide'


# ── Exercise-level hide ───────────────────────────────────────────────────

def test_hidden_exercise_absent_from_module_detail_page():
    w = world()
    hide_exercise(w, w['m1'], w['ex_b'])

    resp = client_as(w['stu']).get(f'/section/{w["section"]}/modules/{w["m1"]}')
    assert resp.status_code == 200
    body = resp.data.decode()
    assert 'Exercise A' in body
    assert 'Exercise B' not in body, \
        "a hidden exercise still appears on its module's page"


def test_hidden_exercise_blocks_launch_and_restoring_it_allows_launch_again():
    w = world()
    hide_exercise(w, w['m1'], w['ex_b'])

    blocked = client_as(w['stu']).get(
        f'/section/{w["section"]}/module_exercise/{w["ex_b"]}/start')
    assert blocked.status_code == 404, \
        'launching a hidden exercise must 404, not redirect into the drill'

    restore_exercise(w, w['ex_b'])

    launched = client_as(w['stu']).get(
        f'/section/{w["section"]}/module_exercise/{w["ex_b"]}/start')
    assert launched.status_code == 302 and _redirect_path(launched).startswith('/exercise/'), \
        'a restored exercise must be launchable again'


# ── Hidden ≠ deleted ───────────────────────────────────────────────────

def test_hiding_an_exercise_keeps_progress_and_restoring_shows_it_again():
    w = world()
    cur.record_attempt(w['stu'], w['section'], module_exercise_id=w['ex_b'],
                       score=None, criterion={'attempts': 1})

    hide_exercise(w, w['m1'], w['ex_b'])

    hidden_body = client_as(w['stu']).get(f'/section/{w["section"]}/modules/{w["m1"]}').data.decode()
    assert 'Exercise B' not in hidden_body, \
        'a hidden exercise with existing progress must still be hidden, ' \
        'not shown just because it is complete'

    mc = ModuleCompletion.query.filter_by(
        user_id=w['stu'], section_id=w['section'], module_exercise_id=w['ex_b']).first()
    assert mc is not None and mc.is_complete, \
        "hiding an exercise must not delete the student's existing progress on it"

    restore_exercise(w, w['ex_b'])

    restored_body = client_as(w['stu']).get(f'/section/{w["section"]}/modules/{w["m1"]}').data.decode()
    assert 'Exercise B' in restored_body and 'border-success' in restored_body, \
        "restoring the exercise must show it again with its prior completion intact"


# ── Teacher-facing: the Edit page must reflect the module-level row ────────

def test_edit_page_shows_restore_after_hiding_an_empty_module():
    """An empty module has no exercises to loop over — the old
    write-one-row-per-exercise scheme silently wrote nothing for it, so the
    page kept offering "Hide module" after a teacher hid it even though the
    flash said it worked. The toggle must read the module-level hide row,
    not the count of per-exercise rows.

    Task 5 moved module hide/restore off the section Edit page (now a short
    card linking to Curriculum) onto the new Curriculum list page — this
    checks the toggle there instead, same invariant."""
    w = world()
    empty = module(w['course'], 'Empty Module', 2)
    assert hide_module(w, empty.id).status_code == 302

    page = client_as(w['at']).get(f'/teacher/section/{w["section"]}/curriculum')
    body = page.data.decode()
    assert body.count('Restore module') == 1, \
        'hiding an empty module must flip its Curriculum-page toggle to "Restore module"'
    assert 'Hide module' in body, 'the untouched modules must still offer "Hide module"'
