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
import re

import pytest
from flask import url_for
from jinja2 import StrictUndefined

from app import app
from models import (db, User, School, SchoolMembership, Course, Module,
                    ModuleExercise, Section, ChordProgression, Tag,
                    Melody, Rhythm, HolisticExercise, GenProgression)


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

        # A second course that no section is attached to. `sec` above is
        # attached to `course`, so the admin course-modules page ("{{
        # course.name }} — Modules") and the student's per-section module
        # list ("{{ section.course.name }} — Modules") would otherwise
        # render as the exact same row's name — not two seeded rows
        # coincidentally sharing a name, but literally one row viewed two
        # ways. See _pages_for_uniqueness in the titles-sweep tests below.
        course2 = Course(name='Theory II', school_id=school.id)
        db.session.add(course2)
        db.session.commit()

        # A second school where a class_teacher-elsewhere holds only a plain
        # student membership — trivial to acquire via /join-school. The
        # unrelated membership is committed BEFORE the class_teacher one
        # below so an unordered `.first()` query would surface this row
        # first, reproducing the row-order-dependent bug in
        # admin_my_school()'s fallback (see test_school_authority.py naming
        # convention: 'ct2' mirrors 'ct').
        other_school = School(name='Other School', join_code='OTHER01')
        db.session.add(other_school)
        db.session.commit()

        ct2 = User(email='ct2@t.com', password_hash='x', role='class_teacher')
        db.session.add(ct2)
        db.session.commit()

        db.session.add(SchoolMembership(school_id=other_school.id, user_id=ct2.id,
                                         role='student'))
        db.session.commit()
        db.session.add(SchoolMembership(school_id=school.id, user_id=ct2.id,
                                         role='class_teacher'))
        db.session.commit()

        ids = {'admin': admin.id, 'at': at.id, 'ct': ct.id, 'stu': stu.id,
               'school': school.id, 'course': course.id, 'module': module.id,
               'section': sec.id, 'course2': course2.id,
               'ct2': ct2.id, 'other_school': other_school.id}
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


def test_admin_melodies_supports_difficulty_filter(world, strict_undefined):
    """Melodies must filter by difficulty like every other content type.

    It was the only list page without this, despite rendering a Diff column.
    """
    resp = client_as(world['admin']).get('/admin/melodies?difficulty=3')
    assert resp.status_code == 200
    assert b'name="difficulty"' in resp.data, \
        'melodies.html must render a difficulty filter control'


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


def test_class_teacher_has_a_reachable_school_link(world, strict_undefined):
    """A class_teacher may view school detail, so the nav must offer a way in.

    The permission existed with no path to it: /admin/schools/<id>/detail
    allows class_teacher, but base.html gave the role no entry at all (D6).
    """
    resp = client_as(world['ct']).get('/')
    assert resp.status_code == 200
    assert b'/admin/my-school' in resp.data, \
        'class_teacher nav must link to the school entry point'


def test_class_teacher_my_school_does_not_403(world, strict_undefined):
    resp = client_as(world['ct']).get('/admin/my-school', follow_redirects=True)
    assert resp.status_code == 200


def test_my_school_lands_on_the_school_actually_taught_not_a_membership_elsewhere(
        world, strict_undefined):
    """A class_teacher who ALSO holds a plain student membership in some other
    school (trivial via /join-school) must land on the school they actually
    teach in, not wherever an unordered, unfiltered fallback happens to land.

    Regression for the "Manage School" link dead-ending in a 403 for exactly
    the class_teachers it was added to serve: the old fallback accepted ANY
    membership with no role filter and no ordering, so it could just as
    easily surface the unrelated student membership first — landing on a
    school where require_school_role() correctly denies them.
    """
    resp = client_as(world['ct2']).get('/admin/my-school')
    assert resp.status_code == 302
    assert resp.headers['Location'] == f"/admin/schools/{world['school']}/detail", \
        ('must redirect to the school actually taught '
         f"({world['school']}), not the unrelated one ({world['other_school']})")

    resp2 = client_as(world['ct2']).get(resp.headers['Location'])
    assert resp2.status_code == 200, \
        'the destination must not deny the class_teacher who was routed there'


def test_my_sections_links_each_section(world, strict_undefined):
    """A student's own section list must let them open a section.

    The only affordance per row was a destructive Leave button — the section
    name was plain text even though /section/<id>/modules exists and the
    viewer is a member (D10).
    """
    resp = client_as(world['stu']).get('/my-sections')
    assert resp.status_code == 200
    body = resp.data.decode()
    modules_url = f"/section/{world['section']}/modules"
    assert modules_url in body, \
        'section row must link to its module list, not just offer Leave'
    assert 'Leave' in body, 'the existing Leave affordance must stay'


def test_teacher_dashboard_links_each_section(world, strict_undefined):
    """A teacher's dashboard card title must itself link to the section detail
    page, not rely solely on the footer's View roster button.

    The footer's "View roster" link already points at teacher_section_detail,
    so merely asserting that URL is present would pass today without the
    title being clickable at all. The title link is a second, distinct
    occurrence of the same href, so require at least two. Matching the full
    `href="..."` attribute (not just the URL substring) avoids a false match
    against the footer's Edit button, whose href is this same URL plus
    "/edit" — the identical substring-collision trap the Leave button poses
    for the my-sections test above.
    """
    resp = client_as(world['at']).get('/teacher')
    assert resp.status_code == 200
    assert b'teacher_section_detail' not in resp.data  # url_for is resolved
    detail_href = f'href="/teacher/section/{world["section"]}"'
    occurrences = resp.data.count(detail_href.encode())
    assert occurrences >= 2, \
        ('card title must also link to section detail (found the exact '
         f'href {occurrences} time(s); the footer\'s "View roster" link '
         'alone only accounts for one)')


MODULE_EXERCISE_FIELDS = [
    'name', 'order', 'criterion_type', 'completion_attempts',
    'completion_min_score', 'completion_passing',
    'time_signature_cb', 'time_signature', 'category', 'tag',
    'difficulty', 'key_signature', 'clef_cb', 'min_dur_cb',
]


def test_module_exercise_add_and_edit_expose_the_same_fields(world, strict_undefined):
    """The add form and the edit modal must accept the same fields.

    They had complementary gaps: clef_cb and min_dur_cb could be set at
    creation but never had a control to change them after, because the edit
    modal never rendered them at all.

    A raw whole-page occurrence count can't catch this: several fields
    render inside more than one type-specific branch of the add form alone
    (e.g. min_dur_cb appears once for melody and once for rhythm), so a
    >=2 whole-page threshold is already satisfied without the edit modal
    containing the field at all. This locates the add-form and edit-modal
    regions separately and requires each field's name attribute in both.

    A ChordProgression carrying a Tag is seeded so `category` and `tag`
    (both sourced from existing harmonic progressions) actually render in
    either region instead of both legitimately showing zero for lack of
    data.
    """
    with app.app_context():
        tag = Tag(name='probe-tag')
        db.session.add(ChordProgression(name='Probe Progression',
                                         midi_filename='probe.mid',
                                         category='diatonic',
                                         chords_json='[]',
                                         tags=[tag]))
        db.session.commit()
        db.session.remove()

    resp = client_as(world['admin']).get(f'/admin/modules/{world["module"]}/exercises')
    assert resp.status_code == 200
    body = resp.data.decode()

    edit_form_start = body.index('id="edit-form"')
    edit_form_end = body.index('Save Changes', edit_form_start) + len('Save Changes')
    add_region  = body[:edit_form_start]
    edit_region = body[edit_form_start:edit_form_end]

    failures = []
    for field in MODULE_EXERCISE_FIELDS:
        needle = f'name="{field}"'
        if needle not in add_region:
            failures.append(f'{field!r} missing from the add form')
        if needle not in edit_region:
            failures.append(f'{field!r} missing from the edit modal')
    assert not failures, 'Add/edit field parity broken:\n  ' + '\n  '.join(failures)


def _page_script(body):
    """The page's own inline <script> — the longest one, since base.html's
    other script tags carry src attributes or a line or two of glue."""
    scripts = re.findall(r'<script>(.*?)</script>', body, re.S)
    assert scripts, 'module_exercises.html renders no inline script'
    return max(scripts, key=len)


def test_add_form_cannot_leak_a_time_signature_across_exercise_types(world, strict_undefined):
    """A time signature picked under one type must not ride along into another.

    The whole add form posts as one request, so a 4/4 checked while the type
    was Melodic used to end up in a *Harmonic* exercise's params_json: the
    sync helper read the checkboxes regardless of type, ran again on submit,
    and nothing cleared them when the type changed. The harmonic query then
    filtered on a column its progressions do not meaningfully carry.

    This is a source contract, not a behavioural test: the leak lives in
    client-side JS and this suite has no JS runtime, so it asserts the two
    structural guarantees that make the leak impossible rather than driving
    the form. Both were verified behaviourally out-of-band, by executing this
    exact rendered script against this exact rendered markup in node (red
    before the fix, green after) — see the task report.
    """
    resp = client_as(world['admin']).get(f'/admin/modules/{world["module"]}/exercises')
    assert resp.status_code == 200
    script = _page_script(resp.data.decode())

    # 1. Changing type wipes every add-form filter control, so nothing chosen
    #    under the previous type survives into the next one's params_json.
    type_switcher = script[script.index('function onTypeChange()'):]
    type_switcher = type_switcher[:type_switcher.index('\n}')]
    assert 'clearAddFilters()' in type_switcher, \
        'onTypeChange must clear the add form\'s filters when the type changes'
    clearer = script[script.index('function clearAddFilters()'):]
    clearer = clearer[:clearer.index('\n}')]
    assert "'add-time-sig-hidden').value = ''" in clearer, \
        'clearAddFilters must blank the time_signature hidden field'
    assert "input[type=\"checkbox\"]" in clearer and 'cb.checked  = false' in clearer, \
        'clearAddFilters must uncheck the add form\'s filter checkboxes'

    # 2. Belt and braces: the submit-time sync refuses to post a time
    #    signature at all while its row is hidden — which is exactly when the
    #    selected type has no time signature (harmonic, holistic, none yet).
    sync = script[script.index('function syncTimeSigHidden(mode)'):]
    sync = sync[:sync.index('\n}')]
    assert "classList.contains('d-none')" in sync and "hidden.value = ''" in sync, \
        ('syncTimeSigHidden must post nothing while the time-signature row is '
         'hidden; reading the checkboxes regardless of type is the leak')


# ── D10: every admin list entity the viewer can reach must be clickable ─────

ADMIN_LIST_LINKS = [
    ('/admin/schools',          'admin_school_detail',        'school_id', 'school'),
    ('/admin/melodies',         'admin_edit_melody',          'mel_id',    'melody'),
    ('/admin/rhythms',          'admin_edit_rhythm',          'rhythm_id', 'rhythm'),
    ('/admin/harmonics',        'admin_edit_harmonic',        'prog_id',   'progression'),
    ('/admin/holistic',         'admin_edit_holistic',        'ex_id',     'holistic'),
    ('/admin/gen-progressions', 'admin_edit_gen_progression', 'gp_id',     'gen_progression'),
]


@pytest.mark.parametrize('path,endpoint,kwarg,content_key', ADMIN_LIST_LINKS,
                         ids=[c[3] for c in ADMIN_LIST_LINKS])
def test_admin_lists_link_their_entities(world, strict_undefined, path, endpoint,
                                         kwarg, content_key):
    """Every listed entity the viewer can reach must be clickable (D10).

    Each of these rows already carries an Edit/Details action button whose
    href is this exact same endpoint, so a bare "href is present" assertion
    would pass before the name itself is linked at all — the same
    substring-collision trap test_teacher_dashboard_links_each_section
    guards against. Require a second, distinct occurrence of the same href.
    """
    with app.app_context():
        melody   = Melody(name='Probe Melody', midi_filename='probe.mid', notes_json='[]')
        rhythm   = Rhythm(name='Probe Rhythm', notes_json='[]')
        prog     = ChordProgression(name='Probe Progression', midi_filename='probe.mid',
                                    chords_json='[]')
        holistic = HolisticExercise(name='Probe Holistic', folder='holistic/probe/')
        gp       = GenProgression(number=9001, chords_json='[]')
        db.session.add_all([melody, rhythm, prog, holistic, gp])
        db.session.commit()
        content_ids = {
            'school':          world['school'],
            'melody':          melody.id,
            'rhythm':          rhythm.id,
            'progression':     prog.id,
            'holistic':        holistic.id,
            'gen_progression': gp.id,
        }
        db.session.remove()

    resp = client_as(world['admin']).get(path)
    assert resp.status_code == 200
    with app.test_request_context():
        expected_href = f'href="{url_for(endpoint, **{kwarg: content_ids[content_key]})}"'
    occurrences = resp.data.count(expected_href.encode())
    assert occurrences >= 2, (
        f'{path}: name cell must also link to {endpoint} (found the exact '
        f'href {occurrences} time(s); the existing action button alone '
        'only accounts for one)')


def test_admin_courses_links_each_course(world, strict_undefined):
    """A course's name in the admin course list must link to its modules.

    The Modules column's own "Manage" button already points at admin_modules,
    so a bare presence check would pass today without the name being
    clickable — require a second, distinct occurrence of the same href.
    """
    resp = client_as(world['admin']).get(f"/admin/schools/{world['school']}/courses")
    assert resp.status_code == 200
    with app.test_request_context():
        modules_href = f'href="{url_for("admin_modules", course_id=world["course"])}"'
    occurrences = resp.data.count(modules_href.encode())
    assert occurrences >= 2, (
        'course name must also link to admin_modules (found the exact href '
        f'{occurrences} time(s); the Modules column\'s "Manage" button alone '
        'only accounts for one)')


def test_admin_modules_links_each_module(world, strict_undefined):
    """A module's name in the admin module list must link to its exercises.

    The row's own "Exercises →" button already points at
    admin_module_exercises, so a bare presence check would pass today
    without the name being clickable — require a second, distinct
    occurrence of the same href.
    """
    resp = client_as(world['admin']).get(f"/admin/courses/{world['course']}/modules")
    assert resp.status_code == 200
    with app.test_request_context():
        exercises_href = f'href="{url_for("admin_module_exercises", module_id=world["module"])}"'
    occurrences = resp.data.count(exercises_href.encode())
    assert occurrences >= 2, (
        'module name must also link to admin_module_exercises (found the '
        f'exact href {occurrences} time(s); the "Exercises →" button alone '
        'only accounts for one)')


def test_admin_course_sections_links_each_section(world, strict_undefined):
    """A section's name in the admin course-sections list must link to its
    teacher detail page, and the join code must stay outside that anchor.

    Unlike the other eight templates in this sweep, this row currently has
    no link at all, so a plain presence check is sufficient here — there is
    no pre-existing occurrence of this href to collide with.
    """
    resp = client_as(world['admin']).get(f"/admin/courses/{world['course']}/sections")
    assert resp.status_code == 200
    body = resp.data.decode()
    with app.test_request_context():
        detail_href = f'href="{url_for("teacher_section_detail", section_id=world["section"])}"'
    assert detail_href in body, 'section name must link to its teacher detail page'

    anchor_start = body.index(detail_href)
    anchor_open_end = body.index('>', anchor_start) + 1
    anchor_close = body.index('</a>', anchor_open_end)
    anchor_inner = body[anchor_open_end:anchor_close]
    assert '<code' not in anchor_inner, \
        'join code must stay outside the name anchor, per the brief'
    assert 'SEC001' in body, 'join code must still render on the page'


# ── Titles sweep: every page says clearly what it is (D22) ──────────────────
#
# The nav item "Sections I Teach" used to open a page titled "My Sections",
# and the different nav item "My Sections" opened another page also titled
# "My Sections". These five tests enforce, everywhere:
#   1. A menu item opens a page with the same name.
#   2. No two different pages share a main heading, or a browser-tab title.
#   3. A page's heading says what the page is.

def _collapse(html_fragment):
    """Strip tags and collapse whitespace."""
    return ' '.join(re.sub(r'<[^>]+>', '', html_fragment).split())


def main_heading(body):
    """The first <h1> or <h2> in the page body, outside the <nav> element
    (so the navbar brand — "Musicianship Trainer" on every page — is never
    picked up as the page's own heading), tags stripped and whitespace
    collapsed. None if the page has neither: e.g. the delete-section confirm
    dialog heads itself with an <h5> instead — out of scope here, see the
    task report's "also found".
    """
    nav_end = body.index('</nav>')
    m = re.search(r'<(h1|h2)\b[^>]*>(.*?)</\1>', body[nav_end:], re.S)
    return _collapse(m.group(2)) if m else None


def tab_title(body):
    """The <title> contents, tags stripped and whitespace collapsed."""
    m = re.search(r'<title>(.*?)</title>', body, re.S)
    assert m is not None, 'page has no <title>'
    return _collapse(m.group(1))


def _endpoint_for(url):
    """Resolve a path (query string ignored) to its Flask endpoint name."""
    adapter = app.url_map.bind('localhost')
    endpoint, _args = adapter.match(url.split('?', 1)[0], method='GET')
    return endpoint


def _pages_for_uniqueness(w):
    """pages_for(w), plus the sandbox and melody-upload pages it doesn't
    cover, with the admin course-modules entry repointed at a second course
    (world['course2']) that no section uses.

    Without this, the admin course-modules page ("{{ course.name }} —
    Modules") and the student's per-section module list ("{{
    section.course.name }} — Modules") render the identical heading and tab
    title for two different endpoints once both are fixed per the brief —
    not because two rows happen to share a name, but because world's only
    Section IS on world['course'], so they're the same row rendered two
    ways. Comparing the admin page against a differently-named course
    instead follows the brief's "give them distinct names" guidance,
    without touching the shared pages_for() that
    test_no_page_reads_an_undefined_variable and
    test_lists_actually_render_their_rows also depend on.
    """
    pages = [p for p in pages_for(w) if p[0] != 'modules']
    pages.append(('modules', f"/admin/courses/{w['course2']}/modules", ['admin', 'at']))
    pages += [
        ('sandbox',       '/sandbox',                ['admin']),
        ('melody upload', '/admin/melodies/upload',  ['admin']),
    ]
    return pages


def test_no_two_pages_share_a_heading(world):
    seen = {}  # heading, lowercased -> (endpoint, label)
    failures = []
    for label, url, roles in _pages_for_uniqueness(world):
        resp = client_as(world[roles[0]]).get(url)
        assert resp.status_code == 200, f'{label}: HTTP {resp.status_code} ({url})'
        heading = main_heading(resp.data.decode())
        if heading is None:
            continue
        endpoint = _endpoint_for(url)
        key = heading.lower()
        prior = seen.get(key)
        if prior and prior[0] != endpoint:
            failures.append(
                f'{heading!r} shared by {prior[1]!r} ({prior[0]}) and {label!r} ({endpoint})')
        seen[key] = (endpoint, label)
    assert not failures, 'Shared main headings:\n  ' + '\n  '.join(failures)


def test_no_two_pages_share_a_tab_title(world):
    seen = {}  # title, lowercased -> (endpoint, label)
    failures = []
    for label, url, roles in _pages_for_uniqueness(world):
        resp = client_as(world[roles[0]]).get(url)
        assert resp.status_code == 200, f'{label}: HTTP {resp.status_code} ({url})'
        title = tab_title(resp.data.decode())
        endpoint = _endpoint_for(url)
        key = title.lower()
        prior = seen.get(key)
        if prior and prior[0] != endpoint:
            failures.append(
                f'{title!r} shared by {prior[1]!r} ({prior[0]}) and {label!r} ({endpoint})')
        seen[key] = (endpoint, label)
    assert not failures, 'Shared tab titles:\n  ' + '\n  '.join(failures)


ACCOUNT_MENU_TEST_ROLES = ['ct', 'at', 'admin']  # Section Teacher, School Admin, Site Admin


def _account_menu_items(body):
    """(label, href) pairs from the account-menu dropdown, in document
    order. The "View as" perspective links carry extra classes
    (`dropdown-item d-flex ...`), so matching the exact class
    `"dropdown-item"` already excludes them without filtering by label.
    """
    start = body.index('dropdown-menu-end')
    end = body.index('</ul>', start)
    menu = body[start:end]
    items = re.findall(r'<a class="dropdown-item" href="([^"]+)">([^<]*)</a>', menu)
    return [(label.strip(), href) for href, label in items]


def test_menu_items_open_a_page_with_the_same_name(world):
    skip_labels = {'home', 'log out'}
    failures = []
    for role in ACCOUNT_MENU_TEST_ROLES:
        c = client_as(world[role])
        resp = c.get('/')
        assert resp.status_code == 200
        items = _account_menu_items(resp.data.decode())
        remaining = [label for label, _ in items if label.lower() not in skip_labels]
        assert remaining, f'{role}: no account-menu items found to check'
        for label, href in items:
            if label.lower() in skip_labels:
                continue
            page = c.get(href, follow_redirects=True)
            assert page.status_code == 200, \
                f'{role}: {label!r} ({href}) -> HTTP {page.status_code}'
            heading = main_heading(page.data.decode())
            if not heading or label.lower() not in heading.lower():
                failures.append(
                    f'{role}: menu item {label!r} ({href}) opens a page headed {heading!r}')
    assert not failures, 'Menu items open mismatched pages:\n  ' + '\n  '.join(failures)


def _dashboard_manage_cards(body):
    """(label, href) for every /admin dashboard card whose own block
    contains a "Manage ->" link — skips the Users and
    {{ section_terms_title }} cards (no link at all) and the Schools card's
    second "Users ->" link, by matching within each card's own block only.
    """
    cards = re.findall(r'<div class="card text-center p-3">(.*?)</div>\s*</div>',
                        body, re.S)
    result = []
    for card in cards:
        label_m = re.search(r'<div class="text-muted">([^<]*)</div>', card)
        link_m = re.search(r'<a href="([^"]+)"[^>]*>\s*Manage\s*→\s*</a>', card)
        if label_m and link_m:
            result.append((label_m.group(1).strip(), link_m.group(1)))
    return result


def test_dashboard_cards_match_the_pages_they_open(world):
    c = client_as(world['admin'])
    resp = c.get('/admin')
    assert resp.status_code == 200
    cards = _dashboard_manage_cards(resp.data.decode())
    assert cards, 'no dashboard cards with a Manage → link found'
    failures = []
    for label, href in cards:
        page = c.get(href)
        assert page.status_code == 200, f'{label}: HTTP {page.status_code} ({href})'
        heading = main_heading(page.data.decode()) or ''
        heading = re.sub(r'\s*\(\d+\)\s*$', '', heading)
        if heading.lower() != label.lower():
            failures.append(f'card {label!r} ({href}) opens a page headed {heading!r}')
    assert not failures, 'Dashboard cards mismatched:\n  ' + '\n  '.join(failures)


def test_melody_upload_page_says_it_uploads_melodies(world):
    resp = client_as(world['admin']).get('/admin/melodies/upload')
    assert resp.status_code == 200
    heading = main_heading(resp.data.decode())
    assert heading and 'melody' in heading.lower(), \
        f'melody upload page heading was {heading!r}'
