"""Module-exercise filters actually work (D23 clef/min-duration, D25 multi
time-signature) and the live match counter carries difficulty for every
type (D24).

Self-contained, mirroring test_school_authority.py's pattern: an autouse
per-test schema fixture and tiny id-based factories, ending in a
client_as(uid) helper — one test client per user per test.
"""
import json
import re
from urllib.parse import urlsplit

import pytest

from app import app
from models import (db, User, School, SchoolMembership, Course, Module,
                     ModuleExercise, Section, Melody, Rhythm)


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


def client_as(uid):
    app.config['TESTING'] = True
    c = app.test_client()
    with c.session_transaction() as s:
        s['_user_id'] = str(uid)
        s['_fresh'] = True
    return c


def world():
    """School + course + module + section: an admin_teacher who owns the
    course (for the admin POST routes) and a student enrolled in the
    section (for start_module_exercise)."""
    s = school('Filters')
    at = user('admin_teacher', 'at@f.com')
    member(s, at, 'admin_teacher')
    stu = user('student', 'stu@f.com')
    member(s, stu, 'student')
    crs = course(s)
    mod = Module(name='M1', course_id=crs.id, order=0)
    db.session.add(mod)
    db.session.commit()
    sec = Section(name='Sec 1', join_code='FILT01', teacher_id=at.id, course_id=crs.id)
    sec.members.append(stu)
    db.session.add(sec)
    db.session.commit()
    return {'school': s.id, 'at': at.id, 'stu': stu.id, 'course': crs.id,
            'module': mod.id, 'section': sec.id}


def melody(name, clef='treble', min_duration='q', time_signature='4/4', difficulty=1):
    m = Melody(name=name, midi_filename=f'{name}.mid', notes_json='[]',
               clef=clef, min_duration=min_duration, time_signature=time_signature,
               difficulty=difficulty)
    db.session.add(m)
    db.session.commit()
    return m


def rhythm(name, min_duration='q', time_signature='4/4', difficulty=1):
    r = Rhythm(name=name, notes_json='[]', min_duration=min_duration,
               time_signature=time_signature, difficulty=difficulty)
    db.session.add(r)
    db.session.commit()
    return r


def make_module_exercise(module_id, exercise_type, params):
    me = ModuleExercise(module_id=module_id, exercise_type=exercise_type,
                        exercise_id=0, name='ME', order=0,
                        params_json=json.dumps(params) if params else None)
    db.session.add(me)
    db.session.commit()
    return me.id


def _redirect_path(resp):
    return urlsplit(resp.headers['Location']).path


# ── D23: clef and min-duration are actually applied at launch ───────────────

def test_start_module_exercise_filters_melody_by_clef_and_min_duration():
    """A melody module exercise filtered to clef=bass, min_duration=8 must
    only ever launch the matching melody, never the mismatched one.

    Only one row can pass the filter, but start_module_exercise still picks
    randomly among whatever DOES pass it — with the filter broken, both rows
    pass and a single launch has a 50% chance of landing on the match purely
    by luck. Launch repeatedly so an unfiltered pick is caught reliably."""
    w = world()
    match = melody('Match', clef='bass', min_duration='8')
    melody('Mismatch', clef='treble', min_duration='q')
    me_id = make_module_exercise(w['module'], 'melody',
                                 {'clef': ['bass'], 'min_duration': ['8']})

    for _ in range(20):
        resp = client_as(w['stu']).get(f'/section/{w["section"]}/module_exercise/{me_id}/start')
        assert resp.status_code == 302
        assert _redirect_path(resp) == f'/exercise/{match.id}'


def test_start_module_exercise_filters_rhythm_by_min_duration():
    """Rhythm has no clef column — only min_duration applies — and it must
    be enforced too. Repeated launches, for the same reason as the melody
    version above: a single unfiltered launch is only a 50/50 coin flip."""
    w = world()
    match = rhythm('Match', min_duration='16')
    rhythm('Mismatch', min_duration='q')
    me_id = make_module_exercise(w['module'], 'rhythm', {'min_duration': ['16']})

    for _ in range(20):
        resp = client_as(w['stu']).get(f'/section/{w["section"]}/module_exercise/{me_id}/start')
        assert resp.status_code == 302
        assert _redirect_path(resp) == f'/rhythm/exercise/{match.id}'


def test_start_module_exercise_no_match_flashes_warning_and_returns_to_module():
    """A filter combination the library can't satisfy must fall back to the
    module page with the 'No exercises match' warning, not silently serve
    something that doesn't fit the filter."""
    w = world()
    melody('OnlyTreble', clef='treble', min_duration='q')
    me_id = make_module_exercise(w['module'], 'melody', {'clef': ['bass']})

    c = client_as(w['stu'])
    resp = c.get(f'/section/{w["section"]}/module_exercise/{me_id}/start')
    assert resp.status_code == 302
    assert _redirect_path(resp) == f'/section/{w["section"]}/modules/{w["module"]}'
    with c.session_transaction() as sess:
        flashes = sess.get('_flashes', [])
    assert any(cat == 'warning' and 'No exercises match' in msg for cat, msg in flashes), \
        f'expected a "No exercises match" warning flash, got {flashes!r}'


# ── D25: several ticked time signatures, and pre-existing single-string rows ─

def test_start_module_exercise_filters_by_multiple_time_signatures():
    """params_json time_signature as a LIST (several boxes ticked) must OR
    across all of them and never launch a signature outside the set."""
    w = world()
    match_a = melody('3-4', time_signature='3/4')
    match_b = melody('2-4', time_signature='2/4')
    melody('4-4', time_signature='4/4')
    me_id = make_module_exercise(w['module'], 'melody',
                                 {'time_signature': ['3/4', '2/4']})

    seen = set()
    for _ in range(12):
        resp = client_as(w['stu']).get(f'/section/{w["section"]}/module_exercise/{me_id}/start')
        assert resp.status_code == 302
        seen.add(_redirect_path(resp))
    assert seen <= {f'/exercise/{match_a.id}', f'/exercise/{match_b.id}'}, \
        f'a launch redirected to a melody outside the selected time signatures: {seen!r}'


def test_start_module_exercise_time_signature_backward_compatible_as_plain_string():
    """Rows saved before D25 store time_signature as a bare string, not a
    list — _apply_exercise_filters must still honour those (existing
    exercises must not silently lose their filter when the code ships)."""
    w = world()
    match = melody('Match', time_signature='3/4')
    melody('Mismatch', time_signature='4/4')
    me_id = make_module_exercise(w['module'], 'melody', {'time_signature': '3/4'})

    resp = client_as(w['stu']).get(f'/section/{w["section"]}/module_exercise/{me_id}/start')
    assert resp.status_code == 302
    assert _redirect_path(resp) == f'/exercise/{match.id}'


# ── D23: the add/edit handlers must actually store clef and min-duration ────

def test_admin_add_module_exercise_stores_clef_and_min_duration():
    w = world()
    c = client_as(w['at'])
    resp = c.post(f'/admin/modules/{w["module"]}/exercises', data={
        'exercise_type': 'melody', 'name': 'Probe',
        'clef_cb': ['bass', 'tenor'], 'min_dur_cb': ['8'],
    })
    assert resp.status_code == 302
    me = ModuleExercise.query.filter_by(name='Probe').first()
    assert me is not None and me.params_json, 'clef/min_duration were not persisted at all'
    params = json.loads(me.params_json)
    assert sorted(params.get('clef', [])) == ['bass', 'tenor']
    assert params.get('min_duration') == ['8']


def test_admin_add_module_exercise_does_not_store_clef_for_rhythm():
    """Clef only exists on Melody — a rhythm exercise must never carry it,
    even if a crafted POST includes clef_cb (defence in depth: the real
    form hides and clears this row for non-melody types)."""
    w = world()
    c = client_as(w['at'])
    c.post(f'/admin/modules/{w["module"]}/exercises', data={
        'exercise_type': 'rhythm', 'name': 'ProbeRhythm',
        'clef_cb': ['bass'], 'min_dur_cb': ['16'],
    })
    me = ModuleExercise.query.filter_by(name='ProbeRhythm').first()
    assert me is not None and me.params_json
    params = json.loads(me.params_json)
    assert 'clef' not in params
    assert params.get('min_duration') == ['16']


def test_admin_edit_module_exercise_stores_clef_and_min_duration():
    w = world()
    me_id = make_module_exercise(w['module'], 'melody', {})
    c = client_as(w['at'])
    resp = c.post(f'/admin/module_exercises/{me_id}/edit', data={
        'name': 'Edited', 'clef_cb': ['tenor'], 'min_dur_cb': ['h'],
    })
    assert resp.status_code == 302
    me = ModuleExercise.query.get(me_id)
    assert me.params_json, 'clef/min_duration were not persisted on edit'
    params = json.loads(me.params_json)
    assert params.get('clef') == ['tenor']
    assert params.get('min_duration') == ['h']


# ── D25: the add handler stores one signature as a string, several as a list ─

def test_admin_add_module_exercise_stores_single_time_signature_as_string():
    w = world()
    c = client_as(w['at'])
    c.post(f'/admin/modules/{w["module"]}/exercises', data={
        'exercise_type': 'melody', 'name': 'OneSig', 'time_signature_cb': ['3/4'],
    })
    me = ModuleExercise.query.filter_by(name='OneSig').first()
    assert me.params_json, 'time_signature_cb was not persisted at all'
    params = json.loads(me.params_json)
    assert params.get('time_signature') == '3/4'


def test_admin_add_module_exercise_stores_multiple_time_signatures_as_list():
    w = world()
    c = client_as(w['at'])
    c.post(f'/admin/modules/{w["module"]}/exercises', data={
        'exercise_type': 'melody', 'name': 'TwoSigs',
        'time_signature_cb': ['3/4', '2/4'],
    })
    me = ModuleExercise.query.filter_by(name='TwoSigs').first()
    assert me.params_json, 'time_signature_cb was not persisted at all'
    params = json.loads(me.params_json)
    assert sorted(params.get('time_signature', [])) == ['2/4', '3/4']


# ── D24: the live match counter's data must include difficulty for every type ──

def test_module_exercises_page_ships_difficulty_for_melodies_and_rhythms():
    w = world()
    melody('DiffMelody', difficulty=4)
    rhythm('DiffRhythm', difficulty=5)
    resp = client_as(w['at']).get(f'/admin/modules/{w["module"]}/exercises')
    assert resp.status_code == 200
    body = resp.data.decode()
    m = re.search(r'const LIB = (\{.*?\});', body, re.S)
    assert m, 'module_exercises.html must still define const LIB = {...}'
    # The captured blob is a JS object literal (unquoted `melody:`/`rhythm:`/
    # `harmonic:` keys) — each *value* came from Jinja's `tojson`, so it's
    # valid JSON; only those three keys need quoting to parse the whole thing.
    raw = re.sub(r'\b(melody|rhythm|harmonic):', r'"\1":', m.group(1))
    raw = re.sub(r',(\s*})', r'\1', raw)
    lib = json.loads(raw)
    assert any(row.get('difficulty') == 4 for row in lib['melody']), \
        'melodies_data must carry difficulty so the counter can narrow by it'
    assert any(row.get('difficulty') == 5 for row in lib['rhythm']), \
        'rhythms_data must carry difficulty so the counter can narrow by it'


def test_module_exercises_table_renders_multiple_time_signatures():
    """The exercises table's Filters column must render a list-valued
    time_signature (D25) as a plain joined list. Unfixed, Jinja prints the
    bare Python list through autoescape as "[&#39;3/4&#39;, &#39;2/4&#39;]"
    — '3/4' and '2/4' are individually still substrings of that, so this
    checks for the joined form itself rather than for their mere presence."""
    w = world()
    make_module_exercise(w['module'], 'melody', {'time_signature': ['3/4', '2/4']})
    resp = client_as(w['at']).get(f'/admin/modules/{w["module"]}/exercises')
    assert resp.status_code == 200
    body = resp.data.decode()
    assert '3/4, 2/4' in body, \
        'expected both signatures joined and readable, not a raw list repr'


# ── Extraction: the editor's URLs come from url_for, not a hardcoded path ───

def test_module_exercises_table_duplicate_and_remove_actions_use_real_ids():
    """The per-row Duplicate/Remove forms are built from the URL templates
    the include receives (me_id=0) with '0' swapped for the row's real id —
    confirm that substitution actually lands on the right, working URL."""
    w = world()
    me_id = make_module_exercise(w['module'], 'melody', {})
    resp = client_as(w['at']).get(f'/admin/modules/{w["module"]}/exercises')
    assert resp.status_code == 200
    body = resp.data.decode()
    assert f'action="/admin/module_exercises/{me_id}/duplicate"' in body
    assert f'action="/admin/module_exercises/{me_id}/delete"' in body


def test_module_exercises_page_has_no_hardcoded_edit_path():
    w = world()
    resp = client_as(w['at']).get(f'/admin/modules/{w["module"]}/exercises')
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "'/admin/module_exercises/'" not in body, \
        'the edit-URL must come from url_for, not a hardcoded path literal'


def test_module_exercises_editor_script_loads_after_bootstrap():
    """The editor's own <script> must render after base.html's Bootstrap
    bundle (base.html's {% block scripts %}), exactly as it did before the
    editor was extracted into an include. openEditModal() only calls
    `new bootstrap.Modal(...)` on click, so nothing breaks *today* if the
    script loads first — but that's a load-order change the task required
    stay identical, and Task 5 reusing this editor on a second page is one
    load-time Bootstrap call away from a silent breakage if it regresses."""
    w = world()
    resp = client_as(w['at']).get(f'/admin/modules/{w["module"]}/exercises')
    assert resp.status_code == 200
    body = resp.data.decode()
    bootstrap_idx = body.index('bootstrap.bundle.min.js')
    script_idx = body.index('EDIT_URL_TEMPLATE')
    assert script_idx > bootstrap_idx, \
        'the editor script must render after the Bootstrap bundle <script>, not before it'
