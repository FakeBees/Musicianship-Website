"""The student assignment flow keeps its module context end to end, and a
Section Teacher's home screen lists the sections they teach.

The class->section rename left the exercise pages reading `class_id` and the
submit JS posting `class_id`/`cme_id`, while the server reads and emits
`section_id`/`sme_id`. Nothing tested that seam, so completion tracking, the
Back button and the next-exercise filters silently fell back to sandbox.
"""
import json
import re
from pathlib import Path

import pytest

from app import app
from models import (db, User, School, SchoolMembership, Course, Module,
                    ModuleExercise, ModuleCompletion, Section, Rhythm)

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def ctx():
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def client_as(uid):
    app.config['TESTING'] = True
    c = app.test_client()
    with c.session_transaction() as s:
        s['_user_id'] = str(uid)
        s['_fresh'] = True
    return c


def world(ts_filter='3/4'):
    s = School(name='Flow', join_code='FLOW01')
    db.session.add(s)
    at = User(email='at@flow.com', password_hash='x', role='admin_teacher')
    st = User(email='st@flow.com', password_hash='x', role='class_teacher')
    stu = User(email='stu@flow.com', password_hash='x', role='student')
    db.session.add_all([at, st, stu])
    db.session.commit()
    for u, r in ((at, 'admin_teacher'), (st, 'class_teacher'), (stu, 'student')):
        db.session.add(SchoolMembership(school_id=s.id, user_id=u.id, role=r))
    crs = Course(name='C1', school_id=s.id)
    db.session.add(crs)
    db.session.commit()
    mod = Module(name='M1', course_id=crs.id, order=0)
    db.session.add(mod)
    db.session.commit()
    sec = Section(name='Sec 1', join_code='FLOW02', teacher_id=at.id,
                  assigned_teacher_id=st.id, course_id=crs.id)
    sec.members.append(stu)
    db.session.add(sec)
    db.session.add_all([
        Rhythm(name='r34', notes_json='[]', min_duration='q', time_signature='3/4', difficulty=1),
        Rhythm(name='r44', notes_json='[]', min_duration='q', time_signature='4/4', difficulty=1),
    ])
    me = ModuleExercise(module_id=mod.id, exercise_type='rhythm', exercise_id=0,
                        name='Rhythms', order=0,
                        params_json=json.dumps({'time_signature': ts_filter}),
                        completion_criterion_json='{"attempts":2}')
    db.session.add(me)
    db.session.commit()
    return dict(at=at.id, st=st.id, stu=stu.id, sec=sec.id, me=me.id, mod=mod.id)


def test_class_teacher_home_lists_their_sections_not_sandbox():
    w = world()
    html = client_as(w['st']).get('/').get_data(as_text=True)
    assert 'Sec 1' in html
    assert 'Rhythmic Dictation' not in html


def test_exercise_page_back_link_and_js_carry_section_context():
    w = world()
    c = client_as(w['stu'])
    resp = c.get(f"/section/{w['sec']}/module_exercise/{w['me']}/start")
    assert resp.status_code == 302
    page = c.get(resp.headers['Location']).get_data(as_text=True)
    assert 'Back to Module' in page
    assert f'const MODULE_SECTION_ID = "{w["sec"]}"' in page


def test_submit_scripts_post_section_keys_the_server_reads():
    for js in ('notation.js', 'rhythm_notation.js', 'harmonic.js', 'holistic.js'):
        src = (ROOT / 'static/js' / js).read_text()
        assert 'section_id: MODULE_SECTION_ID' in src, js
        assert 'sme_id: MODULE_SME_ID' in src, js
        assert 'class_id' not in src and 'cme_id' not in src, js


def test_rhythm_submit_within_assignment_records_progress_and_stays_in_filter():
    w = world()
    c = client_as(w['stu'])
    r34 = Rhythm.query.filter_by(name='r34').first()
    resp = c.post(f'/rhythm/submit/{r34.id}', json={
        'notes': [], 'section_id': str(w['sec']), 'me_id': str(w['me']), 'sme_id': ''})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    loc = resp.get_json()['redirect']
    assert f'section_id={w["sec"]}' in loc
    page = c.get(loc).get_data(as_text=True)
    # the next-exercise link stays inside the assignment, not the sandbox
    assert f'/section/{w["sec"]}/module_exercise/{w["me"]}/start' in page
    assert '/rhythm/random' not in page
    assert ModuleCompletion.query.filter_by(user_id=w['stu']).count() == 1
