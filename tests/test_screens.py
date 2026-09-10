"""The screen registry must stay in sync with the app.

These tests exist so screens.py cannot silently drift: adding a route without
naming it, or naming two screens the same, fails here rather than showing up as
UNKNOWN in the debug panel weeks later.
"""
import pytest

from app import app
import screens


# Endpoints that legitimately have no screen name.
EXEMPT = {'static'}


def _app_endpoints():
    return {r.endpoint for r in app.url_map.iter_rules()} - EXEMPT


def test_every_endpoint_has_a_screen_name():
    missing = sorted(_app_endpoints() - set(screens.SCREENS))
    assert not missing, (
        'These endpoints have no entry in screens.py: ' + ', '.join(missing)
    )


def test_no_stale_registry_entries():
    stale = sorted(set(screens.SCREENS) - _app_endpoints())
    assert not stale, (
        'screens.py names endpoints that no longer exist: ' + ', '.join(stale)
    )


def test_screen_names_are_unique():
    names = screens.all_names()
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert not dupes, 'Duplicate screen names: ' + ', '.join(dupes)


def test_screen_names_are_upper_snake_case():
    bad = [n for n in screens.all_names()
           if not n.replace('_', '').isalnum() or n != n.upper()]
    assert not bad, 'Names must be UPPER_SNAKE_CASE: ' + ', '.join(bad)


def test_access_levels_are_known():
    bad = [s['name'] for s in screens.SCREENS.values()
           if s['access'] not in screens.ACCESS_LEVELS]
    assert not bad, 'Unknown access level on: ' + ', '.join(bad)


def test_kinds_are_known():
    bad = [s['name'] for s in screens.SCREENS.values()
           if s['kind'] not in ('page', 'redirect', 'action')]
    assert not bad, 'Unknown kind on: ' + ', '.join(bad)


def test_every_mapped_template_exists():
    import os
    root = os.path.join(os.path.dirname(__file__), '..', 'templates')
    missing = [t for t in screens.TEMPLATES.values()
               if not os.path.exists(os.path.join(root, t))]
    assert not missing, 'Templates named in screens.py but not on disk: ' + \
                        ', '.join(missing)


def test_drawio_map_names_match_the_registry():
    """Every name drawn on the screen map must exist in screens.py.

    This is what makes "redraw SECTION_MODULE_DETAIL" unambiguous: rename a box in
    the .drawio without renaming it here (or vice versa) and this fails.
    Names containing '*' are deliberate wildcards for boxes that stand in for a
    family of screens, e.g. the shared confirm-delete page.
    """
    import os
    import re
    import xml.etree.ElementTree as ET

    path = os.path.join(os.path.dirname(__file__), '..', 'docs', 'SCREEN_MAP.drawio')
    if not os.path.exists(path):
        pytest.skip('screen map not present')

    root = ET.parse(path).getroot()
    drawn = set()
    for cell in root.iter('mxCell'):
        if not cell.get('vertex'):
            continue
        value = (cell.get('value') or '').replace('&lt;', '<').replace('&gt;', '>')
        m = re.search(r"face='monospace'>([A-Z0-9_*]+)<", value)
        if m:
            drawn.add(m.group(1))

    assert drawn, 'No screen names found in the .drawio — did the label format change?'

    registry = set(screens.all_names())
    unknown = sorted(n for n in drawn - registry if '*' not in n)
    assert not unknown, (
        'Names drawn on SCREEN_MAP.drawio with no entry in screens.py: '
        + ', '.join(unknown)
    )


def test_every_page_screen_is_drawn_on_the_map():
    """Pages and redirects get a box; POST actions live on edges instead."""
    import os
    import re
    import xml.etree.ElementTree as ET

    path = os.path.join(os.path.dirname(__file__), '..', 'docs', 'SCREEN_MAP.drawio')
    if not os.path.exists(path):
        pytest.skip('screen map not present')

    root = ET.parse(path).getroot()
    blob = ' '.join((c.get('value') or '') for c in root.iter('mxCell'))
    blob = blob.replace('&lt;', '<').replace('&gt;', '>')

    # Boxes that intentionally stand in for a family of screens.
    COVERED_BY_WILDCARD = {
        'ADMIN_MELODY_DELETE', 'ADMIN_RHYTHM_DELETE', 'ADMIN_HARMONIC_DELETE',
        'ADMIN_HOLISTIC_DELETE', 'ADMIN_GENPROG_DELETE',
    }
    # Debug tooling is not part of the product surface.
    EXCLUDED_GROUPS = {'Debug'}

    missing = []
    for screen in screens.SCREENS.values():
        if screen['kind'] == 'action' or screen['group'] in EXCLUDED_GROUPS:
            continue
        if screen['name'] in COVERED_BY_WILDCARD:
            continue
        if not re.search(r'\b' + screen['name'] + r'\b', blob):
            missing.append(screen['name'])

    assert not missing, (
        'These screens have no box on SCREEN_MAP.drawio: ' + ', '.join(sorted(missing))
    )


def test_screen_for_handles_unknown_endpoint():
    s = screens.screen_for('no_such_endpoint')
    assert s['name'] == 'UNKNOWN'
    s = screens.screen_for(None)
    assert s['name'] == 'NO_ENDPOINT'


def test_template_for_reverse_lookup():
    assert screens.template_for('SECTION_MODULE_DETAIL') == 'student/module_detail.html'
    assert screens.template_for('NOT_A_SCREEN') is None


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_debug_panel_renders_for_anonymous(client):
    resp = client.get('/debug/panel')
    assert resp.status_code == 200
    assert b'DEBUG_PANEL' in resp.data


def test_debug_state_reports_anonymous(client):
    resp = client.get('/debug/state?endpoint=home')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['authenticated'] is False
    assert data['role'] is None


def test_screen_meta_is_injected_into_pages(client):
    resp = client.get('/sandbox')
    assert resp.status_code == 200
    assert b'id="screen-meta"' in resp.data
    assert b'SANDBOX_HOME' in resp.data


# ── Authenticated viewer state ───────────────────────────────────────────────

@pytest.fixture
def ctx():
    from models import db
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def _login_as(role):
    """Create a user with the given role and return a logged-in test client."""
    from models import db, User
    u = User(email=f'{role}@test.com', password_hash='x', role=role)
    db.session.add(u)
    db.session.commit()
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(u.id)
        sess['_fresh'] = True
    return c, u


def test_state_reports_role_for_logged_in_user(ctx):
    c, u = _login_as('student')
    data = c.get('/debug/state?endpoint=home').get_json()
    assert data['authenticated'] is True
    assert data['role'] == 'student'
    assert data['identity'] == 'student@test.com'


def test_state_warns_student_off_a_site_admin_screen(ctx):
    c, _ = _login_as('student')
    data = c.get('/debug/state?endpoint=admin_users').get_json()
    assert 'site-admin only' in data['verdict']
    assert '403' in data['verdict']


def test_state_warns_class_teacher_off_a_school_admin_screen(ctx):
    c, _ = _login_as('class_teacher')
    data = c.get('/debug/state?endpoint=teacher_new_section').get_json()
    assert 'admin_teacher' in data['verdict']


def test_state_clears_site_admin_everywhere(ctx):
    c, _ = _login_as('admin')
    data = c.get('/debug/state?endpoint=admin_users').get_json()
    assert 'every screen' in data['verdict']


def test_state_reports_class_membership_context(ctx):
    from models import db, Section
    c, u = _login_as('student')
    other = Section(name='Theory I', join_code='ABC123', teacher_id=999)
    other.members.append(u)
    db.session.add(other)
    db.session.commit()

    data = c.get(f'/debug/state?endpoint=section_home&section_id={other.id}').get_json()
    assert data['section_context']['is_member'] is True
    assert data['section_context']['is_owner_teacher'] is False
    assert data['verdict'].startswith('Your role (student) satisfies')


def test_state_flags_non_member_on_a_class_screen(ctx):
    from models import db, Section
    c, _ = _login_as('student')
    other = Section(name='Not Mine', join_code='XYZ789', teacher_id=999)
    db.session.add(other)
    db.session.commit()

    data = c.get(f'/debug/state?endpoint=section_home&section_id={other.id}').get_json()
    assert data['section_context']['is_member'] is False
    assert '403' in data['verdict']
