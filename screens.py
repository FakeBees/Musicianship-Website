"""Canonical screen registry.

Every Flask endpoint in ``app.py`` has exactly one entry here, keyed by its endpoint
name (the view function's name). The ``name`` field is the **stable identifier** for
that screen and is shared with ``docs/SCREEN_MAP.drawio`` — every box in that diagram
carries its name in red monospace at the top.

The point of the shared name: when a screen gets redrawn or redesigned, the name is
what identifies it unambiguously. "Change SECTION_MODULE_DETAIL" is precise in a way
that "change the module page" is not.

Rules
-----
* Names are UPPER_SNAKE_CASE, unique, and stable. Renaming one means updating the
  .drawio file in the same commit.
* ``kind`` is one of:
    ``page``     — renders a template a user actually looks at
    ``redirect`` — 302s somewhere else, renders nothing
    ``action``   — POST endpoint, no page of its own
* ``access`` is the *minimum* level required, matching the legend colours in the
  .drawio map. Route-level conditions beyond the role gate (section membership, school
  membership, record ownership) are spelled out in ``condition``.

``tests/test_screens.py`` fails if an endpoint exists in the app without an entry
here, so this file cannot silently drift out of date.
"""

# ── Access levels, in ascending order of privilege ───────────────────────────
ACCESS_LEVELS = {
    'anon': {
        'label': 'Anonymous',
        'description': 'No login required — anyone with the URL.',
        'colour': '#999999',
    },
    'auth': {
        'label': 'Any logged-in user',
        'description': 'Requires a session; any role will do.',
        'colour': '#6c8ebf',
    },
    'section_member': {
        'label': 'Section member',
        'description': 'Member of the section, its owning teacher, or a site admin.',
        'colour': '#82b366',
    },
    'teacher': {
        'label': 'Teacher of the section',
        'description': "role in ('class_teacher', 'admin_teacher', 'admin'), plus an "
                       'ownership check on the specific section.',
        'colour': '#d79b00',
    },
    'school_admin': {
        'label': 'School admin',
        'description': "role in ('admin_teacher', 'admin'). admin_teacher must hold an "
                       'admin_teacher SchoolMembership for that school.',
        'colour': '#9673a6',
    },
    'site_admin': {
        'label': 'Site admin',
        'description': "role == 'admin' only.",
        'colour': '#b85450',
    },
}

ACCESS_ORDER = ['anon', 'auth', 'section_member', 'teacher', 'school_admin', 'site_admin']


def _s(name, access, group, kind='page', condition=None):
    return {'name': name, 'access': access, 'group': group,
            'kind': kind, 'condition': condition}


# ── The registry ─────────────────────────────────────────────────────────────
SCREENS = {
    # ---- Entry & authentication --------------------------------------------
    'home':            _s('HOME',          'auth', 'Entry'),
    'sandbox':         _s('SANDBOX_HOME',  'anon', 'Entry',
                          condition='Same template as HOME, but with no section list.'),
    'login':           _s('LOGIN',         'anon', 'Entry'),
    'register':        _s('REGISTER',      'anon', 'Entry'),
    'logout':          _s('LOGOUT',        'auth', 'Entry', kind='redirect'),
    'set_perspective': _s('PERSPECTIVE_SET', 'auth', 'Entry', kind='redirect',
                          condition='Switch the viewing perspective. Never role-gated, '
                                    'so you can always get back out. Refuses any role '
                                    'above the account\'s real role (403).'),

    # ---- Melodic dictation --------------------------------------------------
    'melodic_index':   _s('MELODIC_LIBRARY', 'anon', 'Melodic'),
    'random_melody':   _s('MELODIC_RANDOM',  'anon', 'Melodic', kind='redirect'),
    'exercise':        _s('MELODIC_DRILL',   'anon', 'Melodic'),
    'submit':          _s('MELODIC_SUBMIT',  'auth', 'Melodic', kind='action'),
    'results':         _s('MELODIC_RESULTS', 'auth', 'Melodic',
                          condition='Attempt owner, a teacher of one of their sections, '
                                    'or admin. Otherwise 403.'),

    # ---- Rhythmic dictation -------------------------------------------------
    'rhythm_index':    _s('RHYTHM_LIBRARY', 'anon', 'Rhythmic'),
    'random_rhythm':   _s('RHYTHM_RANDOM',  'anon', 'Rhythmic', kind='redirect'),
    'rhythm_exercise': _s('RHYTHM_DRILL',   'anon', 'Rhythmic'),
    'rhythm_submit':   _s('RHYTHM_SUBMIT',  'auth', 'Rhythmic', kind='action'),
    'rhythm_results':  _s('RHYTHM_RESULTS', 'auth', 'Rhythmic',
                          condition='Attempt owner, their teacher, or admin.'),

    # ---- Harmonic dictation -------------------------------------------------
    'harmonic_index':    _s('HARMONIC_LIBRARY', 'anon', 'Harmonic'),
    'random_harmonic':   _s('HARMONIC_RANDOM',  'anon', 'Harmonic', kind='redirect'),
    'harmonic_exercise': _s('HARMONIC_DRILL',   'anon', 'Harmonic'),
    'harmonic_submit':   _s('HARMONIC_SUBMIT',  'auth', 'Harmonic', kind='action'),
    'harmonic_results':  _s('HARMONIC_RESULTS', 'auth', 'Harmonic',
                            condition='Attempt owner, their teacher, or admin.'),

    # ---- Holistic dictation -------------------------------------------------
    'holistic_index':    _s('HOLISTIC_LIBRARY', 'anon', 'Holistic'),
    'holistic_exercise': _s('HOLISTIC_DRILL',   'anon', 'Holistic'),
    'holistic_submit':   _s('HOLISTIC_SUBMIT',  'auth', 'Holistic', kind='action'),
    'holistic_results':  _s('HOLISTIC_RESULTS', 'auth', 'Holistic',
                            condition='Attempt owner, their teacher, or admin.'),

    # ---- Student ------------------------------------------------------------
    'my_sections':           _s('MY_SECTIONS',           'auth', 'Student'),
    'me':                   _s('MY_PROGRESS',          'auth', 'Student'),
    'section_home':           _s('SECTION_HOME',           'section_member', 'Student',
                               condition='Member, section owner-teacher, or admin.'),
    'section_modules':        _s('SECTION_MODULE_LIST',    'section_member', 'Student',
                               condition='Member/owner/admin, and the section must have a '
                                         'course assigned.'),
    'section_module_detail':  _s('SECTION_MODULE_DETAIL',  'section_member', 'Student',
                               condition='Member/owner/admin. Hidden modules are excluded '
                                         'per-section via SectionModuleExercise.'),
    'start_module_exercise': _s('MODULE_EXERCISE_START', 'section_member', 'Student',
                                kind='redirect',
                                condition='302s into the matching drill carrying module '
                                          'context in the session.'),
    'join_section':           _s('SECTION_JOIN',           'auth', 'Student', kind='action'),
    'join_school':          _s('SCHOOL_JOIN',          'auth', 'Student', kind='action'),
    'leave_section':          _s('SECTION_LEAVE',          'auth', 'Student', kind='action'),

    # ---- Teacher ------------------------------------------------------------
    'teacher_dashboard':    _s('TEACHER_DASHBOARD',    'teacher', 'Teacher'),
    'teacher_new_section':    _s('TEACHER_SECTION_NEW',    'school_admin', 'Teacher',
                               condition='admin_teacher | admin only — a class_teacher '
                                         'cannot create sections.'),
    'teacher_section_detail': _s('TEACHER_SECTION_DETAIL', 'teacher', 'Teacher',
                               condition='Section authority: an in-section Section '
                                         'Teacher (assigned_teacher_id == me) or owner '
                                         '(teacher_id == me), or a School Admin of the '
                                         "section's school (or site admin)."),
    'teacher_edit_section':   _s('TEACHER_SECTION_EDIT',   'teacher', 'Teacher',
                               condition='Same section authority as TEACHER_SECTION_DETAIL: '
                                         'in-section Section Teacher or owner, or a School '
                                         "Admin of the section's school. D14: only a "
                                         "manager (owner or School Admin) may change the "
                                         'course; a non-manager gets it read-only.'),
    'teacher_delete_section': _s('TEACHER_SECTION_DELETE', 'school_admin', 'Teacher',
                               condition='admin_teacher | admin only. Owner (teacher_id '
                                         '== me) or a School Admin of the section\'s '
                                         'school — the assigned Section Teacher alone '
                                         'does not qualify.'),
    'teacher_kick_student': _s('TEACHER_STUDENT_KICK', 'teacher', 'Teacher'),
    'teacher_set_course':   _s('TEACHER_SECTION_SET_COURSE', 'school_admin', 'Teacher',
                               kind='action'),
    'teacher_assign_section_teacher': _s('TEACHER_SECTION_ASSIGN_TEACHER', 'school_admin',
                                       'Teacher', kind='action'),
    'teacher_add_override':    _s('TEACHER_OVERRIDE_ADD',    'teacher', 'Teacher',
                                  kind='action'),
    'teacher_delete_override': _s('TEACHER_OVERRIDE_DELETE', 'teacher', 'Teacher',
                                  kind='action'),
    'teacher_hide_module':     _s('TEACHER_MODULE_HIDE',     'teacher', 'Teacher',
                                  kind='action',
                                  condition='Task 5: also 404s unless the module belongs to '
                                            "this section's current course and is either "
                                            'course content or this section\'s own '
                                            '(Task 4 review Minor finding — this used to be '
                                            'unchecked). Returns to TEACHER_SECTION_CURRICULUM.'),
    'teacher_restore_module':  _s('TEACHER_MODULE_RESTORE',  'teacher', 'Teacher',
                                  kind='action',
                                  condition='Same ownership check and return page as '
                                            'TEACHER_MODULE_HIDE.'),
    'teacher_section_curriculum': _s('TEACHER_SECTION_CURRICULUM', 'teacher', 'Teacher'),
    'teacher_section_curriculum_module': _s('TEACHER_SECTION_CURRICULUM_MODULE', 'teacher',
                                            'Teacher',
                                            condition='Module must belong to this section\'s '
                                                      'current course and be either course '
                                                      "content or this section's own — "
                                                      'otherwise 404.'),
    'teacher_delete_curriculum_module': _s('TEACHER_CURRICULUM_MODULE_DELETE', 'teacher',
                                           'Teacher', kind='action',
                                           condition='Only this section\'s own module — '
                                                     '404 for shared course content.'),
    'teacher_edit_curriculum_exercise': _s('TEACHER_CURRICULUM_EXERCISE_EDIT', 'teacher',
                                           'Teacher', kind='action',
                                           condition='Only this section\'s own exercise — '
                                                     '404 otherwise.'),
    'teacher_duplicate_curriculum_exercise': _s('TEACHER_CURRICULUM_EXERCISE_DUPLICATE',
                                                'teacher', 'Teacher', kind='action',
                                                condition='Only this section\'s own exercise '
                                                          '— 404 otherwise.'),
    'teacher_remove_curriculum_exercise': _s('TEACHER_CURRICULUM_EXERCISE_REMOVE', 'teacher',
                                             'Teacher', kind='action',
                                             condition='Only this section\'s own exercise — '
                                                       '404 otherwise.'),

    # ---- School admin -------------------------------------------------------
    'admin_my_school':       _s('SCHOOL_ADMIN_ENTRY', 'teacher', 'School admin',
                                kind='redirect',
                                condition='Actual gate is class_teacher | admin_teacher | '
                                          'admin — corrected from school_admin, which '
                                          "excluded the class_teacher this route serves. "
                                          'No longer BUG-003 (fixed): lands any staff '
                                          'member on their own SCHOOL_DETAIL, preferring '
                                          'an admin_teacher membership and falling back to '
                                          'a class_teacher one. A site admin with no '
                                          'membership goes to ADMIN_SCHOOLS instead; staff '
                                          'with no membership anywhere gets a flash and '
                                          'HOME.'),
    'admin_school_detail':   _s('SCHOOL_DETAIL',      'teacher', 'School admin',
                                condition='admin_teacher must hold an admin_teacher '
                                          'SchoolMembership for THIS school.'),
    'admin_set_member_role': _s('SCHOOL_MEMBER_SET_ROLE', 'school_admin', 'School admin',
                                kind='action'),
    'admin_regen_join_code': _s('SCHOOL_REGEN_JOIN_CODE', 'school_admin', 'School admin',
                                kind='action'),
    'admin_course_sections':  _s('COURSE_SECTIONS',     'school_admin', 'School admin'),
    'admin_rename_course':   _s('COURSE_RENAME',      'school_admin', 'School admin',
                                kind='action'),
    'admin_duplicate_course': _s('COURSE_DUPLICATE',  'school_admin', 'School admin',
                                 kind='action'),

    # ---- Site admin: organisation & curriculum ------------------------------
    'admin':                 _s('ADMIN_DASHBOARD',    'site_admin', 'Site admin'),
    'admin_users':           _s('ADMIN_USERS',        'site_admin', 'Site admin'),
    'admin_delete_user':     _s('ADMIN_USER_DELETE',  'site_admin', 'Site admin',
                                condition='Three-step confirm (GET ?step=1|2|3); POST only '
                                          'deletes when step=3. Cascades: owned sections, '
                                          'completions, attempts (all 4 modes), memberships. '
                                          'Cannot delete your own account, at any step.'),
    'admin_schools':         _s('ADMIN_SCHOOLS',      'site_admin', 'Site admin'),
    'admin_delete_school':   _s('ADMIN_SCHOOL_DELETE', 'site_admin', 'Site admin',
                                condition='Three-step confirm (GET ?step=1|2|3); POST only '
                                          'deletes when step=3. Cascades: courses, sections, '
                                          'progress. Members keep their accounts; roles are '
                                          'recalculated.'),
    'admin_add_school_member': _s('SCHOOL_ADD_MEMBER', 'school_admin', 'School admin',
                                  kind='action',
                                  condition='Can only grant a role strictly below your '
                                            'own, so only a site admin seats an '
                                            'admin_teacher.'),
    'admin_set_school_admin': _s('SCHOOL_SET_ADMIN', 'site_admin', 'School admin',
                                 kind='action',
                                 condition='Appoint an administrative teacher by email. '
                                           'Granting admin_teacher needs a role above it, '
                                           'so this is site-admin only.'),
    'admin_remove_school_member': _s('SCHOOL_REMOVE_MEMBER', 'teacher', 'School admin',
                                     kind='action',
                                     condition='Anyone above student may remove a member '
                                               'whose school role is strictly below '
                                               'their own.'),
    'admin_courses':         _s('ADMIN_COURSES',      'school_admin', 'Site admin'),
    'admin_delete_course':   _s('ADMIN_COURSE_DELETE', 'school_admin', 'Site admin',
                                condition='Three-step confirm (GET ?step=1|2|3); POST only '
                                          'deletes when step=3. Cascades: sections following '
                                          'the course and their progress.'),
    'admin_modules':         _s('ADMIN_MODULES',      'school_admin', 'Site admin'),
    'admin_delete_module':   _s('ADMIN_MODULE_DELETE', 'school_admin', 'Site admin',
                                kind='action'),
    'admin_module_exercises': _s('ADMIN_MODULE_EXERCISES', 'school_admin', 'Site admin'),
    'admin_edit_module_exercise':   _s('ADMIN_MODULE_EXERCISE_EDIT',      'school_admin',
                                       'Site admin', kind='action'),
    'admin_delete_module_exercise': _s('ADMIN_MODULE_EXERCISE_DELETE',    'school_admin',
                                       'Site admin', kind='action'),
    'admin_duplicate_module_exercise': _s('ADMIN_MODULE_EXERCISE_DUPLICATE', 'school_admin',
                                          'Site admin', kind='action'),

    # ---- Site admin: content CMS -------------------------------------------
    'admin_melodies':        _s('ADMIN_MELODY_LIST',   'site_admin', 'Melody CMS'),
    'admin_edit_melody':     _s('ADMIN_MELODY_EDIT',   'site_admin', 'Melody CMS'),
    'admin_delete_melody':   _s('ADMIN_MELODY_DELETE', 'site_admin', 'Melody CMS'),
    'admin_melody_upload':   _s('ADMIN_MELODY_UPLOAD', 'site_admin', 'Melody CMS'),
    'admin_melody_generator': _s('ADMIN_MELODY_GENERATOR', 'site_admin', 'Melody CMS'),
    'admin_melody_approve':  _s('ADMIN_MELODY_APPROVE', 'site_admin', 'Melody CMS',
                                kind='action'),
    'admin_melody_reject':   _s('ADMIN_MELODY_REJECT',  'site_admin', 'Melody CMS',
                                kind='action'),

    'admin_rhythms':         _s('ADMIN_RHYTHM_LIST',   'site_admin', 'Rhythm CMS'),
    'admin_edit_rhythm':     _s('ADMIN_RHYTHM_EDIT',   'site_admin', 'Rhythm CMS'),
    'admin_delete_rhythm':   _s('ADMIN_RHYTHM_DELETE', 'site_admin', 'Rhythm CMS'),
    'admin_rhythm_upload':   _s('ADMIN_RHYTHM_UPLOAD', 'site_admin', 'Rhythm CMS'),

    'admin_harmonics':       _s('ADMIN_HARMONIC_LIST',   'site_admin', 'Harmonic CMS'),
    'admin_edit_harmonic':   _s('ADMIN_HARMONIC_EDIT',   'site_admin', 'Harmonic CMS'),
    'admin_delete_harmonic': _s('ADMIN_HARMONIC_DELETE', 'site_admin', 'Harmonic CMS'),
    'admin_harmonic_upload': _s('ADMIN_HARMONIC_UPLOAD', 'site_admin', 'Harmonic CMS'),

    'admin_holistic':        _s('ADMIN_HOLISTIC_LIST',   'site_admin', 'Holistic CMS'),
    'admin_edit_holistic':   _s('ADMIN_HOLISTIC_EDIT',   'site_admin', 'Holistic CMS',
                                condition='Includes the drag-reorder Lines builder.'),
    'admin_delete_holistic': _s('ADMIN_HOLISTIC_DELETE', 'site_admin', 'Holistic CMS'),
    'admin_holistic_upload': _s('ADMIN_HOLISTIC_UPLOAD', 'site_admin', 'Holistic CMS'),
    'admin_add_holistic_line':     _s('ADMIN_HOLISTIC_LINE_ADD',     'site_admin',
                                      'Holistic CMS', kind='action'),
    'admin_reorder_holistic_lines': _s('ADMIN_HOLISTIC_LINE_REORDER', 'site_admin',
                                       'Holistic CMS', kind='action'),
    'admin_delete_holistic_line':  _s('ADMIN_HOLISTIC_LINE_DELETE',  'site_admin',
                                      'Holistic CMS', kind='action'),

    'admin_gen_progressions':     _s('ADMIN_GENPROG_LIST',   'site_admin', 'GenProg CMS'),
    'admin_edit_gen_progression': _s('ADMIN_GENPROG_EDIT',   'site_admin', 'GenProg CMS'),
    'admin_delete_gen_progression': _s('ADMIN_GENPROG_DELETE', 'site_admin', 'GenProg CMS'),

    # ---- Debug --------------------------------------------------------------
    'debug_panel': _s('DEBUG_PANEL', 'anon', 'Debug',
                      condition='Reports only the current viewer\'s own state.'),
    'debug_state': _s('DEBUG_STATE', 'anon', 'Debug', kind='action'),
}


# ── Which template each page renders ─────────────────────────────────────────
# Kept separate from SCREENS so the registry above stays readable. This is the
# lookup that matters when a screen gets redrawn: name -> file to edit.
TEMPLATES = {
    'home': 'home.html',
    'sandbox': 'home.html',
    'login': 'auth/login.html',
    'register': 'auth/register.html',

    'melodic_index': 'index.html',
    'exercise': 'exercise.html',
    'results': 'results.html',

    'rhythm_index': 'rhythm_index.html',
    'rhythm_exercise': 'rhythm_exercise.html',
    'rhythm_results': 'rhythm_results.html',

    'harmonic_index': 'harmonic_index.html',
    'harmonic_exercise': 'harmonic_exercise.html',
    'harmonic_results': 'harmonic_results.html',

    'holistic_index': 'holistic_index.html',
    'holistic_exercise': 'holistic_exercise.html',
    'holistic_results': 'holistic_results.html',

    'my_sections': 'student/my_sections.html',
    'me': 'me.html',
    'section_home': 'student/mode_select.html',
    'section_modules': 'student/module_list.html',
    'section_module_detail': 'student/module_detail.html',

    'teacher_dashboard': 'teacher/dashboard.html',
    'teacher_new_section': 'teacher/new_section.html',
    'teacher_section_detail': 'teacher/section_detail.html',
    'teacher_edit_section': 'teacher/edit_section.html',
    'teacher_delete_section': 'teacher/confirm_delete_section.html',
    'teacher_kick_student': 'teacher/confirm_kick_student.html',
    'teacher_section_curriculum': 'teacher/section_curriculum.html',
    'teacher_section_curriculum_module': 'teacher/section_curriculum_module.html',

    'admin_school_detail': 'admin/school_detail.html',
    'admin_course_sections': 'admin/course_sections.html',

    'admin': 'admin/index.html',
    'admin_users': 'admin/users.html',
    'admin_delete_user': 'admin/confirm_delete_cascade.html',
    'admin_schools': 'admin/schools.html',
    'admin_delete_school': 'admin/confirm_delete_cascade.html',
    'admin_courses': 'admin/courses.html',
    'admin_delete_course': 'admin/confirm_delete_cascade.html',
    'admin_modules': 'admin/modules.html',
    'admin_module_exercises': 'admin/module_exercises.html',

    'admin_melodies': 'admin/melodies.html',
    'admin_edit_melody': 'admin/melody_edit.html',
    'admin_delete_melody': 'admin/confirm_delete.html',
    'admin_melody_upload': 'admin/melody_upload.html',
    'admin_melody_generator': 'admin/melody_generator.html',

    'admin_rhythms': 'admin/rhythms.html',
    'admin_edit_rhythm': 'admin/rhythm_edit.html',
    'admin_delete_rhythm': 'admin/confirm_delete.html',
    'admin_rhythm_upload': 'admin/rhythm_upload.html',

    'admin_harmonics': 'admin/harmonics.html',
    'admin_edit_harmonic': 'admin/harmonic_edit.html',
    'admin_delete_harmonic': 'admin/confirm_delete.html',
    'admin_harmonic_upload': 'admin/harmonic_upload.html',

    'admin_holistic': 'admin/holistic_list.html',
    'admin_edit_holistic': 'admin/holistic_edit.html',
    'admin_delete_holistic': 'admin/confirm_delete.html',
    'admin_holistic_upload': 'admin/holistic_upload.html',

    'admin_gen_progressions': 'admin/gen_progressions.html',
    'admin_edit_gen_progression': 'admin/gen_progression_edit.html',
    'admin_delete_gen_progression': 'admin/confirm_delete.html',

    'debug_panel': 'debug_panel.html',
}


UNKNOWN_SCREEN = {
    'name': 'UNKNOWN', 'access': 'anon', 'group': 'Unregistered',
    'kind': 'page',
    'condition': 'This endpoint has no entry in screens.py. Add one so it shows up '
                 'on the screen map.',
}


def screen_for(endpoint):
    """Return the registry entry for a Flask endpoint name, or UNKNOWN_SCREEN.

    The returned dict always carries ``endpoint`` and ``template`` keys; a
    ``template`` of None means the endpoint renders no page of its own.
    """
    if not endpoint:
        return dict(UNKNOWN_SCREEN, name='NO_ENDPOINT', endpoint=None, template=None)
    entry = SCREENS.get(endpoint, UNKNOWN_SCREEN)
    return dict(entry, endpoint=endpoint, template=TEMPLATES.get(endpoint))


def template_for(name):
    """Reverse lookup: screen NAME -> template path. Returns None if unmapped."""
    for endpoint, screen in SCREENS.items():
        if screen['name'] == name:
            return TEMPLATES.get(endpoint)
    return None


def access_info(access_key):
    """Return the {label, description, colour} block for an access level."""
    return ACCESS_LEVELS.get(access_key, ACCESS_LEVELS['anon'])


def all_names():
    """Every screen name, for uniqueness checks and doc generation."""
    return [s['name'] for s in SCREENS.values()]
