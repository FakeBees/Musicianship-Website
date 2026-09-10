"""Templates must only read variables their route actually passes.

Jinja's default Undefined renders as an empty string and is falsy, so a template
that reads `classes` while its route passes `sections` fails *silently*: the list
just appears empty and the `{% else %}` branch renders "none yet". That shipped
three separate times during the class -> section rename — on the teacher
dashboard, the course-sections page and the my-sections page — and no test
caught any of them, because every page still returned 200.

These tests re-render the real pages with StrictUndefined, which turns that
silent emptiness into a loud error.
"""
import pytest
from jinja2 import StrictUndefined

from app import app
from models import (db, User, School, SchoolMembership, Course, Module,
                    ModuleExercise, Section)


@pytest.fixture
def strict_undefined():
    """Make any unprovided template variable raise instead of rendering ''."""
    original = app.jinja_env.undefined
    app.jinja_env.undefined = StrictUndefined
    yield
    app.jinja_env.undefined = original


@pytest.fixture
def world():
    """A small but complete world: school, course, module, a section, and a user
    at each role with a real relationship to it.

    The app context is opened only for setup and teardown, never held across the
    test body. Flask reuses an already-pushed app context instead of creating a
    fresh one per request, and Flask-Login caches the resolved user on ``g`` —
    so a fixture that keeps a context open makes every request after the first
    silently reuse the first request's user. Yielding plain ids avoids that.
    """
    with app.app_context():
        db.create_all()

        admin = User(email='admin@t.com', password_hash='x', role='admin')
        at    = User(email='at@t.com',    password_hash='x', role='admin_teacher')
        ct    = User(email='ct@t.com',    password_hash='x', role='class_teacher')
        stu   = User(email='stu@t.com',   password_hash='x', role='student')
        db.session.add_all([admin, at, ct, stu])
        db.session.commit()

        school = School(name='Test School', join_code='SCHOOL1')
        db.session.add(school)
        db.session.commit()
        for u, r in ((at, 'admin_teacher'), (ct, 'class_teacher'), (stu, 'student')):
            db.session.add(SchoolMembership(school_id=school.id, user_id=u.id, role=r))

        course = Course(name='Theory I', school_id=school.id)
        db.session.add(course)
        db.session.commit()

        module = Module(name='Module 1', course_id=course.id, order=0)
        db.session.add(module)
        db.session.commit()
        db.session.add(ModuleExercise(module_id=module.id, exercise_type='melody',
                                      exercise_id=1, name='Ex 1', order=0))

        sec = Section(name='Theory I – 001', join_code='SEC001',
                      teacher_id=at.id, assigned_teacher_id=ct.id,
                      course_id=course.id)
        sec.members.append(stu)
        db.session.add(sec)
        db.session.commit()

        ids = {'admin': admin.id, 'at': at.id, 'ct': ct.id, 'stu': stu.id,
               'school': school.id, 'course': course.id, 'module': module.id,
               'section': sec.id}
        db.session.remove()

    # Context deliberately closed here — see the docstring.
    yield ids

    with app.app_context():
        db.session.remove()
        db.drop_all()


def client_as(uid):
    app.config['TESTING'] = True
    c = app.test_client()
    with c.session_transaction() as s:
        s['_user_id'] = str(uid)
        s['_fresh'] = True
    return c


def pages_for(w):
    """(label, url, [roles that should get 200])."""
    s, c, m, sec = w['school'], w['course'], w['module'], w['section']
    return [
        ('home',             '/',                              ['admin', 'at', 'ct', 'stu']),
        ('my sections',      '/my-sections',                   ['admin', 'at', 'ct', 'stu']),
        ('my progress',      '/me',                            ['admin', 'at', 'ct', 'stu']),
        ('teacher dash',     '/teacher',                       ['admin', 'at', 'ct']),
        ('section detail',   f'/teacher/section/{sec}',        ['admin', 'at', 'ct']),
        ('section edit',     f'/teacher/section/{sec}/edit',   ['admin', 'at', 'ct']),
        ('section delete',   f'/teacher/sections/{sec}/delete', ['admin', 'at']),
        ('new section',      '/teacher/section/new',           ['admin', 'at']),
        ('school detail',    f'/admin/schools/{s}/detail',     ['admin', 'at', 'ct']),
        ('courses',          f'/admin/schools/{s}/courses',    ['admin', 'at']),
        ('course sections',  f'/admin/courses/{c}/sections',   ['admin', 'at']),
        ('modules',          f'/admin/courses/{c}/modules',    ['admin', 'at']),
        ('module exercises', f'/admin/modules/{m}/exercises',  ['admin', 'at']),
        ('section home',     f'/section/{sec}',                ['stu']),
        ('section modules',  f'/section/{sec}/modules',        ['stu']),
        ('admin dash',       '/admin',                         ['admin']),
        ('admin users',      '/admin/users',                   ['admin']),
        ('admin schools',    '/admin/schools',                 ['admin']),
    ]


def test_no_page_reads_an_undefined_variable(world, strict_undefined):
    failures = []
    for label, url, roles in pages_for(world):
        for role in roles:
            resp = client_as(world[role]).get(url)
            if resp.status_code != 200:
                failures.append(f'{label} as {role}: HTTP {resp.status_code} ({url})')
    assert not failures, 'Pages failed to render:\n  ' + '\n  '.join(failures)


def test_lists_actually_render_their_rows(world):
    """The specific symptom of the silent-undefined bug: a populated list that
    renders its empty state anyway."""
    name = 'Theory I – 001'
    checks = [
        ('teacher dashboard', 'at',  '/teacher',                               'No sections yet'),
        ('course sections',   'at',  f"/admin/courses/{world['course']}/sections",
         'use this course'),
        ('my sections',       'stu', '/my-sections',                           'not enrolled in any'),
    ]
    for label, role, url, empty_marker in checks:
        body = client_as(world[role]).get(url).get_data(as_text=True)
        assert name in body, f'{label}: section missing from the page'
        assert empty_marker not in body, f'{label}: showed its empty state despite having rows'
