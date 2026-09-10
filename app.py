import json
import os
import random
import secrets
import string as _string
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from models import db, Melody, Tag, UserAttempt, Rhythm, RhythmAttempt, \
                   ChordProgression, HarmonicAttempt, HolisticExercise, HolisticAttempt, HolisticLine, \
                   GenProgression, Container, \
                   User, Section, School, Course, Module, ModuleExercise, \
                   SectionModuleExercise, ModuleCompletion, SchoolMembership
from chord_utils import grade_harmonic_attempt, format_chord_name
import curriculum as cur
import screens

_ALPHA = _string.ascii_uppercase + _string.digits

def _random_school_code():
    return ''.join(secrets.choice(_ALPHA) for _ in range(8))

app = Flask(__name__)

# ── Database ─────────────────────────────────────────────────────────────────
# The exercise database is bundled directly in the repository (instance/musicianship.db).
# No external database service is needed.
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///musicianship.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ── Secret key ───────────────────────────────────────────────────────────────
# In production set the SECRET_KEY environment variable to a long random string.
# Locally it falls back to the dev placeholder (sessions are not sensitive here).
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

db.init_app(app)

from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
from flask import abort

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# Permission perspectives ("view as")
#
# A user may drop into any role at or below their own to see the site the way
# that role sees it. The perspective is stored in the session and genuinely
# restricts: role_required() and every ownership check consult the effective
# role, not User.role.
#
# Two invariants make this safe:
#   1. active_role() is always min(session perspective, real role) — a
#      perspective can only ever REDUCE privileges, never grant them. A tampered
#      session value above the user's real role is ignored, not honoured.
#   2. The perspective switcher itself is never role-gated, so you can always
#      get back out.
#
# Roles are per-section, so there is a second, narrower rule for a specific
# section — see effective_section_role().
# ---------------------------------------------------------------------------

ROLE_ORDER = ['student', 'class_teacher', 'admin_teacher', 'admin']

ROLE_LABELS = {
    'student':       'Student',
    'class_teacher': 'Section Teacher',
    'admin_teacher': 'School Admin',
    'admin':         'Site Admin',
}


def role_rank(role):
    """Position in the privilege hierarchy; -1 for anything unrecognised."""
    try:
        return ROLE_ORDER.index(role)
    except ValueError:
        return -1


def real_role():
    """The role stored on the account, ignoring any active perspective."""
    return current_user.role if current_user.is_authenticated else None


def active_role():
    """The role currently in force. Never exceeds the account's real role."""
    if not current_user.is_authenticated:
        return None
    chosen = session.get('perspective')
    if not chosen or chosen not in ROLE_ORDER:
        return current_user.role
    # Invariant 1: cap at the real role. Never trust the session upward.
    if role_rank(chosen) > role_rank(current_user.role):
        return current_user.role
    return chosen


def in_perspective():
    """True when viewing as something other than your own role."""
    return current_user.is_authenticated and active_role() != current_user.role


def available_perspectives():
    """Every role this account may view as — its own and everything below."""
    if not current_user.is_authenticated:
        return []
    return [r for r in ROLE_ORDER if role_rank(r) <= role_rank(current_user.role)]


def section_role(section, user=None):
    """The role a user actually holds *within* one section, or None.

    Deliberately does not special-case site admins: global authority is not a
    relationship with a particular section, and the perspective screens list
    only sections the account genuinely belongs to.
    """
    u = user or current_user
    if not u.is_authenticated:
        return None
    if section.teacher_id == u.id:
        return 'admin_teacher'
    if section.assigned_teacher_id == u.id:
        return 'class_teacher'
    if u in section.members:
        return 'student'
    return None


def effective_section_role(section):
    """Role held in this section, capped by the active perspective.

    This is the rule for the per-section conflict: you get the highest role you
    genuinely hold here that does not exceed the perspective you selected.
    """
    actual = section_role(section)
    if actual is None:
        return None
    perspective = active_role()
    if role_rank(actual) > role_rank(perspective):
        return perspective
    return actual


def section_access(section):
    """Effective role within one section, including site-admin blanket authority.

    Returns None when the account has no claim on this section at the active
    perspective.
    """
    role = effective_section_role(section)
    if role is None and active_role() == 'admin':
        return 'admin'
    return role


def require_section_role(section, minimum):
    """403 unless the effective role in `section` is at least `minimum`.

    Roles are inclusive: holding admin_teacher over a section also grants
    class_teacher and student access to it. That is what makes a lowered
    perspective useful — a section owner viewing as a student gets the student
    view of their OWN section rather than being locked out of it.
    """
    role = section_access(section)
    if role is None or role_rank(role) < role_rank(minimum):
        abort(403)



def find_user_by_email(email):
    """Look up an account by email, case- and whitespace-insensitively.

    People type addresses with stray capitals and spaces; every email-driven
    form goes through here so they all behave the same. Deliberately not
    ``ilike``, which would treat ``_`` and ``%`` in an address as wildcards.
    """
    from sqlalchemy import func
    cleaned = (email or '').strip()
    if not cleaned:
        return None
    return User.query.filter(func.lower(User.email) == cleaned.lower()).first()


def school_role(school_id, user=None):
    """A user's SchoolMembership role for one school, or None if not a member.

    Deliberately ignores site-admin authority — that is global, not a membership.
    Use effective_school_role() for authorization.
    """
    u = user or current_user
    if not getattr(u, 'is_authenticated', False):
        return None
    mem = SchoolMembership.query.filter_by(school_id=school_id, user_id=u.id).first()
    return mem.role if mem else None


def effective_school_role(school_id):
    """The caller's authority over one school: their membership role, plus
    site-admin blanket authority, capped by the active perspective."""
    if active_role() == 'admin':
        return 'admin'
    role = school_role(school_id)
    if role is None:
        return None
    if role_rank(role) > role_rank(active_role()):
        return active_role()
    return role


def require_school_role(school_id, minimum):
    """403 unless the caller's authority over `school_id` is at least `minimum`.

    This is the school-level twin of require_section_role(). Every route that
    touches a school's courses, modules or membership goes through it — without
    it, `@role_required('admin_teacher')` alone lets any school's admin_teacher
    edit every other school's courses.
    """
    role = effective_school_role(school_id)
    if role is None or role_rank(role) < role_rank(minimum):
        abort(403)


def section_school_id(section):
    """The school a section belongs to, derived through its course.

    Sections are attached to a school only via Course, so a section with no
    course assigned has no school — and only its owner has authority over it.
    """
    return section.course.school_id if section.course else None


def can_manage_section(section):
    """True if the caller may administer this section: either they hold
    admin_teacher over it directly (they own it), or they are a school admin of
    the school it belongs to."""
    if role_rank(section_access(section) or '') >= role_rank('admin_teacher'):
        return True
    sid = section_school_id(section)
    return sid is not None and \
        role_rank(effective_school_role(sid) or '') >= role_rank('admin_teacher')


def require_manage_section(section):
    if not can_manage_section(section):
        abort(403)


def outranks_in_school(school_id, target_user):
    """True if the caller may act on `target_user` within this school.

    The rule: you may add, re-role or remove anyone whose school role is
    strictly below your own. Students outrank nobody, so they can never act on
    anyone; and nobody can confer or revoke a role at or above their own — which
    is what keeps 'only a site admin creates an admin_teacher' true.
    """
    mine = effective_school_role(school_id)
    if mine is None:
        return False
    theirs = school_role(school_id, target_user)
    if theirs is None:
        return False
    return role_rank(mine) > role_rank(theirs)


def grantable_school_roles(school_id):
    """School roles the caller may hand out here — strictly below their own."""
    mine = effective_school_role(school_id)
    if mine is None:
        return []
    return [r for r in ('student', 'class_teacher', 'admin_teacher')
            if role_rank(r) < role_rank(mine)]


def administered_schools():
    """Schools the caller is an admin_teacher of (all schools for site admins)."""
    if active_role() == 'admin':
        return School.query.order_by(School.name).all()
    mems = SchoolMembership.query.filter_by(
        user_id=current_user.id, role='admin_teacher').all()
    ids = [m.school_id for m in mems]
    if not ids:
        return []
    return School.query.filter(School.id.in_(ids)).order_by(School.name).all()


def administered_courses():
    """Courses in schools the caller administers."""
    school_ids = [s.id for s in administered_schools()]
    if not school_ids:
        return []
    return (Course.query.filter(Course.school_id.in_(school_ids))
            .order_by(Course.name).all())


def related_sections(user=None):
    """Sections the account has a real relationship with: owns, is assigned to,
    or is enrolled in. Site admins get no blanket expansion here."""
    u = user or current_user
    if not u.is_authenticated:
        return []
    from sqlalchemy import or_
    return (Section.query
            .filter(or_(Section.teacher_id == u.id,
                        Section.assigned_teacher_id == u.id,
                        Section.members.any(User.id == u.id)))
            .order_by(Section.name)
            .all())


@app.context_processor
def inject_perspective():
    if not current_user.is_authenticated:
        return {'active_role': None, 'in_perspective': False,
                'available_perspectives': [], 'role_labels': ROLE_LABELS}
    return {
        'active_role': active_role(),
        'real_role': current_user.role,
        'in_perspective': in_perspective(),
        'available_perspectives': available_perspectives(),
        'role_labels': ROLE_LABELS,
    }


@app.route('/perspective/<role>')
@login_required
def set_perspective(role):
    """Switch the viewing perspective. Selecting your own role exits."""
    if role not in ROLE_ORDER:
        abort(404)
    # Invariant 1 again, at the entry point: refuse to store an elevated role.
    if role_rank(role) > role_rank(current_user.role):
        abort(403)
    if role == current_user.role:
        session.pop('perspective', None)
        flash('Back to your own view.', 'info')
    else:
        session['perspective'] = role
        flash(f'Now viewing as {ROLE_LABELS[role]}. '
              f'You will only see what that role can reach.', 'info')
    return redirect(url_for('home'))


# ---------------------------------------------------------------------------
# Audience-dependent wording
#
# One concept, two names in the UI: staff read "section", students read
# "classroom". Code, routes and templates always say "section" — only the words
# on screen change. See docs/NAMING.md.
# ---------------------------------------------------------------------------

def section_word(plural=False, title=False):
    """The word for a Section, from the current viewer's point of view."""
    is_student = current_user.is_authenticated and active_role() == 'student'
    word = 'classroom' if is_student else 'section'
    if plural:
        word += 's'
    return word.capitalize() if title else word


@app.context_processor
def inject_section_words():
    return {
        'section_term':       section_word(),
        'section_terms':      section_word(plural=True),
        'section_term_title': section_word(title=True),
        'section_terms_title': section_word(plural=True, title=True),
    }


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated or active_role() not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


# ---------------------------------------------------------------------------
# Module-completion helper
# ---------------------------------------------------------------------------

def _handle_module_completion(section_id, me_id, sme_id, score, keep_practicing=False):
    """
    Called after a drill submission when the student came from a module.
    Records the attempt, checks criterion, returns nav context dict or None.
    """
    if not section_id:
        return None
    try:
        section_id_int = int(section_id)
        section = Section.query.get(section_id_int)
        if not section:
            return None
    except (ValueError, TypeError):
        return None

    if section_access(section) is None:
        return None

    me_id_int  = int(me_id)  if me_id  else None
    sme_id_int = int(sme_id) if sme_id else None

    me = ModuleExercise.query.get(me_id_int) if me_id_int else None
    criterion = me.completion_criterion if me else {'attempts': 1}

    # Validate me_id belongs to this class's course (prevent forged me_id)
    if me and (section.course_id is None or me.module.course_id != section.course_id):
        return None

    mc, just_completed = cur.record_attempt(
        current_user.id, section_id_int, me_id_int, sme_id_int, score, criterion
    )

    progress = cur.get_progress(
        current_user.id, section_id_int, me_id_int, sme_id_int, criterion
    )

    module = me.module if me else None
    if not module and sme_id_int:
        sme = SectionModuleExercise.query.get(sme_id_int)
        if sme and sme.section_id == section_id_int:
            module = Module.query.get(sme.module_id)

    module_url = url_for('section_module_detail', section_id=section_id_int,
                         module_id=module.id) if module else url_for('section_home', section_id=section_id_int)
    module_name  = module.name if module else None
    exercise_name = me.name if me else None
    keep_practicing_url = url_for('start_module_exercise',
                                  section_id=section_id_int, me_id=me_id_int,
                                  kp='1') if me_id_int else None

    if not module:
        return {
            'next_url': url_for('section_home', section_id=section_id_int),
            'module_url': url_for('section_home', section_id=section_id_int),
            'module_name': None,
            'exercise_name': exercise_name,
            'keep_practicing_url': None,
            'keep_practicing': keep_practicing,
            'module_done': False,
            'complete': mc.is_complete,
            'progress': progress,
            'section_id': section_id_int,
        }

    if mc.is_complete:
        next_ex = cur.next_incomplete(current_user.id, section_id_int, section, module)
        if next_ex:
            if next_ex['module_exercise_id']:
                next_url = url_for('start_module_exercise',
                                   section_id=section_id_int,
                                   me_id=next_ex['module_exercise_id'])
            else:
                next_url = module_url
            return {
                'next_url': next_url,
                'module_url': module_url,
                'module_name': module_name,
                'exercise_name': exercise_name,
                'keep_practicing_url': keep_practicing_url,
                'keep_practicing': keep_practicing,
                'module_done': False,
                'complete': True,
                'progress': progress,
                'section_id': section_id_int,
                'module_id': module.id,
            }
        else:
            return {
                'next_url': module_url,
                'module_url': module_url,
                'module_name': module_name,
                'exercise_name': exercise_name,
                'keep_practicing_url': keep_practicing_url,
                'keep_practicing': keep_practicing,
                'module_done': True,
                'complete': True,
                'progress': progress,
                'section_id': section_id_int,
                'module_id': module.id,
            }
    else:
        if me_id_int:
            start_url = url_for('start_module_exercise',
                                section_id=section_id_int, me_id=me_id_int)
        else:
            start_url = module_url
        return {
            'next_url': start_url,
            'module_url': module_url,
            'module_name': module_name,
            'exercise_name': exercise_name,
            'keep_practicing_url': keep_practicing_url,
            'keep_practicing': keep_practicing,
            'module_done': False,
            'complete': False,
            'progress': progress,
            'section_id': section_id_int,
            'module_id': module.id,
        }


# ---------------------------------------------------------------------------
# Grading helpers
# ---------------------------------------------------------------------------

# Pitch-class number for each note name (ignoring octave).
# Used so enharmonic equivalents (G# / Ab, etc.) compare as equal.
_PC = {
    'c': 0, 'c#': 1, 'db': 1,
    'd': 2, 'd#': 3, 'eb': 3,
    'e': 4,
    'f': 5, 'f#': 6, 'gb': 6,
    'g': 7, 'g#': 8, 'ab': 8,
    'a': 9, 'a#': 10, 'bb': 10,
    'b': 11,
}

def key_to_midi(key):
    """Convert 'g#/4' → MIDI integer (60 = C4).  Returns None on parse error."""
    try:
        slash      = key.index('/')
        letter_acc = key[:slash].strip().lower()
        octave     = int(key[slash + 1:].strip())
        pc         = _PC.get(letter_acc)
        if pc is None:
            return None
        return (octave + 1) * 12 + pc
    except (ValueError, IndexError):
        return None


def pitches_match(key1, key2):
    """True if both keys sound the same pitch (handles enharmonic equivalents)."""
    k1, k2 = key1.strip().lower(), key2.strip().lower()
    if k1 == k2:
        return True
    m1, m2 = key_to_midi(k1), key_to_midi(k2)
    return m1 is not None and m2 is not None and m1 == m2


def normalize_key(key):
    return key.strip().lower()


def grade_attempt(correct_notes, user_notes):
    """
    Compare two lists of {key, duration} dicts.
    Returns (pitch_accuracy, duration_accuracy, overall_score) as percentages.
    Pitch comparison is enharmonic-aware (G# == Ab).
    """
    if not correct_notes:
        return 0.0, 0.0, 0.0

    total = len(correct_notes)
    pitch_correct = 0
    duration_correct = 0

    for i in range(min(total, len(user_notes))):
        if pitches_match(correct_notes[i]['key'], user_notes[i]['key']):
            pitch_correct += 1
        if correct_notes[i]['duration'] == user_notes[i]['duration']:
            duration_correct += 1

    pitch_acc = pitch_correct / total * 100
    dur_acc = duration_correct / total * 100
    overall = (pitch_acc + dur_acc) / 2

    return round(pitch_acc, 1), round(dur_acc, 1), round(overall, 1)


def grade_rhythm(correct_notes, user_notes):
    """Grade a rhythm attempt — duration only, no pitch. Returns percentage."""
    if not correct_notes:
        return 0.0
    total = len(correct_notes)
    dur_correct = sum(
        1 for i in range(min(total, len(user_notes)))
        if correct_notes[i]['duration'] == user_notes[i]['duration']
    )
    return round(dur_correct / total * 100, 1)


def grade_holistic_attempt(exercise, user_data):
    """
    Grade a holistic attempt against the correct answers stored in the exercise.

    Returns:
        scores (dict): individual metric scores keyed by line id, e.g.:
            {"3_pitch": 85.0, "3_duration": 72.0,
             "5_letter": 90.0, "5_quality": 80.0,
             "4_duration": 70.0, ...}
        overall (float): simple average of all individual metric scores.
    """
    from chord_utils import grade_harmonic_attempt

    scores = {}
    for line in exercise.lines:
        key = str(line.id)
        user_line = user_data.get(key, [])
        if line.line_type == 'melody':
            p, d, _ = grade_attempt(line.content, user_line)
            scores[f'{key}_pitch'] = p
            scores[f'{key}_duration'] = d
        elif line.line_type == 'rhythm':
            scores[f'{key}_duration'] = grade_rhythm(line.content, user_line)
        elif line.line_type == 'harmonic':
            l, q, _ = grade_harmonic_attempt(line.content, user_line)
            scores[f'{key}_letter'] = l
            scores[f'{key}_quality'] = q

    overall = round(sum(scores.values()) / len(scores), 1) if scores else 0.0
    return scores, overall


def build_next_url():
    """Build the /random URL using filter params stored in the session."""
    from urllib.parse import urlencode
    difficulties = session.get('last_difficulty', [])
    tags         = session.get('last_tags', [])
    time_sigs    = session.get('last_time_sigs', [])
    min_durs     = session.get('last_min_durs', [])
    clefs        = session.get('last_clefs', [])
    params = (
        [('difficulty', d) for d in difficulties]
        + [('tag',       t) for t in tags]
        + [('time_sig',  s) for s in time_sigs]
        + [('min_dur',   d) for d in min_durs]
        + [('clef',      c) for c in clefs]
    )
    if params:
        return url_for('random_melody') + '?' + urlencode(params)
    return url_for('random_melody')


def build_next_rhythm_url():
    """Build the /rhythm/random URL using rhythm filter params stored in the session."""
    from urllib.parse import urlencode
    time_sigs = session.get('last_rhythm_time_sigs', [])
    min_durs  = session.get('last_rhythm_min_durs', [])
    tags      = session.get('last_rhythm_tags', [])
    params = (
        [('time_sig', s) for s in time_sigs]
        + [('min_dur', d) for d in min_durs]
        + [('tag',     t) for t in tags]
    )
    if params:
        return url_for('random_rhythm') + '?' + urlencode(params)
    return url_for('random_rhythm')


def _visible_exercise_filter(model):
    """Returns a SQLAlchemy filter for sandbox visibility."""
    from sqlalchemy import or_, and_
    if not current_user.is_authenticated:
        return model.visibility == 'public'
    user_school_ids = set()
    for section in current_user.sections:
        if section.course_id and section.course:
            user_school_ids.add(section.course.school_id)
    if user_school_ids:
        return or_(
            model.visibility == 'public',
            and_(model.visibility == 'school', model.school_id.in_(user_school_ids))
        )
    return model.visibility == 'public'


def _apply_exercise_filters(query, model, params):
    """Apply params_json filter dict to a SQLAlchemy query for melody/rhythm/harmonic."""
    if params.get('difficulty'):
        query = query.filter(model.difficulty.in_(params['difficulty']))
    if params.get('time_signature'):
        query = query.filter(model.time_signature == params['time_signature'])
    if params.get('key_signature') and hasattr(model, 'key_signature'):
        query = query.filter(model.key_signature == params['key_signature'])
    if params.get('category') and hasattr(model, 'category'):
        query = query.filter(model.category.in_(params['category']))
    if params.get('tags'):
        for tag_name in params['tags']:
            query = query.filter(model.tags.any(Tag.name == tag_name))
    return query


# ---------------------------------------------------------------------------
# Screen registry / debug mode
# ---------------------------------------------------------------------------

@app.context_processor
def inject_screen():
    """Make the current screen's registry entry available to every template.

    Deliberately cheap: pure dict lookups, no database access. The debug panel
    fetches the (query-backed) viewer state separately from /debug/state, so a
    normal page load costs nothing extra.
    """
    scr = screens.screen_for(request.endpoint)
    access = screens.access_info(scr['access'])
    meta = {
        'name':               scr['name'],
        'endpoint':           scr['endpoint'],
        'kind':               scr['kind'],
        'group':              scr['group'],
        'template':           scr.get('template'),
        'condition':          scr.get('condition'),
        'access':             scr['access'],
        'access_label':       access['label'],
        'access_description': access['description'],
        'access_colour':      access['colour'],
        'path':               request.path,
        'section_id':           (request.view_args or {}).get('section_id'),
    }
    return {'screen_name': scr['name'], 'screen_meta': meta}


def _viewer_state(endpoint, section_id):
    """Describe the current viewer's permissions. Only called by /debug/state."""
    scr = screens.screen_for(endpoint)

    if not current_user.is_authenticated:
        return {
            'authenticated': False,
            'identity': 'anonymous',
            'role': None,
            'real_role': None,
            'perspective': None,
            'schools': [],
            'sections': [],
            'section_context': None,
            'verdict': ('Not logged in. You can reach anything marked Anonymous; '
                        'everything else redirects to LOGIN or 403s.'),
        }

    memberships = SchoolMembership.query.filter_by(user_id=current_user.id).all()
    schools = [f'{m.school.name} ({m.role})' for m in memberships if m.school]
    sections = [f'{c.name} #{c.id}' for c in current_user.sections]

    section_context = None
    if section_id:
        section = db.session.get(Section, section_id)
        if section:
            section_context = {
                'id': section.id,
                'name': section.name,
                'is_member': current_user in section.members,
                'is_owner_teacher': section.teacher_id == current_user.id,
                'is_assigned_teacher': section.assigned_teacher_id == current_user.id,
            }

    required = scr['access']
    role = active_role()
    if role == 'admin':
        verdict = 'Site admin — every screen on the map is reachable.'
    elif required == 'site_admin':
        verdict = f'This screen is site-admin only; your role is {role}. Expect a 403.'
    elif required == 'school_admin' and role not in ('admin_teacher', 'admin'):
        verdict = f'This screen needs admin_teacher; your role is {role}. Expect a 403.'
    elif required == 'teacher' and role not in ('class_teacher', 'admin_teacher', 'admin'):
        verdict = f'This screen needs a teacher role; your role is {role}. Expect a 403.'
    elif required == 'section_member' and section_context and not (
            section_context['is_member'] or section_context['is_owner_teacher']):
        verdict = 'You are neither a member nor the owning teacher of this section. Expect a 403.'
    else:
        verdict = f'Your role ({role}) satisfies this screen.'
    if in_perspective():
        verdict = (f'Viewing as {ROLE_LABELS[role]} (real role: '
                   f'{current_user.role}). ' + verdict)

    return {
        'authenticated': True,
        'identity': current_user.display_name or current_user.email,
        'role': role,
        'real_role': current_user.role,
        'perspective': active_role() if in_perspective() else None,
        'schools': schools,
        'sections': sections,
        'section_context': section_context,
        'verdict': verdict,
    }


@app.route('/debug/panel')
def debug_panel():
    """Popup window for debug mode. Reports only the current viewer's own state."""
    scr = screens.screen_for(request.endpoint)
    access = screens.access_info(scr['access'])
    boot = {
        'name': scr['name'], 'endpoint': scr['endpoint'], 'kind': scr['kind'],
        'group': scr['group'], 'template': scr.get('template'),
        'condition': scr.get('condition'), 'access': scr['access'],
        'access_label': access['label'], 'access_description': access['description'],
        'path': request.path, 'section_id': None,
    }
    colours = {k: v['colour'] for k, v in screens.ACCESS_LEVELS.items()}
    return render_template('debug_panel.html',
                           boot_screen=boot, access_colours=colours)


@app.route('/debug/state')
def debug_state():
    """JSON viewer state for the debug panel."""
    section_id = request.args.get('section_id', type=int)
    return jsonify(_viewer_state(request.args.get('endpoint'), section_id))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
@login_required
def home():
    sandbox_mode = request.args.get('sandbox') == '1'
    role = active_role()
    # Under a perspective, list only sections this account genuinely belongs to
    # (owns, is assigned to, or is enrolled in) — see related_sections().
    user_sections = related_sections() if role == 'student' else []
    teacher_courses = []
    if role == 'admin_teacher' and not sandbox_mode:
        mem = SchoolMembership.query.filter_by(
            user_id=current_user.id, role='admin_teacher'
        ).first()
        if mem:
            teacher_courses = Course.query.filter_by(school_id=mem.school_id).all()
    return render_template('home.html',
                           user_sections=user_sections,
                           teacher_courses=teacher_courses,
                           sandbox_mode=sandbox_mode)


@app.route('/sandbox')
def sandbox():
    return render_template('home.html', user_sections=[], sandbox_mode=True)


@app.route('/melodic')
def melodic_index():
    all_tags = Tag.query.order_by(Tag.name).all()
    melodies = Melody.query.filter(_visible_exercise_filter(Melody)).all()
    melodies_data = [
        {
            'time_signature': m.time_signature,
            'min_duration':   m.min_duration,
            'clef':           m.clef,
            'tags':           [t.name for t in m.tags],
        }
        for m in melodies
    ]
    return render_template('index.html', all_tags=all_tags,
                           melodies_data=melodies_data)


@app.route('/random')
def random_melody():
    difficulties = request.args.getlist('difficulty', type=int)
    tags         = request.args.getlist('tag')
    time_sigs    = request.args.getlist('time_sig')
    min_durs     = request.args.getlist('min_dur')
    clefs        = request.args.getlist('clef')

    # Persist filters in session so "Next Melody" on results page reuses them
    session['last_difficulty'] = difficulties
    session['last_tags']       = tags
    session['last_time_sigs']  = time_sigs
    session['last_min_durs']   = min_durs
    session['last_clefs']      = clefs

    query = Melody.query
    if difficulties:
        query = query.filter(Melody.difficulty.in_(difficulties))
    if tags:
        # OR logic: melody must have at least one of the selected tags
        query = query.filter(Melody.tags.any(Tag.name.in_(tags)))
    if time_sigs:
        query = query.filter(Melody.time_signature.in_(time_sigs))
    if min_durs:
        query = query.filter(Melody.min_duration.in_(min_durs))
    if clefs:
        query = query.filter(Melody.clef.in_(clefs))

    melodies = query.all()
    if not melodies:
        # Nothing matched — fall back to full library
        melodies = Melody.query.all()

    melody = random.choice(melodies)
    return redirect(url_for('exercise', melody_id=melody.id))


@app.route('/exercise/<int:melody_id>')
def exercise(melody_id):
    melody = Melody.query.get_or_404(melody_id)
    return render_template('exercise.html', melody=melody)


@app.route('/submit/<int:melody_id>', methods=['POST'])
@login_required
def submit(melody_id):
    melody = Melody.query.get_or_404(melody_id)

    data = request.get_json()
    if not data or 'notes' not in data:
        return jsonify({'error': 'No notes submitted'}), 400

    user_notes = data['notes']
    correct_notes = melody.notes

    pitch_acc, dur_acc, overall = grade_attempt(correct_notes, user_notes)

    attempt = UserAttempt(
        melody_id=melody_id,
        user_notes_json=json.dumps(user_notes),
        pitch_accuracy=pitch_acc,
        duration_accuracy=dur_acc,
        overall_score=overall,
        user_id=current_user.id if current_user.is_authenticated else None,
    )
    db.session.add(attempt)
    db.session.commit()

    section_id = data.get('section_id', '')
    me_id    = data.get('me_id', '')
    sme_id   = data.get('sme_id', '')
    return jsonify({'redirect': url_for('results', attempt_id=attempt.id,
                                        section_id=section_id, me_id=me_id, sme_id=sme_id)})


@app.route('/results/<int:attempt_id>')
@login_required
def results(attempt_id):
    attempt = UserAttempt.query.get_or_404(attempt_id)
    if attempt.user_id is not None and attempt.user_id != current_user.id:
        is_teacher = attempt.user and any(
            s.teacher_id == current_user.id for s in attempt.user.sections
        )
        if not is_teacher and active_role() != 'admin':
            abort(403)
    melody = attempt.melody
    correct_notes = melody.notes
    user_notes = attempt.user_notes

    # Build a per-note comparison list
    comparison = []
    total = max(len(correct_notes), len(user_notes))
    for i in range(total):
        c = correct_notes[i] if i < len(correct_notes) else None
        u = user_notes[i] if i < len(user_notes) else None
        comparison.append({
            'index': i + 1,
            'correct': c,
            'user': u,
            'pitch_match': (c and u and pitches_match(c['key'], u['key'])),
            'duration_match': (c and u and c['duration'] == u['duration']),
        })

    next_url = build_next_url()

    section_id = request.args.get('section_id')
    me_id    = request.args.get('me_id')
    sme_id   = request.args.get('sme_id')
    kp       = request.args.get('kp', '') == '1'
    module_ctx = None
    if current_user.is_authenticated and section_id:
        module_ctx = _handle_module_completion(section_id, me_id, sme_id, attempt.overall_score,
                                               keep_practicing=kp)

    return render_template('results.html', attempt=attempt, melody=melody,
                           comparison=comparison, next_url=next_url, module_ctx=module_ctx)


# ---------------------------------------------------------------------------
# Rhythm routes
# ---------------------------------------------------------------------------

@app.route('/rhythm')
def rhythm_index():
    all_tags = Tag.query.filter(Tag.rhythms.any()).order_by(Tag.name).all()
    rhythms = Rhythm.query.filter(_visible_exercise_filter(Rhythm)).all()
    rhythms_data = [
        {
            'time_signature': r.time_signature,
            'min_duration':   r.min_duration,
            'tags':           [t.name for t in r.tags],
        }
        for r in rhythms
    ]
    return render_template('rhythm_index.html', all_tags=all_tags,
                           rhythms_data=rhythms_data)


@app.route('/rhythm/random')
def random_rhythm():
    time_sigs = request.args.getlist('time_sig')
    min_durs  = request.args.getlist('min_dur')
    tags      = request.args.getlist('tag')

    session['last_rhythm_time_sigs'] = time_sigs
    session['last_rhythm_min_durs']  = min_durs
    session['last_rhythm_tags']      = tags

    query = Rhythm.query
    if time_sigs:
        query = query.filter(Rhythm.time_signature.in_(time_sigs))
    if min_durs:
        query = query.filter(Rhythm.min_duration.in_(min_durs))
    if tags:
        query = query.filter(Rhythm.tags.any(Tag.name.in_(tags)))

    rhythms = query.all()
    if not rhythms:
        rhythms = Rhythm.query.all()

    rhythm = random.choice(rhythms)
    return redirect(url_for('rhythm_exercise', rhythm_id=rhythm.id))


@app.route('/rhythm/exercise/<int:rhythm_id>')
def rhythm_exercise(rhythm_id):
    rhythm = Rhythm.query.get_or_404(rhythm_id)
    return render_template('rhythm_exercise.html', rhythm=rhythm)


@app.route('/rhythm/submit/<int:rhythm_id>', methods=['POST'])
@login_required
def rhythm_submit(rhythm_id):
    rhythm = Rhythm.query.get_or_404(rhythm_id)

    data = request.get_json()
    if not data or 'notes' not in data:
        return jsonify({'error': 'No notes submitted'}), 400

    user_notes    = data['notes']
    correct_notes = rhythm.notes
    dur_acc       = grade_rhythm(correct_notes, user_notes)

    attempt = RhythmAttempt(
        rhythm_id=rhythm_id,
        user_notes_json=json.dumps(user_notes),
        duration_accuracy=dur_acc,
        user_id=current_user.id if current_user.is_authenticated else None,
    )
    db.session.add(attempt)
    db.session.commit()

    section_id = data.get('section_id', '')
    me_id    = data.get('me_id', '')
    sme_id   = data.get('sme_id', '')
    return jsonify({'redirect': url_for('rhythm_results', attempt_id=attempt.id,
                                        section_id=section_id, me_id=me_id, sme_id=sme_id)})


@app.route('/rhythm/results/<int:attempt_id>')
@login_required
def rhythm_results(attempt_id):
    attempt = RhythmAttempt.query.get_or_404(attempt_id)
    if attempt.user_id is not None and attempt.user_id != current_user.id:
        is_teacher = attempt.user and any(
            s.teacher_id == current_user.id for s in attempt.user.sections
        )
        if not is_teacher and active_role() != 'admin':
            abort(403)
    rhythm  = attempt.rhythm
    correct_notes = rhythm.notes
    user_notes    = attempt.user_notes

    comparison = []
    total = max(len(correct_notes), len(user_notes))
    for i in range(total):
        c = correct_notes[i] if i < len(correct_notes) else None
        u = user_notes[i]    if i < len(user_notes)    else None
        comparison.append({
            'index':          i + 1,
            'correct':        c,
            'user':           u,
            'duration_match': (c and u and c['duration'] == u['duration']),
        })

    next_url = build_next_rhythm_url()

    section_id = request.args.get('section_id')
    me_id    = request.args.get('me_id')
    sme_id   = request.args.get('sme_id')
    kp       = request.args.get('kp', '') == '1'
    module_ctx = None
    if current_user.is_authenticated and section_id:
        module_ctx = _handle_module_completion(section_id, me_id, sme_id, attempt.duration_accuracy,
                                               keep_practicing=kp)

    return render_template('rhythm_results.html', attempt=attempt, rhythm=rhythm,
                           comparison=comparison, next_url=next_url, module_ctx=module_ctx)


# ---------------------------------------------------------------------------
# Harmonic Dictation routes
# ---------------------------------------------------------------------------

@app.route('/harmonic')
def harmonic_index():
    all_tags     = Tag.query.filter(Tag.progressions.any()).order_by(Tag.name).all()
    contains_tags = [t for t in all_tags if t.name.startswith('contains:')]
    other_tags    = [t for t in all_tags if not t.name.startswith('contains:')]
    progressions = ChordProgression.query.filter(_visible_exercise_filter(ChordProgression)).all()
    progressions_data = [
        {
            'category':   p.category,
            'difficulty': p.difficulty,
            'key':        p.key_signature,
            'tags':       [t.name for t in p.tags],
        }
        for p in progressions
    ]
    categories = ['diatonic', 'chromatic', 'mode_mixture', 'modal']
    return render_template('harmonic_index.html',
                           contains_tags=contains_tags,
                           other_tags=other_tags,
                           progressions_data=progressions_data,
                           categories=categories)


@app.route('/harmonic/random')
def random_harmonic():
    categories   = request.args.getlist('category')
    difficulties = request.args.getlist('difficulty', type=int)
    tags         = request.args.getlist('tag')
    show_count   = request.args.get('show_chord_count', '0')

    session['last_harmonic_categories']   = categories
    session['last_harmonic_difficulties'] = difficulties
    session['last_harmonic_tags']         = tags
    session['last_harmonic_show_chord_count'] = (show_count == '1')

    query = ChordProgression.query
    if categories:
        query = query.filter(ChordProgression.category.in_(categories))
    if difficulties:
        query = query.filter(ChordProgression.difficulty.in_(difficulties))
    if tags:
        query = query.filter(ChordProgression.tags.any(Tag.name.in_(tags)))

    progressions = query.all()
    if not progressions:
        progressions = ChordProgression.query.all()

    progression = random.choice(progressions)
    return redirect(url_for('harmonic_exercise', progression_id=progression.id))


@app.route('/harmonic/exercise/<int:progression_id>')
def harmonic_exercise(progression_id):
    progression = ChordProgression.query.get_or_404(progression_id)
    chords = progression.chords
    unlock_seventh    = any(c.get('seventh')    for c in chords)
    unlock_extensions = any(c.get('extensions') for c in chords)
    unlock_sus        = any(c.get('sus')        for c in chords)
    show_chord_count  = session.get('last_harmonic_show_chord_count', False)
    return render_template('harmonic_exercise.html',
                           progression=progression,
                           unlock_seventh=unlock_seventh,
                           unlock_extensions=unlock_extensions,
                           unlock_sus=unlock_sus,
                           show_chord_count=show_chord_count,
                           num_chords=len(chords))


@app.route('/harmonic/submit/<int:progression_id>', methods=['POST'])
@login_required
def harmonic_submit(progression_id):
    progression = ChordProgression.query.get_or_404(progression_id)
    data = request.get_json()
    if not data or 'chords' not in data:
        return jsonify({'error': 'No chords submitted'}), 400

    user_chords    = data['chords']
    correct_chords = progression.chords

    letter_acc, quality_acc, overall = grade_harmonic_attempt(correct_chords, user_chords)

    attempt = HarmonicAttempt(
        progression_id        = progression_id,
        user_chords_json      = json.dumps(user_chords),
        chord_letter_accuracy = letter_acc,
        chord_quality_accuracy= quality_acc,
        overall_score         = overall,
        user_id               = current_user.id if current_user.is_authenticated else None,
    )
    db.session.add(attempt)
    db.session.commit()

    section_id = data.get('section_id', '')
    me_id    = data.get('me_id', '')
    sme_id   = data.get('sme_id', '')
    return jsonify({'redirect': url_for('harmonic_results', attempt_id=attempt.id,
                                        section_id=section_id, me_id=me_id, sme_id=sme_id)})


@app.route('/harmonic/results/<int:attempt_id>')
@login_required
def harmonic_results(attempt_id):
    attempt     = HarmonicAttempt.query.get_or_404(attempt_id)
    if attempt.user_id is not None and attempt.user_id != current_user.id:
        is_teacher = attempt.user and any(
            s.teacher_id == current_user.id for s in attempt.user.sections
        )
        if not is_teacher and active_role() != 'admin':
            abort(403)
    progression = attempt.progression
    correct_chords = progression.chords
    user_chords    = attempt.user_chords

    comparison = []
    total = max(len(correct_chords), len(user_chords)) if correct_chords or user_chords else 0
    for i in range(total):
        c = correct_chords[i] if i < len(correct_chords) else None
        u = user_chords[i]    if i < len(user_chords)    else None
        comparison.append({
            'index':         i + 1,
            'correct':       c,
            'user':          u,
            'letter_match':  (c and u and c['root_pc'] == u['root_pc']),
            'quality_match': (c and u
                              and c['quality']             == u.get('quality')
                              and c.get('sus')             == u.get('sus')
                              and c.get('seventh')         == u.get('seventh')
                              and sorted(c.get('extensions') or []) == sorted(u.get('extensions') or [])),
        })

    # Pre-format chord names in all three modes for the toggle to work without reload
    def fmt_all(chord):
        if not chord:
            return {'lead': '—', 'roman': '—', 'nashville': '—'}
        return {
            'lead':      format_chord_name(chord, 'lead',      progression.key_signature),
            'roman':     format_chord_name(chord, 'roman',     progression.key_signature),
            'nashville': format_chord_name(chord, 'nashville', progression.key_signature),
        }

    correct_formatted = [fmt_all(c['correct']) for c in comparison]
    user_formatted    = [fmt_all(c['user'])    for c in comparison]

    # Build next URL from session
    from urllib.parse import urlencode
    cats   = session.get('last_harmonic_categories', [])
    diffs  = session.get('last_harmonic_difficulties', [])
    tags   = session.get('last_harmonic_tags', [])
    show   = session.get('last_harmonic_show_chord_count', False)
    params = (
        [('category',   c) for c in cats]
        + [('difficulty', d) for d in diffs]
        + [('tag',        t) for t in tags]
        + [('show_chord_count', '1' if show else '0')]
    )
    next_url = url_for('random_harmonic') + '?' + urlencode(params)

    section_id = request.args.get('section_id')
    me_id    = request.args.get('me_id')
    sme_id   = request.args.get('sme_id')
    kp       = request.args.get('kp', '') == '1'
    module_ctx = None
    if current_user.is_authenticated and section_id:
        module_ctx = _handle_module_completion(section_id, me_id, sme_id, attempt.overall_score,
                                               keep_practicing=kp)

    return render_template('harmonic_results.html',
                           attempt=attempt,
                           progression=progression,
                           comparison=comparison,
                           correct_formatted=correct_formatted,
                           user_formatted=user_formatted,
                           next_url=next_url,
                           correct_chords_json=json.dumps(correct_chords),
                           user_chords_json=json.dumps(user_chords),
                           module_ctx=module_ctx)


# ---------------------------------------------------------------------------
# Holistic Dictation routes
# ---------------------------------------------------------------------------

@app.route('/holistic')
def holistic_index():
    exercises = HolisticExercise.query.filter(_visible_exercise_filter(HolisticExercise)).all()
    all_tags  = Tag.query.filter(Tag.holistic_exercises.any()).order_by(Tag.name).all()
    contains_tags = [t for t in all_tags if t.name.startswith('contains:')]
    other_tags    = [t for t in all_tags if not t.name.startswith('contains:')]
    time_sigs = sorted(set(e.time_signature for e in exercises))
    return render_template('holistic_index.html',
                           exercises=exercises,
                           contains_tags=contains_tags,
                           other_tags=other_tags,
                           time_sigs=time_sigs)


@app.route('/holistic/exercise/<int:exercise_id>')
def holistic_exercise(exercise_id):
    exercise = HolisticExercise.query.get_or_404(exercise_id)
    harmonic_lines = [l for l in exercise.lines if l.line_type == 'harmonic']
    all_chords = [c for l in harmonic_lines for c in l.content]
    unlock_seventh    = any(c.get('seventh')    for c in all_chords)
    unlock_extensions = any(c.get('extensions') for c in all_chords)
    unlock_sus        = any(c.get('sus')        for c in all_chords)
    lines_display = [
        {'id': l.id, 'key': str(l.id), 'type': l.line_type, 'label': l.name, 'clef': l.clef or 'treble'}
        for l in exercise.lines
    ]
    return render_template('holistic_exercise.html',
                           exercise=exercise,
                           unlock_seventh=unlock_seventh,
                           unlock_extensions=unlock_extensions,
                           unlock_sus=unlock_sus,
                           lines_display=lines_display)


@app.route('/holistic/submit/<int:exercise_id>', methods=['POST'])
@login_required
def holistic_submit(exercise_id):
    exercise = HolisticExercise.query.get_or_404(exercise_id)
    data = request.get_json()
    if not data or 'lines' not in data:
        return jsonify({'error': 'No data submitted'}), 400

    user_data = data['lines']   # dict keyed by line id
    scores, overall = grade_holistic_attempt(exercise, user_data)

    attempt = HolisticAttempt(
        exercise_id    = exercise_id,
        user_data_json = json.dumps(user_data),
        scores_json    = json.dumps(scores),
        overall_score  = overall,
        user_id        = current_user.id if current_user.is_authenticated else None,
    )
    db.session.add(attempt)
    db.session.commit()

    section_id = data.get('section_id', '')
    me_id    = data.get('me_id', '')
    sme_id   = data.get('sme_id', '')
    return jsonify({'redirect': url_for('holistic_results', attempt_id=attempt.id,
                                        section_id=section_id, me_id=me_id, sme_id=sme_id)})


@app.route('/holistic/results/<int:attempt_id>')
@login_required
def holistic_results(attempt_id):
    attempt  = HolisticAttempt.query.get_or_404(attempt_id)
    if attempt.user_id is not None and attempt.user_id != current_user.id:
        is_teacher = attempt.user and any(
            s.teacher_id == current_user.id for s in attempt.user.sections
        )
        if not is_teacher and active_role() != 'admin':
            abort(403)
    exercise = attempt.exercise

    section_id = request.args.get('section_id')
    me_id    = request.args.get('me_id')
    sme_id   = request.args.get('sme_id')
    kp       = request.args.get('kp', '') == '1'
    module_ctx = None
    if current_user.is_authenticated and section_id:
        module_ctx = _handle_module_completion(section_id, me_id, sme_id, attempt.overall_score,
                                               keep_practicing=kp)

    return render_template('holistic_results.html',
                           attempt=attempt,
                           exercise=exercise,
                           module_ctx=module_ctx)


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
from werkzeug.security import generate_password_hash, check_password_hash


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        name     = request.form.get('display_name', '').strip()
        if not email or not password:
            flash('Email and password are required.', 'danger')
            return render_template('auth/register.html')
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('auth/register.html')
        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'danger')
            return render_template('auth/register.html')
        user = User(
            email         = email,
            password_hash = generate_password_hash(password, method='pbkdf2:sha256'),
            display_name  = name or email.split('@')[0],
            role          = 'student',
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Account created! Welcome.', 'success')
        return redirect(url_for('home'))
    return render_template('auth/register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user     = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid email or password.', 'danger')
            return render_template('auth/login.html')
        login_user(user, remember=request.form.get('remember') == 'on')
        from urllib.parse import urlparse
        next_page = request.args.get('next')
        if next_page and urlparse(next_page).netloc != '':
            next_page = None
        return redirect(next_page or url_for('home'))
    return render_template('auth/login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))


# ---------------------------------------------------------------------------
# Stub routes (replaced in Tasks 1-G and 1-H)
# ---------------------------------------------------------------------------

@app.route('/admin')
@login_required
@role_required('admin')
def admin():
    return render_template('admin/index.html',
        user_count=User.query.count(),
        school_count=School.query.count(),
        section_count=Section.query.count(),
        melody_count=Melody.query.count(),
        harmonic_count=ChordProgression.query.count(),
        rhythm_count=Rhythm.query.count(),
        holistic_count=HolisticExercise.query.count(),
        gen_prog_count=GenProgression.query.count(),
    )


@app.route('/admin/users')
@login_required
@role_required('admin')
def admin_users():
    users = User.query.order_by(User.email).all()
    return render_template('admin/users.html', users=users)


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_user(user_id):
    if user_id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin_users'))
    u = User.query.get_or_404(user_id)
    db.session.delete(u)
    db.session.commit()
    flash(f'User {u.email} deleted.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/schools', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_schools():
    if request.method == 'POST':
        name = request.form['name'].strip()
        if name:
            db.session.add(School(name=name))
            db.session.commit()
            flash('School created.', 'success')
        return redirect(url_for('admin_schools'))
    schools = School.query.order_by(School.name).all()
    return render_template('admin/schools.html', schools=schools)


@app.route('/admin/schools/<int:school_id>/courses', methods=['GET', 'POST'])
@login_required
@role_required('admin_teacher', 'admin')
def admin_courses(school_id):
    require_school_role(school_id, 'admin_teacher')
    school = School.query.get_or_404(school_id)
    if request.method == 'POST':
        name = request.form['name'].strip()
        if name:
            db.session.add(Course(name=name, school_id=school_id))
            db.session.commit()
            flash('Course created.', 'success')
        return redirect(url_for('admin_courses', school_id=school_id))
    courses = Course.query.filter_by(school_id=school_id).order_by(Course.name).all()
    return render_template('admin/courses.html', school=school, courses=courses)


@app.route('/admin/courses/<int:course_id>/modules', methods=['GET', 'POST'])
@login_required
@role_required('admin_teacher', 'admin')
def admin_modules(course_id):
    course = Course.query.get_or_404(course_id)
    require_school_role(course.school_id, 'admin_teacher')
    if request.method == 'POST':
        name  = request.form['name'].strip()
        order = int(request.form.get('order', 0))
        if name:
            db.session.add(Module(name=name, course_id=course_id, order=order))
            db.session.commit()
            flash('Module created.', 'success')
        return redirect(url_for('admin_modules', course_id=course_id))
    modules = Module.query.filter_by(course_id=course_id).order_by(Module.order).all()
    return render_template('admin/modules.html', course=course, modules=modules)


@app.route('/admin/modules/<int:module_id>/exercises', methods=['GET', 'POST'])
@login_required
@role_required('admin_teacher', 'admin')
def admin_module_exercises(module_id):
    module = Module.query.get_or_404(module_id)
    require_school_role(module.course.school_id, 'admin_teacher')
    if request.method == 'POST':
        ex_type   = request.form['exercise_type']
        name      = request.form.get('name', '').strip() or ex_type.capitalize()
        order     = int(request.form.get('order', 0))
        criterion_type = request.form.get('criterion_type', 'attempts')
        if criterion_type == 'passing':
            passing   = int(request.form.get('completion_passing', 1))
            min_score = int(request.form.get('completion_min_score', 70))
            criterion = json.dumps({'passing': passing, 'min_score': min_score})
        else:
            attempts  = int(request.form.get('completion_attempts', 1))
            criterion = json.dumps({'attempts': attempts})

        if ex_type == 'holistic':
            ex_id      = int(request.form['exercise_id'])
            params_val = None
        else:
            ex_id = 0  # sentinel — not used for filter-based exercises
            difficulties = request.form.getlist('difficulty')
            tags_list    = request.form.getlist('tag')
            category_list = request.form.getlist('category')
            time_sig     = request.form.get('time_signature', '').strip()
            key_sig      = request.form.get('key_signature', '').strip()
            params_dict  = {}
            if difficulties:
                params_dict['difficulty'] = [int(d) for d in difficulties]
            if tags_list:
                params_dict['tags'] = [t for t in tags_list if t]
            if category_list and ex_type == 'harmonic':
                params_dict['category'] = [c for c in category_list if c]
            if time_sig:
                params_dict['time_signature'] = time_sig
            if key_sig and ex_type == 'harmonic':
                params_dict['key_signature'] = key_sig
            params_val = json.dumps(params_dict) if params_dict else None

        db.session.add(ModuleExercise(
            module_id=module_id,
            name=name,
            exercise_type=ex_type,
            exercise_id=ex_id,
            order=order,
            completion_criterion_json=criterion,
            params_json=params_val,
        ))
        db.session.commit()
        flash('Exercise added to module.', 'success')
        return redirect(url_for('admin_module_exercises', module_id=module_id))
    exercises = module.exercises.order_by(ModuleExercise.order).all()
    melodies     = Melody.query.order_by(Melody.name).all()
    rhythms      = Rhythm.query.order_by(Rhythm.name).all()
    progressions = ChordProgression.query.order_by(ChordProgression.name).all()
    holistics    = HolisticExercise.query.order_by(HolisticExercise.name).all()
    all_tags = [t.name for t in Tag.query.order_by(Tag.name).all()]
    melody_tags_list  = sorted({t.name for m in melodies     for t in m.tags})
    rhythm_tags_list  = sorted({t.name for r in rhythms      for t in r.tags})
    harmonic_tags_list = sorted({t.name for p in progressions for t in p.tags})
    harmonic_categories = sorted({p.category for p in progressions if p.category})
    melodies_data = [{'time_signature': m.time_signature, 'min_duration': m.min_duration,
                      'clef': m.clef, 'tags': [t.name for t in m.tags]} for m in melodies]
    rhythms_data  = [{'time_signature': r.time_signature, 'min_duration': r.min_duration,
                      'tags': [t.name for t in r.tags]} for r in rhythms]
    progressions_data = [{'category': p.category, 'difficulty': p.difficulty,
                          'tags': [t.name for t in p.tags]} for p in progressions]
    return render_template('admin/module_exercises.html',
                           module=module,
                           exercises=exercises,
                           holistics=holistics,
                           all_tags=all_tags,
                           melody_tags_list=melody_tags_list,
                           rhythm_tags_list=rhythm_tags_list,
                           harmonic_tags_list=harmonic_tags_list,
                           harmonic_categories=harmonic_categories,
                           melodies_data=melodies_data,
                           rhythms_data=rhythms_data,
                           progressions_data=progressions_data)


@app.route('/admin/module_exercises/<int:me_id>/delete', methods=['POST'])
@login_required
@role_required('admin_teacher', 'admin')
def admin_delete_module_exercise(me_id):
    me = ModuleExercise.query.get_or_404(me_id)
    require_school_role(me.module.course.school_id, 'admin_teacher')
    module_id = me.module_id
    db.session.delete(me)
    db.session.commit()
    flash('Exercise removed.', 'success')
    return redirect(url_for('admin_module_exercises', module_id=module_id))


@app.route('/admin/module_exercises/<int:me_id>/edit', methods=['POST'])
@login_required
@role_required('admin_teacher', 'admin')
def admin_edit_module_exercise(me_id):
    me = ModuleExercise.query.get_or_404(me_id)
    require_school_role(me.module.course.school_id, 'admin_teacher')
    me.name  = request.form.get('name', me.name).strip() or me.name
    me.order = int(request.form.get('order', me.order))
    criterion_type = request.form.get('criterion_type', 'attempts')
    if criterion_type == 'passing':
        passing   = int(request.form.get('completion_passing', 1))
        min_score = int(request.form.get('completion_min_score', 70))
        me.completion_criterion_json = json.dumps({'passing': passing, 'min_score': min_score})
    else:
        attempts = int(request.form.get('completion_attempts', 1))
        me.completion_criterion_json = json.dumps({'attempts': attempts})
    if me.exercise_type != 'holistic':
        difficulties = request.form.getlist('difficulty')
        tags_list    = request.form.getlist('tag')
        category_list = request.form.getlist('category')
        time_sig     = request.form.get('time_signature', '').strip()
        key_sig      = request.form.get('key_signature', '').strip()
        params_dict  = {}
        if difficulties:
            params_dict['difficulty'] = [int(d) for d in difficulties]
        if tags_list:
            params_dict['tags'] = [t for t in tags_list if t]
        if category_list and me.exercise_type == 'harmonic':
            params_dict['category'] = [c for c in category_list if c]
        if time_sig:
            params_dict['time_signature'] = time_sig
        if key_sig and me.exercise_type == 'harmonic':
            params_dict['key_signature'] = key_sig
        me.params_json = json.dumps(params_dict) if params_dict else None
    db.session.commit()
    flash('Exercise updated.', 'success')
    return redirect(url_for('admin_module_exercises', module_id=me.module_id))


@app.route('/admin/module_exercises/<int:me_id>/duplicate', methods=['POST'])
@login_required
@role_required('admin_teacher', 'admin')
def admin_duplicate_module_exercise(me_id):
    src = ModuleExercise.query.get_or_404(me_id)
    require_school_role(src.module.course.school_id, 'admin_teacher')
    copy = ModuleExercise(
        module_id=src.module_id,
        name=src.name + ' (copy)',
        exercise_type=src.exercise_type,
        exercise_id=src.exercise_id,
        order=src.order + 1,
        completion_criterion_json=src.completion_criterion_json,
        params_json=src.params_json,
    )
    db.session.add(copy)
    db.session.commit()
    flash('Exercise duplicated.', 'success')
    return redirect(url_for('admin_module_exercises', module_id=src.module_id))


@app.route('/admin/schools/<int:school_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_school(school_id):
    school = School.query.get_or_404(school_id)
    name = school.name
    for course in school.courses.all():
        for module in course.modules.all():
            # Clean up dependent records before deleting ModuleExercise
            me_ids = [me.id for me in ModuleExercise.query.filter_by(module_id=module.id).all()]
            if me_ids:
                ModuleCompletion.query.filter(ModuleCompletion.module_exercise_id.in_(me_ids)).delete(synchronize_session=False)
                SectionModuleExercise.query.filter(SectionModuleExercise.module_exercise_id.in_(me_ids)).delete(synchronize_session=False)
            ModuleExercise.query.filter_by(module_id=module.id).delete()
            db.session.delete(module)
        db.session.delete(course)
    db.session.delete(school)
    db.session.commit()
    flash(f'School "{name}" deleted.', 'success')
    return redirect(url_for('admin_schools'))


@app.route('/admin/schools/<int:school_id>/detail', methods=['GET'])
@login_required
@role_required('class_teacher', 'admin_teacher', 'admin')
def admin_school_detail(school_id):
    school = School.query.get_or_404(school_id)
    require_school_role(school_id, 'class_teacher')
    can_manage_members = role_rank(effective_school_role(school_id) or '') \
        >= role_rank('admin_teacher')
    memberships = SchoolMembership.query.filter_by(school_id=school_id).all()
    return render_template(
        'admin/school_detail.html',
        school=school,
        memberships=memberships,
        is_full_admin=(active_role() == 'admin'),
        my_school_role=effective_school_role(school_id),
        grantable_roles=grantable_school_roles(school_id),
        can_manage_members=can_manage_members,
        school_admins=[m.user for m in memberships
                       if m.role == 'admin_teacher' and m.user],
        # Precomputed so the template never has to re-derive authority.
        actionable={m.user_id: outranks_in_school(school_id, m.user)
                    for m in memberships if m.user},
    )


@app.route('/admin/schools/<int:school_id>/set-member-role', methods=['POST'])
@login_required
@role_required('admin_teacher', 'admin')
def admin_set_member_role(school_id):
    School.query.get_or_404(school_id)
    require_school_role(school_id, 'admin_teacher')
    back = redirect(url_for('admin_school_detail', school_id=school_id))

    user_id  = request.form.get('user_id', type=int)
    new_role = request.form.get('role', '').strip()

    target = db.session.get(User, user_id) if user_id else None
    if target is None:
        flash('No such user.', 'danger')
        return back
    mem = SchoolMembership.query.filter_by(
        school_id=school_id, user_id=user_id).first()
    if not mem:
        flash('User is not a member of this school.', 'danger')
        return back

    # You may only act on someone whose school role is strictly below your own…
    if not outranks_in_school(school_id, target):
        flash('You can only change the role of members below your own.', 'danger')
        return back
    # …and only hand out a role strictly below your own.
    if new_role not in grantable_school_roles(school_id):
        flash(f'You cannot grant the role "{new_role}".', 'danger')
        return back

    mem.role = new_role
    _sync_global_role(target)
    db.session.commit()
    flash(f'{target.email} is now {new_role} in {mem.school.name}.', 'success')
    return back


def _sync_global_role(user):
    """Keep User.role in step with the user's highest role across all schools.

    School membership is the source of truth for staff status: promote someone
    anywhere and they gain the role globally; strip their last staff membership
    and they drop back to student. Site admins are never demoted by this — their
    role is global, not conferred by any school.
    """
    if user.role == 'admin':
        return
    mems = SchoolMembership.query.filter_by(user_id=user.id).all()
    best = 'student'
    for m in mems:
        if role_rank(m.role) > role_rank(best):
            best = m.role
    user.role = best


@app.route('/admin/schools/<int:school_id>/add-member', methods=['POST'])
@login_required
@role_required('admin_teacher', 'admin')
def admin_add_school_member(school_id):
    School.query.get_or_404(school_id)
    require_school_role(school_id, 'admin_teacher')
    back = redirect(url_for('admin_school_detail', school_id=school_id))

    email = request.form.get('email', '').strip()
    role  = request.form.get('role', 'student')

    # Only roles strictly below your own — so only a site admin can seat an
    # admin_teacher, which is what makes "the site admin decides which schools
    # an admin_teacher is over" hold.
    if role not in grantable_school_roles(school_id):
        flash(f'You cannot grant the role "{role}".', 'danger')
        return back

    user = User.query.filter_by(email=email).first()
    if not user:
        flash(f'No user with email "{email}".', 'danger')
        return back
    if SchoolMembership.query.filter_by(school_id=school_id, user_id=user.id).first():
        flash(f'{email} is already a member.', 'info')
        return back

    db.session.add(SchoolMembership(school_id=school_id, user_id=user.id, role=role))
    db.session.flush()
    _sync_global_role(user)
    db.session.commit()
    flash(f'Added {email} as {role}.', 'success')
    return back


@app.route('/admin/schools/<int:school_id>/set-admin', methods=['POST'])
@login_required
@role_required('admin_teacher', 'admin')
def admin_set_school_admin(school_id):
    """Appoint someone, by email, as an administrative teacher of this school.

    Requirement 1 of the authority model — "the site admin decides which schools
    an admin_teacher is over" — falls out of the ordinary strictly-below rule:
    granting admin_teacher needs a school role ranking above it, which only a
    site admin has. This route is the dedicated place to do it, and handles both
    cases: promoting an existing member, and adding someone who is not a member
    yet.
    """
    school = School.query.get_or_404(school_id)
    require_school_role(school_id, 'admin_teacher')
    back = redirect(url_for('admin_school_detail', school_id=school_id))

    if 'admin_teacher' not in grantable_school_roles(school_id):
        flash('Only a site admin can appoint a school administrator.', 'danger')
        return back

    email = (request.form.get('email') or '').strip()
    user = find_user_by_email(email)
    if user is None:
        flash(f'No account found for "{email}".', 'danger')
        return back

    mem = SchoolMembership.query.filter_by(
        school_id=school_id, user_id=user.id).first()
    if mem is None:
        db.session.add(SchoolMembership(school_id=school_id, user_id=user.id,
                                        role='admin_teacher'))
        verb = 'added to'
    elif mem.role == 'admin_teacher':
        flash(f'{user.email} already administers {school.name}.', 'info')
        return back
    else:
        mem.role = 'admin_teacher'
        verb = 'promoted in'

    db.session.flush()
    _sync_global_role(user)
    db.session.commit()
    flash(f'{user.email} {verb} {school.name} as an administrative teacher.',
          'success')
    return back


@app.route('/admin/schools/<int:school_id>/remove-member', methods=['POST'])
@login_required
@role_required('class_teacher', 'admin_teacher', 'admin')
def admin_remove_school_member(school_id):
    """Remove a member from a school.

    Anyone above student may remove someone whose school role is strictly below
    their own. Removal also drops the person from that school's sections —
    otherwise they would keep doing the coursework they were just removed from.
    Attempt history and completion records are left untouched.
    """
    School.query.get_or_404(school_id)
    require_school_role(school_id, 'class_teacher')
    back = redirect(url_for('admin_school_detail', school_id=school_id))

    user_id = request.form.get('user_id', type=int)
    target = db.session.get(User, user_id) if user_id else None
    if target is None:
        flash('No such user.', 'danger')
        return back
    mem = SchoolMembership.query.filter_by(
        school_id=school_id, user_id=user_id).first()
    if not mem:
        flash('User is not a member of this school.', 'danger')
        return back
    if not outranks_in_school(school_id, target):
        flash('You can only remove members below your own role.', 'danger')
        return back

    # A section's teacher_id is NOT nullable, so refuse rather than cascade-delete
    # somebody's sections out from under them.
    owned = [s for s in Section.query.filter_by(teacher_id=target.id).all()
             if section_school_id(s) == school_id]
    if owned:
        names = ', '.join(s.name for s in owned)
        flash(f'{target.email} still owns {len(owned)} '
              f'{section_word(plural=len(owned) != 1)} here ({names}). '
              f'Reassign or delete them first.', 'danger')
        return back

    school_sections = [s for s in Section.query.all()
                       if section_school_id(s) == school_id]
    dropped = 0
    unassigned = 0
    for sec in school_sections:
        if target in sec.members:
            sec.members.remove(target)
            dropped += 1
        if sec.assigned_teacher_id == target.id:
            sec.assigned_teacher_id = None
            unassigned += 1

    db.session.delete(mem)
    db.session.flush()
    _sync_global_role(target)
    db.session.commit()

    detail = []
    if dropped:
        detail.append(f'removed from {dropped} {section_word(plural=dropped != 1)}')
    if unassigned:
        detail.append(f'unassigned as teacher of {unassigned}')
    suffix = f' ({"; ".join(detail)})' if detail else ''
    flash(f'{target.email} removed from the school{suffix}.', 'success')
    return back


@app.route('/admin/schools/<int:school_id>/regen-join-code', methods=['POST'])
@login_required
@role_required('admin_teacher', 'admin')
def admin_regen_join_code(school_id):
    school = School.query.get_or_404(school_id)
    require_school_role(school_id, 'admin_teacher')
    school.join_code = _random_school_code()
    db.session.commit()
    flash(f'Join code regenerated: {school.join_code}', 'success')
    return redirect(url_for('admin_school_detail', school_id=school_id))


@app.route('/admin/courses/<int:course_id>/delete', methods=['POST'])
@login_required
@role_required('admin_teacher', 'admin')
def admin_delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    require_school_role(course.school_id, 'admin_teacher')
    school_id = course.school_id
    name = course.name
    for module in course.modules.all():
        # Clean up dependent records before deleting ModuleExercise
        me_ids = [me.id for me in ModuleExercise.query.filter_by(module_id=module.id).all()]
        if me_ids:
            ModuleCompletion.query.filter(ModuleCompletion.module_exercise_id.in_(me_ids)).delete(synchronize_session=False)
            SectionModuleExercise.query.filter(SectionModuleExercise.module_exercise_id.in_(me_ids)).delete(synchronize_session=False)
        ModuleExercise.query.filter_by(module_id=module.id).delete()
        db.session.delete(module)
    db.session.delete(course)
    db.session.commit()
    flash(f'Course "{name}" deleted.', 'success')
    return redirect(url_for('admin_courses', school_id=school_id))


@app.route('/admin/courses/<int:course_id>/rename', methods=['POST'])
@login_required
@role_required('admin_teacher', 'admin')
def admin_rename_course(course_id):
    course = Course.query.get_or_404(course_id)
    require_school_role(course.school_id, 'admin_teacher')
    name = request.form.get('name', '').strip()
    if name:
        course.name = name
        db.session.commit()
        flash(f'Course renamed to "{name}".', 'success')
    return redirect(url_for('admin_courses', school_id=course.school_id))


@app.route('/admin/courses/<int:course_id>/duplicate', methods=['POST'])
@login_required
@role_required('admin_teacher', 'admin')
def admin_duplicate_course(course_id):
    src = Course.query.get_or_404(course_id)
    require_school_role(src.school_id, 'admin_teacher')
    new_course = Course(name=f'{src.name} (copy)', school_id=src.school_id)
    db.session.add(new_course)
    db.session.flush()
    for mod in src.modules.order_by(Module.order):
        new_mod = Module(name=mod.name, course_id=new_course.id, order=mod.order)
        db.session.add(new_mod)
        db.session.flush()
        for ex in mod.exercises:
            new_ex = ModuleExercise(
                module_id=new_mod.id,
                exercise_type=ex.exercise_type,
                exercise_id=ex.exercise_id,
                name=ex.name,
                params_json=ex.params_json,
                order=ex.order,
                completion_criterion_json=ex.completion_criterion_json,
            )
            db.session.add(new_ex)
    db.session.commit()
    flash(f'Duplicated "{src.name}".', 'success')
    return redirect(url_for('admin_courses', school_id=src.school_id))


@app.route('/admin/courses/<int:course_id>/sections')
@login_required
@role_required('admin_teacher', 'admin')
def admin_course_sections(course_id):
    course = Course.query.get_or_404(course_id)
    require_school_role(course.school_id, 'admin_teacher')
    sections = Section.query.filter_by(course_id=course_id).all()
    return render_template('admin/course_sections.html',
                           course=course, sections=sections)


@app.route('/admin/modules/<int:module_id>/delete', methods=['POST'])
@login_required
@role_required('admin_teacher', 'admin')
def admin_delete_module(module_id):
    module = Module.query.get_or_404(module_id)
    require_school_role(module.course.school_id, 'admin_teacher')
    course_id = module.course_id
    name = module.name
    # Clean up dependent records before deleting ModuleExercise
    me_ids = [me.id for me in ModuleExercise.query.filter_by(module_id=module.id).all()]
    if me_ids:
        ModuleCompletion.query.filter(ModuleCompletion.module_exercise_id.in_(me_ids)).delete(synchronize_session=False)
        SectionModuleExercise.query.filter(SectionModuleExercise.module_exercise_id.in_(me_ids)).delete(synchronize_session=False)
    ModuleExercise.query.filter_by(module_id=module.id).delete()
    db.session.delete(module)
    db.session.commit()
    flash(f'Module "{name}" deleted.', 'success')
    return redirect(url_for('admin_modules', course_id=course_id))


# ── Melody CMS ──────────────────────────────────────────────────────────────

@app.route('/admin/melodies')
@login_required
@role_required('admin')
def admin_melodies():
    q = request.args.get('q', '').strip()
    tag_filter = request.args.get('tag', '').strip()
    container_filter = request.args.get('container', type=int)
    query = Melody.query
    if q:
        query = query.filter(db.or_(Melody.name.ilike(f'%{q}%'), Melody.public_id.ilike(f'%{q}%')))
    if tag_filter:
        query = query.filter(Melody.tags.any(Tag.name == tag_filter))
    if container_filter:
        query = query.filter_by(container_id=container_filter)
    melodies = query.order_by(Melody.id.desc()).all()
    all_tags = Tag.query.order_by(Tag.name).all()
    containers = Container.query.order_by(Container.name).all()
    return render_template('admin/melodies.html', melodies=melodies, all_tags=all_tags,
                           containers=containers, q=q, tag_filter=tag_filter,
                           container_filter=container_filter)


@app.route('/admin/melodies/<int:mel_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_edit_melody(mel_id):
    mel = Melody.query.get_or_404(mel_id)
    all_tags = Tag.query.order_by(Tag.name).all()
    containers = Container.query.order_by(Container.name).all()
    if request.method == 'POST':
        mel.name          = request.form.get('name', '').strip() or mel.name
        mel.description   = request.form.get('description', '').strip()
        mel.key_signature = request.form.get('key_signature', mel.key_signature)
        mel.time_signature = request.form.get('time_signature', mel.time_signature)
        mel.clef          = request.form.get('clef', mel.clef)
        mel.min_duration  = request.form.get('min_duration', mel.min_duration)
        mel.tempo         = request.form.get('tempo', mel.tempo, type=int) or mel.tempo
        mel.difficulty    = request.form.get('difficulty', mel.difficulty, type=int) or mel.difficulty
        mel.visibility    = request.form.get('visibility', mel.visibility)
        mel.container_id  = request.form.get('container_id', type=int) or None
        tag_ids = request.form.getlist('tag_ids', type=int)
        mel.tags = Tag.query.filter(Tag.id.in_(tag_ids)).all() if tag_ids else []
        notes_raw = request.form.get('notes_json', '').strip()
        if notes_raw:
            try:
                json.loads(notes_raw)
                mel.notes_json = notes_raw
            except ValueError:
                flash('Invalid notes JSON — not saved.', 'warning')
        db.session.commit()
        flash('Melody updated.', 'success')
        return redirect(url_for('admin_edit_melody', mel_id=mel_id))
    return render_template('admin/melody_edit.html', mel=mel, all_tags=all_tags, containers=containers)


@app.route('/admin/melodies/<int:mel_id>/delete', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_delete_melody(mel_id):
    mel = Melody.query.get_or_404(mel_id)
    if request.method == 'POST':
        db.session.delete(mel)
        db.session.commit()
        flash(f'Melody "{mel.name}" deleted.', 'success')
        return redirect(url_for('admin_melodies'))
    return render_template('admin/confirm_delete.html', item_type='Melody', item_name=mel.name,
                           cancel_url=url_for('admin_melodies'))


@app.route('/admin/melodies/upload', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_melody_upload():
    if request.method == 'GET':
        return render_template('admin/melody_upload.html')
    # POST — parse uploaded MIDI
    f = request.files.get('midi_file')
    if not f or not f.filename or not f.filename.endswith('.mid'):
        flash('Please upload a .mid file.', 'danger')
        return redirect(url_for('admin_melody_upload'))
    name = request.form.get('name', '').strip() or f.filename.rsplit('.', 1)[0]
    key  = request.form.get('key_signature', 'C').strip()
    time_sig = request.form.get('time_signature', '').strip()
    tempo_raw = request.form.get('tempo', '').strip()
    if not time_sig:
        flash('Time signature is required.', 'danger')
        return redirect(url_for('admin_melody_upload'))
    if not tempo_raw.isdigit():
        flash('BPM is required and must be a number.', 'danger')
        return redirect(url_for('admin_melody_upload'))
    from midi_to_notes import extract_notes, build_json_list
    import tempfile, re, shutil

    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.mid')
        with os.fdopen(tmp_fd, 'wb') as tmp_f:
            f.save(tmp_f)
        notes     = extract_notes(tmp_path)
        note_list = build_json_list(notes, key)
        base_slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'melody'
        mel = Melody(
            name=name,
            midi_filename='',  # set after flush
            notes_json=json.dumps(note_list),
            key_signature=key,
            time_signature=time_sig,
            tempo=int(tempo_raw),
        )
        db.session.add(mel)
        db.session.flush()
        mel.public_id = f'MEL-{mel.id:04d}'
        slug = f'{base_slug}-{mel.id}'
        dest_dir  = os.path.join(app.static_folder, 'melodic', slug)
        os.makedirs(dest_dir, exist_ok=True)
        midi_dest = os.path.join(dest_dir, f'{slug}.mid')
        shutil.copy(tmp_path, midi_dest)
        mel.midi_filename = f'melodic/{slug}/{slug}.mid'
        db.session.commit()
        flash(f'Melody "{mel.name}" uploaded ({mel.public_id}).', 'success')
        return redirect(url_for('admin_edit_melody', mel_id=mel.id))
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ── Melody Generator ─────────────────────────────────────────────────────────

@app.route('/admin/melodies/generate', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_melody_generator():
    import melody_generator as mg
    gen_progressions = GenProgression.query.order_by(GenProgression.number).all()
    all_tags   = Tag.query.order_by(Tag.name).all()
    containers = Container.query.order_by(Container.name).all()

    if request.method == 'GET':
        last_params = session.get('generator_params', {})
        return render_template('admin/melody_generator.html',
                               gen_progressions=gen_progressions,
                               all_tags=all_tags, containers=containers,
                               last_params=last_params, preview=None)

    # POST: generate
    gp_id = request.form.get('gen_progression_id', type=int)
    gp    = GenProgression.query.get(gp_id) if gp_id else None
    if not gp:
        flash('Please select a GenProgression.', 'danger')
        return redirect(url_for('admin_melody_generator'))

    key          = request.form.get('key', 'C')
    mode         = request.form.get('mode', 'major')
    time_sig     = request.form.get('time_sig', '4/4')
    num_measures = request.form.get('num_measures', 4, type=int)
    min_duration = request.form.get('min_duration', 'q')
    clef         = request.form.get('clef', 'treble')
    tempo        = request.form.get('tempo', 100, type=int)
    complexity   = request.form.get('rhythm_complexity', 1, type=int)
    syncopation  = request.form.get('syncopation') == 'on'
    techniques   = request.form.getlist('techniques')
    seed_raw     = request.form.get('seed', '').strip()
    seed         = int(seed_raw) if seed_raw.isdigit() else None

    start_midi = request.form.get('start_midi', type=int) or 64
    high_midi  = request.form.get('high_midi',  type=int) or 72
    low_midi   = request.form.get('low_midi',   type=int) or 60

    params = {
        'key': key, 'mode': mode,
        'gen_progression_chords': gp.chords,
        'gen_prog_difficulty': gp.difficulty,
        'time_sig': time_sig, 'num_measures': num_measures,
        'min_duration': min_duration, 'clef': clef, 'tempo': tempo,
        'start_midi': start_midi, 'high_midi': high_midi, 'low_midi': low_midi,
        'techniques': techniques, 'rhythm_complexity': complexity,
        'syncopation': syncopation, 'seed': seed,
    }

    try:
        result = mg.generate(params)
    except Exception as e:
        flash(f'Generation error: {e}', 'danger')
        return redirect(url_for('admin_melody_generator'))

    session['pending_melody'] = {
        'notes_json':            result['notes_json'],
        'midi_path':             result['midi_path'],
        'difficulty_suggestion': result['difficulty_suggestion'],
        'auto_tags':             result['auto_tags'],
        'generation_params':     result['generation_params'],
        'gp_id': gp_id,
    }
    session['generator_params'] = request.form.to_dict(flat=False)

    preview = {
        'notes_json':            result['notes_json'],
        'midi_url':              url_for('static', filename=result['midi_path']),
        'difficulty_suggestion': result['difficulty_suggestion'],
        'auto_tags':             result['auto_tags'],
    }
    return render_template('admin/melody_generator.html',
                           gen_progressions=gen_progressions,
                           all_tags=all_tags, containers=containers,
                           last_params=request.form.to_dict(flat=False),
                           preview=preview)


@app.route('/admin/melodies/approve', methods=['POST'])
@login_required
@role_required('admin')
def admin_melody_approve():
    pending = session.pop('pending_melody', None)
    if not pending:
        flash('No pending melody to approve.', 'warning')
        return redirect(url_for('admin_melody_generator'))

    name = request.form.get('name', '').strip()
    if not name:
        flash('Name is required.', 'danger')
        session['pending_melody'] = pending
        return redirect(url_for('admin_melody_generator'))

    src_path  = os.path.join(app.static_folder, pending['midi_path'].replace('/', os.sep))

    difficulty   = request.form.get('difficulty', pending['difficulty_suggestion'], type=int)
    container_id = request.form.get('container_id', type=int) or None

    tag_ids      = request.form.getlist('tag_ids', type=int)
    manual_tags  = Tag.query.filter(Tag.id.in_(tag_ids)).all() if tag_ids else []

    # Create Melody WITHOUT public_id; we'll set it after flush to get the auto-assigned ID
    mel = Melody(
        name=name,
        description=request.form.get('description', '').strip(),
        # midi_filename will be set after we know the slug
        notes_json=pending['notes_json'],
        key_signature=pending['generation_params']['key'],
        time_signature=pending['generation_params']['time_sig'],
        clef=pending['generation_params']['clef'],
        min_duration=pending['generation_params']['min_duration'],
        tempo=pending['generation_params'].get('tempo', 100),
        difficulty=difficulty,
        container_id=container_id,
        generation_params=json.dumps(pending['generation_params']),
    )
    mel.tags = manual_tags

    for tag_name in pending['auto_tags']:
        tag = Tag.query.filter_by(name=tag_name).first()
        if tag and tag not in mel.tags:
            mel.tags.append(tag)

    db.session.add(mel)
    db.session.flush()  # Get the auto-assigned mel.id

    # Now set public_id and slug based on the actual ID
    public_id = f'MEL-{mel.id:04d}'
    slug      = f'mel_{public_id.lower().replace("-", "_")}'
    dest_dir  = os.path.join(app.static_folder, 'melodic', slug)
    dest_name = f'{slug}.mid'
    os.makedirs(dest_dir, exist_ok=True)
    import shutil
    shutil.copy2(src_path, os.path.join(dest_dir, dest_name))
    midi_filename = f'melodic/{slug}/{dest_name}'

    # Update the Melody object with the correct public_id and midi_filename
    mel.public_id = public_id
    mel.midi_filename = midi_filename

    db.session.commit()
    flash(f'Melody "{name}" saved ({public_id}).', 'success')
    return redirect(url_for('admin_edit_melody', mel_id=mel.id))


@app.route('/admin/melodies/reject', methods=['POST'])
@login_required
@role_required('admin')
def admin_melody_reject():
    session.pop('pending_melody', None)
    flash('Melody discarded. Generate another.', 'info')
    return redirect(url_for('admin_melody_generator'))


# ── Rhythm CMS ───────────────────────────────────────────────────────────────

@app.route('/admin/rhythms')
@login_required
@role_required('admin')
def admin_rhythms():
    q = request.args.get('q', '').strip()
    tag_filter = request.args.get('tag', '').strip()
    diff_filter = request.args.get('difficulty', type=int)
    query = Rhythm.query
    if q:
        query = query.filter(db.or_(Rhythm.name.ilike(f'%{q}%'),
                                    Rhythm.public_id.ilike(f'%{q}%')))
    if tag_filter:
        query = query.filter(Rhythm.tags.any(Tag.name == tag_filter))
    if diff_filter:
        query = query.filter_by(difficulty=diff_filter)
    rhythms = query.order_by(Rhythm.id.desc()).all()
    all_tags = Tag.query.order_by(Tag.name).all()
    return render_template('admin/rhythms.html', rhythms=rhythms,
                           all_tags=all_tags, q=q, tag_filter=tag_filter, diff_filter=diff_filter)


@app.route('/admin/rhythms/<int:rhythm_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_edit_rhythm(rhythm_id):
    rhythm = Rhythm.query.get_or_404(rhythm_id)
    all_tags = Tag.query.order_by(Tag.name).all()
    if request.method == 'POST':
        rhythm.name          = request.form.get('name', '').strip() or rhythm.name
        rhythm.description   = request.form.get('description', '').strip()
        rhythm.time_signature = request.form.get('time_signature', rhythm.time_signature)
        rhythm.min_duration  = request.form.get('min_duration', rhythm.min_duration)
        rhythm.difficulty    = request.form.get('difficulty', rhythm.difficulty, type=int) or rhythm.difficulty
        rhythm.tempo         = request.form.get('tempo', rhythm.tempo, type=int) or rhythm.tempo
        rhythm.visibility    = request.form.get('visibility', rhythm.visibility)
        tag_ids = request.form.getlist('tag_ids', type=int)
        rhythm.tags = Tag.query.filter(Tag.id.in_(tag_ids)).all() if tag_ids else []
        notes_raw = request.form.get('notes_json', '').strip()
        if notes_raw:
            try:
                json.loads(notes_raw)
                rhythm.notes_json = notes_raw
            except ValueError:
                flash('Invalid notes JSON — not saved.', 'warning')
        db.session.commit()
        flash('Rhythm updated.', 'success')
        return redirect(url_for('admin_edit_rhythm', rhythm_id=rhythm_id))
    return render_template('admin/rhythm_edit.html', rhythm=rhythm, all_tags=all_tags)


@app.route('/admin/rhythms/<int:rhythm_id>/delete', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_delete_rhythm(rhythm_id):
    rhythm = Rhythm.query.get_or_404(rhythm_id)
    if request.method == 'POST':
        db.session.delete(rhythm)
        db.session.commit()
        flash(f'Rhythm "{rhythm.name}" deleted.', 'success')
        return redirect(url_for('admin_rhythms'))
    return render_template('admin/confirm_delete.html', item_type='Rhythm',
                           item_name=rhythm.name, cancel_url=url_for('admin_rhythms'))


@app.route('/admin/rhythms/upload', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_rhythm_upload():
    all_tags = Tag.query.order_by(Tag.name).all()
    if request.method == 'GET':
        return render_template('admin/rhythm_upload.html', all_tags=all_tags)
    # POST — parse uploaded MIDI
    f = request.files.get('midi_file')
    if not f or not f.filename or not f.filename.endswith('.mid'):
        flash('Please upload a .mid file.', 'danger')
        return redirect(url_for('admin_rhythm_upload'))
    time_sig = request.form.get('time_signature', '').strip()
    tempo_raw = request.form.get('tempo', '').strip()
    if not time_sig:
        flash('Time signature is required.', 'danger')
        return redirect(url_for('admin_rhythm_upload'))
    if not tempo_raw.isdigit():
        flash('BPM is required and must be a number.', 'danger')
        return redirect(url_for('admin_rhythm_upload'))
    name = request.form.get('name', '').strip() or f.filename.rsplit('.', 1)[0]
    from midi_to_notes import extract_notes, build_json_list
    import tempfile, re, shutil

    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.mid')
        with os.fdopen(tmp_fd, 'wb') as tmp_f:
            f.save(tmp_f)
        notes     = extract_notes(tmp_path)
        note_list = build_json_list(notes, 'C')
        base_slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'rhythm'
        tag_ids = request.form.getlist('tag_ids', type=int)
        rhy = Rhythm(
            name=name,
            notes_json=json.dumps(note_list),
            time_signature=time_sig,
            min_duration=request.form.get('min_duration', 'q'),
            difficulty=request.form.get('difficulty', 1, type=int),
            tempo=int(tempo_raw),
        )
        rhy.tags = Tag.query.filter(Tag.id.in_(tag_ids)).all() if tag_ids else []
        db.session.add(rhy)
        db.session.flush()
        rhy.public_id = f'RHY-{rhy.id:04d}'
        slug = f'{base_slug}-{rhy.id}'
        dest_dir  = os.path.join(app.static_folder, 'rhythmic', slug)
        os.makedirs(dest_dir, exist_ok=True)
        midi_dest = os.path.join(dest_dir, f'{slug}.mid')
        shutil.copy(tmp_path, midi_dest)
        db.session.commit()
        flash(f'Rhythm "{rhy.name}" uploaded ({rhy.public_id}).', 'success')
        return redirect(url_for('admin_edit_rhythm', rhythm_id=rhy.id))
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ── Holistic Exercise CMS ────────────────────────────────────────────────────

@app.route('/admin/holistic')
@login_required
@role_required('admin')
def admin_holistic():
    q = request.args.get('q', '').strip()
    tag_filter = request.args.get('tag', '').strip()
    diff_filter = request.args.get('difficulty', type=int)
    query = HolisticExercise.query
    if q:
        query = query.filter(db.or_(HolisticExercise.name.ilike(f'%{q}%'), HolisticExercise.public_id.ilike(f'%{q}%')))
    if tag_filter:
        query = query.filter(HolisticExercise.tags.any(Tag.name == tag_filter))
    if diff_filter:
        query = query.filter_by(difficulty=diff_filter)
    exercises = query.order_by(HolisticExercise.id.desc()).all()
    all_tags = Tag.query.order_by(Tag.name).all()
    return render_template('admin/holistic_list.html', exercises=exercises, all_tags=all_tags,
                           q=q, tag_filter=tag_filter, diff_filter=diff_filter)


@app.route('/admin/holistic/<int:ex_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_edit_holistic(ex_id):
    h = HolisticExercise.query.get_or_404(ex_id)
    all_tags = Tag.query.order_by(Tag.name).all()
    if request.method == 'POST':
        h.name           = request.form.get('name', '').strip() or h.name
        h.description    = request.form.get('description', '').strip()
        h.key_signature  = request.form.get('key_signature', h.key_signature)
        time_sig = request.form.get('time_signature', '').strip()
        tempo_raw = request.form.get('tempo', '').strip()
        if not time_sig:
            flash('Time signature is required.', 'danger')
            return redirect(url_for('admin_edit_holistic', ex_id=ex_id))
        if not tempo_raw.isdigit():
            flash('BPM is required and must be a number.', 'danger')
            return redirect(url_for('admin_edit_holistic', ex_id=ex_id))
        h.time_signature = time_sig
        h.tempo          = int(tempo_raw)
        h.difficulty     = request.form.get('difficulty', h.difficulty, type=int) or h.difficulty
        h.visibility     = request.form.get('visibility', h.visibility)
        tag_ids = request.form.getlist('tag_ids', type=int)
        h.tags = Tag.query.filter(Tag.id.in_(tag_ids)).all() if tag_ids else []
        db.session.commit()
        flash('Exercise updated.', 'success')
        return redirect(url_for('admin_edit_holistic', ex_id=ex_id))
    lines = h.lines
    return render_template('admin/holistic_edit.html', h=h, all_tags=all_tags, lines=lines)


@app.route('/admin/holistic/<int:ex_id>/lines/add', methods=['POST'])
@login_required
@role_required('admin')
def admin_add_holistic_line(ex_id):
    h = HolisticExercise.query.get_or_404(ex_id)
    name = request.form.get('name', '').strip()
    line_type = request.form.get('line_type', '').strip()
    clef = request.form.get('clef', 'treble').strip() if line_type == 'melody' else None
    f = request.files.get('midi_file')
    if not name or line_type not in ('melody', 'rhythm', 'harmonic'):
        flash('Line name and a valid type are required.', 'danger')
        return redirect(url_for('admin_edit_holistic', ex_id=ex_id))
    if not f or not f.filename or not f.filename.lower().endswith('.mid'):
        flash('Please upload a .mid file for this line.', 'danger')
        return redirect(url_for('admin_edit_holistic', ex_id=ex_id))

    import tempfile, shutil
    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.mid')
    try:
        with os.fdopen(tmp_fd, 'wb') as tmp_f:
            f.save(tmp_f)
        if line_type == 'harmonic':
            from chord_utils import infer_chords_from_midi
            content = infer_chords_from_midi(tmp_path, h.key_signature)
        else:
            from midi_to_notes import extract_notes, build_json_list
            notes = extract_notes(tmp_path)
            content = build_json_list(notes, h.key_signature)

        next_order = (max((l.order for l in h.lines), default=-1)) + 1
        dest_dir = os.path.join(app.static_folder, h.folder)
        os.makedirs(dest_dir, exist_ok=True)
        midi_dest_name = f'line-{next_order}.mid'
        shutil.copy(tmp_path, os.path.join(dest_dir, midi_dest_name))

        line = HolisticLine(
            holistic_exercise_id=h.id, line_type=line_type, name=name,
            order=next_order, clef=clef,
            midi_filename=h.folder.rstrip('/') + '/' + midi_dest_name,
            content_json=json.dumps(content),
        )
        db.session.add(line)
        db.session.commit()
        flash(f'Line "{name}" added.', 'success')
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return redirect(url_for('admin_edit_holistic', ex_id=ex_id))


@app.route('/admin/holistic/<int:ex_id>/lines/reorder', methods=['POST'])
@login_required
@role_required('admin')
def admin_reorder_holistic_lines(ex_id):
    h = HolisticExercise.query.get_or_404(ex_id)
    order_data = request.get_json(silent=True) or {}
    line_ids = order_data.get('line_ids', [])
    line_map = {l.id: l for l in h.lines}
    for idx, lid in enumerate(line_ids):
        if lid in line_map:
            line_map[lid].order = idx
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/admin/holistic/lines/<int:line_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_holistic_line(line_id):
    line = HolisticLine.query.get_or_404(line_id)
    ex_id = line.holistic_exercise_id
    db.session.delete(line)
    db.session.commit()
    flash('Line removed.', 'success')
    return redirect(url_for('admin_edit_holistic', ex_id=ex_id))


@app.route('/admin/holistic/<int:ex_id>/delete', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_delete_holistic(ex_id):
    h = HolisticExercise.query.get_or_404(ex_id)
    if request.method == 'POST':
        db.session.delete(h)
        db.session.commit()
        flash(f'Exercise "{h.name}" deleted.', 'success')
        return redirect(url_for('admin_holistic'))
    return render_template('admin/confirm_delete.html', item_type='Holistic Exercise',
                           item_name=h.name, cancel_url=url_for('admin_holistic'))


@app.route('/admin/holistic/upload', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_holistic_upload():
    if request.method == 'GET':
        return render_template('admin/holistic_upload.html')
    # POST — accept WAV only; lines are added afterward on the edit page.
    wav_file = request.files.get('wav_file')
    if not wav_file or not wav_file.filename or not wav_file.filename.lower().endswith('.wav'):
        flash('Please upload a .wav file.', 'danger')
        return redirect(url_for('admin_holistic_upload'))

    import re, shutil, tempfile
    name = request.form.get('name', '').strip() or wav_file.filename.rsplit('.', 1)[0]
    key  = request.form.get('key_signature', 'C').strip()
    time_sig = request.form.get('time_signature', '').strip()
    tempo_raw = request.form.get('tempo', '').strip()
    if not time_sig:
        flash('Time signature is required.', 'danger')
        return redirect(url_for('admin_holistic_upload'))
    if not tempo_raw.isdigit():
        flash('BPM is required and must be a number.', 'danger')
        return redirect(url_for('admin_holistic_upload'))
    base_slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'holistic'

    wav_tmp_fd, wav_tmp_path = tempfile.mkstemp(suffix='.wav')
    with os.fdopen(wav_tmp_fd, 'wb') as _wf:
        wav_file.save(_wf)

    h = HolisticExercise(
        name=name,
        folder='',  # set after flush
        wav_filename='',  # set after flush
        key_signature=key,
        time_signature=time_sig,
        tempo=int(tempo_raw),
    )
    db.session.add(h)
    db.session.flush()
    h.public_id = f'HOL-{h.id:04d}'
    slug = f'{base_slug}-{h.id}'
    dest_dir = os.path.join(app.static_folder, 'holistic', slug)
    os.makedirs(dest_dir, exist_ok=True)

    wav_dest = os.path.join(dest_dir, f'{slug}.wav')
    shutil.copy(wav_tmp_path, wav_dest)
    try:
        os.unlink(wav_tmp_path)
    except OSError:
        pass

    h.folder = f'holistic/{slug}/'
    h.wav_filename = f'{slug}.wav'
    db.session.commit()
    flash(f'Exercise "{h.name}" uploaded ({h.public_id}). Now add lines below.', 'success')
    return redirect(url_for('admin_edit_holistic', ex_id=h.id))


# ── GenProgression CMS ───────────────────────────────────────────────────────

@app.route('/admin/gen-progressions', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_gen_progressions():
    if request.method == 'POST':
        chords_raw = request.form.get('chords_json', '[]').strip()
        try:
            json.loads(chords_raw)
        except ValueError:
            flash('Invalid JSON in chords field.', 'danger')
            return redirect(url_for('admin_gen_progressions'))
        last = GenProgression.query.order_by(GenProgression.number.desc()).first()
        next_num = (last.number + 1) if last else 1
        gp = GenProgression(
            number=request.form.get('number', next_num, type=int),
            name=request.form.get('name', '').strip(),
            length_bars=request.form.get('length_bars', 4, type=int),
            mode=request.form.get('mode', 'major'),
            difficulty=request.form.get('difficulty', 1, type=int),
            chords_json=chords_raw,
        )
        db.session.add(gp)
        db.session.commit()
        flash(f'GenProgression #{gp.number} created.', 'success')
        return redirect(url_for('admin_edit_gen_progression', gp_id=gp.id))

    q = request.args.get('q', '').strip()
    mode_filter = request.args.get('mode', '').strip()
    diff_filter = request.args.get('difficulty', type=int)
    query = GenProgression.query
    if q:
        query = query.filter(GenProgression.name.ilike(f'%{q}%'))
    if mode_filter:
        query = query.filter_by(mode=mode_filter)
    if diff_filter:
        query = query.filter_by(difficulty=diff_filter)
    progressions = query.order_by(GenProgression.number).all()
    return render_template('admin/gen_progressions.html', progressions=progressions,
                           q=q, mode_filter=mode_filter, diff_filter=diff_filter)


@app.route('/admin/gen-progressions/<int:gp_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_edit_gen_progression(gp_id):
    gp = GenProgression.query.get_or_404(gp_id)
    if request.method == 'POST':
        chords_raw = request.form.get('chords_json', gp.chords_json).strip()
        try:
            json.loads(chords_raw)
        except ValueError:
            flash('Invalid JSON in chords field.', 'danger')
            return redirect(url_for('admin_edit_gen_progression', gp_id=gp_id))
        gp.number      = request.form.get('number', gp.number, type=int)
        gp.name        = request.form.get('name', '').strip() or gp.name
        gp.length_bars = request.form.get('length_bars', gp.length_bars, type=int)
        gp.mode        = request.form.get('mode', gp.mode)
        gp.difficulty  = request.form.get('difficulty', gp.difficulty, type=int)
        gp.chords_json = chords_raw
        db.session.commit()
        flash('GenProgression updated.', 'success')
        return redirect(url_for('admin_edit_gen_progression', gp_id=gp_id))
    return render_template('admin/gen_progression_edit.html', gp=gp)


@app.route('/admin/gen-progressions/<int:gp_id>/delete', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_delete_gen_progression(gp_id):
    gp = GenProgression.query.get_or_404(gp_id)
    if request.method == 'POST':
        db.session.delete(gp)
        db.session.commit()
        flash(f'GenProgression #{gp.number} deleted.', 'success')
        return redirect(url_for('admin_gen_progressions'))
    return render_template('admin/confirm_delete.html',
                           item_type='GenProgression',
                           item_name=f'#{gp.number} {gp.name or ""}',
                           cancel_url=url_for('admin_gen_progressions'))


# ── Harmonic (ChordProgression) CMS ─────────────────────────────────────────

@app.route('/admin/harmonics')
@login_required
@role_required('admin')
def admin_harmonics():
    q = request.args.get('q', '').strip()
    tag_filter = request.args.get('tag', '').strip()
    diff_filter = request.args.get('difficulty', type=int)
    query = ChordProgression.query
    if q:
        query = query.filter(db.or_(ChordProgression.name.ilike(f'%{q}%'),
                                    ChordProgression.public_id.ilike(f'%{q}%')))
    if tag_filter:
        query = query.filter(ChordProgression.tags.any(Tag.name == tag_filter))
    if diff_filter:
        query = query.filter_by(difficulty=diff_filter)
    progressions = query.order_by(ChordProgression.id.desc()).all()
    all_tags = Tag.query.order_by(Tag.name).all()
    return render_template('admin/harmonics.html', progressions=progressions,
                           all_tags=all_tags, q=q, tag_filter=tag_filter, diff_filter=diff_filter)


@app.route('/admin/harmonics/<int:prog_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_edit_harmonic(prog_id):
    prog = ChordProgression.query.get_or_404(prog_id)
    all_tags = Tag.query.order_by(Tag.name).all()
    if request.method == 'POST':
        prog.name          = request.form.get('name', '').strip() or prog.name
        prog.description   = request.form.get('description', '').strip()
        prog.key_signature = request.form.get('key_signature', prog.key_signature)
        tempo_raw = request.form.get('tempo', '').strip()
        if not tempo_raw.isdigit():
            flash('BPM is required and must be a number.', 'danger')
            return redirect(url_for('admin_edit_harmonic', prog_id=prog_id))
        prog.tempo          = int(tempo_raw)
        prog.difficulty    = request.form.get('difficulty', prog.difficulty, type=int) or prog.difficulty
        prog.visibility    = request.form.get('visibility', prog.visibility)
        prog.category      = request.form.get('category', prog.category)
        tag_ids = request.form.getlist('tag_ids', type=int)
        prog.tags = Tag.query.filter(Tag.id.in_(tag_ids)).all() if tag_ids else []
        chords_raw = request.form.get('chords_json', '').strip()
        if chords_raw:
            try:
                json.loads(chords_raw)
                prog.chords_json = chords_raw
            except ValueError:
                flash('Invalid chords JSON — not saved.', 'warning')
        db.session.commit()
        flash('Progression updated.', 'success')
        return redirect(url_for('admin_edit_harmonic', prog_id=prog_id))
    return render_template('admin/harmonic_edit.html', prog=prog, all_tags=all_tags)


@app.route('/admin/harmonics/<int:prog_id>/delete', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_delete_harmonic(prog_id):
    prog = ChordProgression.query.get_or_404(prog_id)
    if request.method == 'POST':
        db.session.delete(prog)
        db.session.commit()
        flash(f'Progression "{prog.name}" deleted.', 'success')
        return redirect(url_for('admin_harmonics'))
    return render_template('admin/confirm_delete.html', item_type='Chord Progression',
                           item_name=prog.name, cancel_url=url_for('admin_harmonics'))


@app.route('/admin/harmonics/upload', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_harmonic_upload():
    all_tags = Tag.query.order_by(Tag.name).all()
    if request.method == 'GET':
        return render_template('admin/harmonic_upload.html', all_tags=all_tags)
    # POST — parse uploaded MIDI
    f = request.files.get('midi_file')
    if not f or not f.filename or not f.filename.endswith('.mid'):
        flash('Please upload a .mid file.', 'danger')
        return redirect(url_for('admin_harmonic_upload'))
    name = request.form.get('name', '').strip() or f.filename.rsplit('.', 1)[0]
    key  = request.form.get('key_signature', 'C').strip()
    tempo_raw = request.form.get('tempo', '').strip()
    if not tempo_raw.isdigit():
        flash('BPM is required and must be a number.', 'danger')
        return redirect(url_for('admin_harmonic_upload'))
    from chord_utils import infer_chords_from_midi
    import tempfile, re, shutil

    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.mid')
        with os.fdopen(tmp_fd, 'wb') as tmp_f:
            f.save(tmp_f)
        chords_list = infer_chords_from_midi(tmp_path, key)
        base_slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'progression'
        tag_ids = request.form.getlist('tag_ids', type=int)
        prog = ChordProgression(
            name=name,
            midi_filename='',  # set after flush
            chords_json=json.dumps(chords_list),
            key_signature=key,
            difficulty=request.form.get('difficulty', 1, type=int),
            category=request.form.get('category', 'diatonic'),
            tempo=int(tempo_raw),
        )
        prog.tags = Tag.query.filter(Tag.id.in_(tag_ids)).all() if tag_ids else []
        db.session.add(prog)
        db.session.flush()
        prog.public_id = f'HRM-{prog.id:04d}'
        slug = f'{base_slug}-{prog.id}'
        dest_dir  = os.path.join(app.static_folder, 'harmonic', slug)
        os.makedirs(dest_dir, exist_ok=True)
        midi_dest = os.path.join(dest_dir, f'{slug}.mid')
        shutil.copy(tmp_path, midi_dest)
        prog.midi_filename = f'harmonic/{slug}/{slug}.mid'
        db.session.commit()
        flash(f'Progression "{prog.name}" uploaded ({prog.public_id}).', 'success')
        return redirect(url_for('admin_edit_harmonic', prog_id=prog.id))
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@app.route('/teacher/sections/<int:section_id>/delete', methods=['GET', 'POST'])
@login_required
@role_required('admin_teacher', 'admin')
def teacher_delete_section(section_id):
    section = Section.query.get_or_404(section_id)
    require_manage_section(section)
    if request.method == 'GET':
        return render_template('teacher/confirm_delete_section.html', section=section)
    name = section.name
    ModuleCompletion.query.filter_by(section_id=section_id).delete()
    SectionModuleExercise.query.filter_by(section_id=section_id).delete()
    section.members.clear()
    db.session.flush()
    db.session.delete(section)
    db.session.commit()
    flash(f'Section "{name}" deleted.', 'success')
    return redirect(url_for('teacher_dashboard'))


@app.route('/teacher/section/<int:section_id>/kick/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin_teacher', 'class_teacher', 'admin')
def teacher_kick_student(section_id, user_id):
    section = Section.query.get_or_404(section_id)
    require_section_role(section, 'class_teacher')
    student = User.query.get_or_404(user_id)
    if request.method == 'GET':
        return render_template('teacher/confirm_kick_student.html', section=section, student=student)
    if student in section.members:
        section.members.remove(student)
        db.session.commit()
        flash(f'{student.display_name or student.email} removed from {section.name}.', 'success')
    return redirect(url_for('teacher_section_detail', section_id=section_id))


@app.route('/section/<int:section_id>/leave', methods=['POST'])
@login_required
def leave_section(section_id):
    section = Section.query.get_or_404(section_id)
    if current_user not in section.members:
        flash(f'You are not in this {section_word()}.', 'info')
    else:
        section.members.remove(current_user)
        db.session.commit()
        flash(f'Left "{section.name}".', 'success')
    return redirect(url_for('my_sections'))


@app.route('/me')
@login_required
def me():
    uid  = current_user.id
    days = request.args.get('days', '30')
    try:
        days_int = int(days)
    except (ValueError, TypeError):
        days_int = 30

    if days_int > 0:
        cutoff = datetime.utcnow() - timedelta(days=days_int)
        mel_q  = UserAttempt.query.filter(UserAttempt.user_id == uid, UserAttempt.created_at >= cutoff)
        rhy_q  = RhythmAttempt.query.filter(RhythmAttempt.user_id == uid, RhythmAttempt.created_at >= cutoff)
        har_q  = HarmonicAttempt.query.filter(HarmonicAttempt.user_id == uid, HarmonicAttempt.created_at >= cutoff)
        hol_q  = HolisticAttempt.query.filter(HolisticAttempt.user_id == uid, HolisticAttempt.created_at >= cutoff)
    else:
        mel_q  = UserAttempt.query.filter_by(user_id=uid)
        rhy_q  = RhythmAttempt.query.filter_by(user_id=uid)
        har_q  = HarmonicAttempt.query.filter_by(user_id=uid)
        hol_q  = HolisticAttempt.query.filter_by(user_id=uid)

    melody_attempts   = mel_q.order_by(UserAttempt.created_at.desc()).all()
    rhythm_attempts   = rhy_q.order_by(RhythmAttempt.created_at.desc()).all()
    harmonic_attempts = har_q.order_by(HarmonicAttempt.created_at.desc()).all()
    holistic_attempts = hol_q.order_by(HolisticAttempt.created_at.desc()).all()

    def avg(attempts, field='overall_score'):
        vals = [getattr(a, field) for a in attempts if getattr(a, field) is not None]
        return round(sum(vals) / len(vals)) if vals else None

    stats = {
        'melodic':  {'count': len(melody_attempts),   'avg': avg(melody_attempts)},
        'rhythmic': {'count': len(rhythm_attempts),   'avg': avg(rhythm_attempts, 'duration_accuracy')},
        'harmonic': {'count': len(harmonic_attempts), 'avg': avg(harmonic_attempts)},
        'holistic': {'count': len(holistic_attempts), 'avg': avg(holistic_attempts)},
    }

    module_progress_by_section = []
    for section in current_user.sections:
        mods = cur.modules_with_progress(current_user.id, section.id, section)
        if mods:
            module_progress_by_section.append({'section': section, 'modules': mods})

    return render_template('me.html',
                           stats=stats,
                           days=days_int,
                           module_progress_by_section=module_progress_by_section)


@app.route('/teacher')
@login_required
@role_required('admin_teacher', 'class_teacher', 'admin')
def teacher_dashboard():
    if active_role() == 'class_teacher':
        sections = Section.query.filter_by(assigned_teacher_id=current_user.id).all()
    else:
        sections = Section.query.filter_by(teacher_id=current_user.id).all()
    return render_template('teacher/dashboard.html', sections=sections,
                           can_create_section=bool(administered_schools()))


@app.route('/admin/my-school')
@login_required
@role_required('admin_teacher', 'admin')
def admin_my_school():
    """Entry point for the nav's "Admin" link.

    BUG-003 lived here: this used to send an admin_teacher to admin_courses,
    which was site-admin-only, so they 403'd out of their own nav bar. It now
    lands on the school detail page — which they can actually use — and
    admin_courses is open to school admins anyway.
    """
    mem = SchoolMembership.query.filter_by(
        user_id=current_user.id, role='admin_teacher'
    ).first()
    if mem:
        return redirect(url_for('admin_school_detail', school_id=mem.school_id))
    if active_role() == 'admin':
        return redirect(url_for('admin_schools'))
    # A staff member with no admin_teacher membership anywhere.
    flash('You are not a school administrator of any school yet.', 'info')
    return redirect(url_for('home'))


@app.route('/my-sections')
@login_required
def my_sections():
    school_memberships = SchoolMembership.query.filter_by(
        user_id=current_user.id
    ).all()
    return render_template('student/my_sections.html',
                           sections=current_user.sections,
                           school_memberships=school_memberships)


@app.route('/join-school', methods=['POST'])
@login_required
def join_school():
    code = request.form.get('school_code', '').strip()
    school = School.query.filter_by(join_code=code).first()
    if not school:
        flash('Invalid school join code.', 'danger')
        return redirect(url_for('my_sections'))
    exists = SchoolMembership.query.filter_by(
        school_id=school.id, user_id=current_user.id
    ).first()
    if exists:
        flash(f'You are already a member of "{school.name}".', 'info')
        return redirect(url_for('my_sections'))
    db.session.add(SchoolMembership(
        school_id=school.id,
        user_id=current_user.id,
        role='student',
    ))
    db.session.commit()
    flash(f'Joined school "{school.name}"! Now you can join {section_word(plural=True)} at that school.', 'success')
    return redirect(url_for('my_sections'))


@app.route('/teacher/section/<int:section_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin_teacher', 'class_teacher', 'admin')
def teacher_edit_section(section_id):
    section = Section.query.get_or_404(section_id)
    require_section_role(section, 'class_teacher')
    courses = administered_courses()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        course_id = request.form.get('course_id', type=int)
        if not name:
            flash('Section name is required.', 'danger')
        elif course_id and course_id not in {c.id for c in administered_courses()}:
            flash('That course is not in a school you administer.', 'danger')
        else:
            section.name = name
            section.course_id = course_id or None
            db.session.commit()
            flash(f'{section_word(title=True)} updated.', 'success')
        return redirect(url_for('teacher_edit_section', section_id=section_id))

    # Build module/exercise data for override management
    modules_with_exercises = []
    hidden_ids = {sme.module_exercise_id for sme in section.module_overrides if sme.action == 'hide' and sme.module_exercise_id}
    if section.course_id and section.course:
        for mod in section.course.modules.order_by(Module.order).all():
            exercises = list(mod.exercises.order_by(ModuleExercise.order).all())
            modules_with_exercises.append({'module': mod, 'exercises': exercises})

    school_id = section_school_id(section)
    school = db.session.get(School, school_id) if school_id else None
    return render_template('teacher/edit_section.html', section=section, courses=courses,
                           modules_with_exercises=modules_with_exercises,
                           hidden_ids=hidden_ids,
                           overrides=section.module_overrides,
                           assignable_count=len(assignable_section_teachers(section)),
                           school_name=school.name if school else None,
                           can_manage=can_manage_section(section))


@app.route('/teacher/section/new', methods=['GET', 'POST'])
@login_required
@role_required('admin_teacher', 'admin')
def teacher_new_section():
    # @role_required only asks "is this account an admin_teacher anywhere?".
    # A section is governed through the school its course belongs to, so someone
    # who administers no school has nowhere to put one — and the section they
    # created would answer to nobody but themselves.
    if not administered_schools():
        flash('You do not administer any school yet, so there is nowhere to '
              f'create a {section_word()}.', 'warning')
        return redirect(url_for('teacher_dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        course_id = request.form.get('course_id', type=int)
        if not name:
            flash(f'{section_word(title=True)} name is required.', 'danger')
            return render_template('teacher/new_section.html',
                                   courses=administered_courses())
        if course_id and course_id not in {c.id for c in administered_courses()}:
            flash('That course is not in a school you administer.', 'danger')
            return render_template('teacher/new_section.html',
                                   courses=administered_courses())
        join_code = secrets.token_urlsafe(8)[:8].upper()
        section = Section(name=name, join_code=join_code,
                    teacher_id=current_user.id,
                    course_id=course_id if course_id else None)
        db.session.add(section)
        db.session.commit()
        flash(f'Section "{name}" created. Join code: {join_code}', 'success')
        return redirect(url_for('teacher_section_detail', section_id=section.id))
    return render_template('teacher/new_section.html',
                           courses=administered_courses())


@app.route('/teacher/section/<int:section_id>')
@login_required
@role_required('admin_teacher', 'class_teacher', 'admin')
def teacher_section_detail(section_id):
    section = Section.query.get_or_404(section_id)
    require_section_role(section, 'class_teacher')

    roster = []
    for student in section.members:
        uid = student.id

        def mode_avg(model, score_field, _uid=uid):
            rows = model.query.filter_by(user_id=_uid).order_by(model.created_at.desc()).limit(20).all()
            vals = [getattr(r, score_field) for r in rows if getattr(r, score_field) is not None]
            return round(sum(vals) / len(vals)) if vals else None

        roster.append({
            'student':  student,
            'melodic':  mode_avg(UserAttempt,    'overall_score'),
            'rhythmic': mode_avg(RhythmAttempt,  'duration_accuracy'),
            'harmonic': mode_avg(HarmonicAttempt,'overall_score'),
            'holistic': mode_avg(HolisticAttempt,'overall_score'),
        })

    return render_template('teacher/section_detail.html', section=section, roster=roster)


@app.route('/teacher/sections/<int:section_id>/set_course', methods=['POST'])
@login_required
@role_required('admin_teacher', 'admin')
def teacher_set_course(section_id):
    section = Section.query.get_or_404(section_id)
    require_manage_section(section)
    course_id = request.form.get('course_id', type=int)
    if course_id and course_id not in {c.id for c in administered_courses()}:
        flash('That course is not in a school you administer.', 'danger')
        return redirect(url_for('teacher_section_detail', section_id=section_id))
    section.course_id = course_id or None
    db.session.commit()
    flash('Course assignment updated.', 'success')
    return redirect(url_for('teacher_section_detail', section_id=section_id))


@app.route('/teacher/sections/<int:section_id>/assign-teacher', methods=['POST'])
@login_required
@role_required('admin_teacher', 'admin')
def teacher_assign_section_teacher(section_id):
    section = Section.query.get_or_404(section_id)
    require_manage_section(section)
    back = redirect(url_for('teacher_edit_section', section_id=section_id))

    if request.form.get('clear'):
        section.assigned_teacher_id = None
        db.session.commit()
        flash(f'{section_word(title=True)} teacher cleared.', 'success')
        return back

    email = (request.form.get('email') or '').strip()
    if not email:
        flash('Enter the email of a teacher in this school.', 'danger')
        return back

    school_id = section_school_id(section)
    if school_id is None:
        flash(f'This {section_word()} has no course, so it does not belong to a '
              f'school yet. Assign a course first.', 'warning')
        return back
    school = db.session.get(School, school_id)

    user = find_user_by_email(email)
    if user is None:
        flash(f'No account found for "{email}".', 'danger')
        return back

    # The candidate must be staff in THIS section's school — otherwise any
    # teacher anywhere on the site could be assigned. Say precisely which of
    # those two things went wrong.
    mem = SchoolMembership.query.filter_by(
        school_id=school_id, user_id=user.id).first()
    if mem is None:
        flash(f'{user.email} is not a member of {school.name}. '
              f'Add them to the school first.', 'warning')
        return back
    if mem.role not in ('class_teacher', 'admin_teacher'):
        flash(f'{user.email} is a {mem.role} in {school.name}, not a teacher. '
              f'Change their school role first.', 'warning')
        return back

    section.assigned_teacher_id = user.id
    db.session.commit()
    flash(f'{user.email} is now the {section_word()} teacher.', 'success')
    return back


def assignable_section_teachers(section):
    """Staff who may be assigned to teach this section: class_teacher or
    admin_teacher members of the section's school. "Or higher" is honoured — an
    admin_teacher can be assigned as a section teacher."""
    sid = section_school_id(section)
    if sid is None:
        return []
    mems = SchoolMembership.query.filter(
        SchoolMembership.school_id == sid,
        SchoolMembership.role.in_(('class_teacher', 'admin_teacher'))
    ).all()
    return [m.user for m in mems if m.user]


@app.route('/teacher/sections/<int:section_id>/overrides/add', methods=['POST'])
@login_required
@role_required('admin_teacher', 'class_teacher', 'admin')
def teacher_add_override(section_id):
    section = Section.query.get_or_404(section_id)
    require_section_role(section, 'class_teacher')
    action    = request.form['action']
    module_id = request.form.get('module_id', type=int)
    me_id     = request.form.get('module_exercise_id', type=int)
    ex_type   = request.form.get('exercise_type')
    ex_id     = request.form.get('exercise_id', type=int)
    order     = request.form.get('order', type=int)
    criterion = request.form.get('completion_criterion')
    if criterion:
        try:
            json.loads(criterion)
        except (ValueError, TypeError):
            criterion = '{"attempts":1}'
    sme = SectionModuleExercise(
        section_id=section_id,
        action=action,
        module_exercise_id=me_id,
        module_id=module_id,
        exercise_type=ex_type,
        exercise_id=ex_id,
        order=order,
        completion_criterion_json=criterion,
    )
    db.session.add(sme)
    db.session.commit()
    flash('Override added.', 'success')
    return redirect(url_for('teacher_edit_section', section_id=section_id))


@app.route('/teacher/sections/<int:section_id>/overrides/<int:sme_id>/delete', methods=['POST'])
@login_required
@role_required('admin_teacher', 'class_teacher', 'admin')
def teacher_delete_override(section_id, sme_id):
    section = Section.query.get_or_404(section_id)
    require_section_role(section, 'class_teacher')
    sme = SectionModuleExercise.query.get_or_404(sme_id)
    if sme.section_id != section_id:
        abort(403)
    db.session.delete(sme)
    db.session.commit()
    flash('Override removed.', 'success')
    return redirect(url_for('teacher_edit_section', section_id=section_id))


@app.route('/teacher/sections/<int:section_id>/modules/<int:module_id>/hide', methods=['POST'])
@login_required
@role_required('admin_teacher', 'class_teacher', 'admin')
def teacher_hide_module(section_id, module_id):
    section = Section.query.get_or_404(section_id)
    require_section_role(section, 'class_teacher')
    module = Module.query.get_or_404(module_id)
    for ex in module.exercises:
        exists = SectionModuleExercise.query.filter_by(
            section_id=section_id, module_exercise_id=ex.id, action='hide'
        ).first()
        if not exists:
            db.session.add(SectionModuleExercise(
                section_id=section_id,
                module_id=module_id,
                module_exercise_id=ex.id,
                action='hide'
            ))
    db.session.commit()
    flash(f'Module "{module.name}" hidden for this {section_word()}.', 'success')
    return redirect(url_for('teacher_edit_section', section_id=section_id))


@app.route('/teacher/sections/<int:section_id>/modules/<int:module_id>/restore', methods=['POST'])
@login_required
@role_required('admin_teacher', 'class_teacher', 'admin')
def teacher_restore_module(section_id, module_id):
    section = Section.query.get_or_404(section_id)
    require_section_role(section, 'class_teacher')
    SectionModuleExercise.query.filter_by(
        section_id=section_id, module_id=module_id, action='hide'
    ).delete()
    db.session.commit()
    flash('Module restored.', 'success')
    return redirect(url_for('teacher_edit_section', section_id=section_id))


@app.route('/teacher/sections/<int:section_id>/module_exercises/add', methods=['POST'])
@login_required
@role_required('admin_teacher', 'admin')
def teacher_add_module_exercise(section_id):
    section = Section.query.get_or_404(section_id)
    require_manage_section(section)
    module_id = request.form.get('module_id', type=int)
    exercise_type = request.form.get('exercise_type', '').strip()
    exercise_id = request.form.get('exercise_id', type=int)
    name = request.form.get('name', '').strip()
    order = request.form.get('order', type=int) or 0
    if not all([module_id, exercise_type, exercise_id]):
        flash('All fields required.', 'danger')
        return redirect(url_for('teacher_edit_section', section_id=section_id))
    # Per-SECTION addition. Writing a ModuleExercise here would edit the shared
    # course and change the curriculum for every other section using it.
    sme = SectionModuleExercise(
        section_id=section_id,
        action='add',
        module_id=module_id,
        exercise_type=exercise_type,
        exercise_id=exercise_id,
        order=order,
    )
    db.session.add(sme)
    db.session.commit()
    flash(f'Exercise added to this {section_word()} only.', 'success')
    return redirect(url_for('teacher_edit_section', section_id=section_id))


@app.route('/section/join', methods=['POST'])
@login_required
def join_section():
    code = request.form.get('join_code', '').strip().upper()
    if not code:
        flash('Please enter a join code.', 'danger')
        return redirect(url_for('me'))
    section  = Section.query.filter_by(join_code=code).first()
    if not section:
        flash('Invalid join code.', 'danger')
    elif current_user in section.members:
        flash(f'You are already in this {section_word()}.', 'info')
    else:
        if section.course and section.course.school_id:
            mem = SchoolMembership.query.filter_by(
                school_id=section.course.school_id,
                user_id=current_user.id,
            ).first()
            if not mem:
                school = School.query.get(section.course.school_id)
                flash(
                    f'You must join school "{school.name}" first. '
                    f'Ask your teacher for the school join code.',
                    'warning'
                )
                return redirect(url_for('me'))
        section.members.append(current_user)
        db.session.commit()
        flash(f'Joined "{section.name}".', 'success')
    return redirect(url_for('me'))


# ---------------------------------------------------------------------------
# Student class routes
# ---------------------------------------------------------------------------

@app.route('/section/<int:section_id>')
@login_required
def section_home(section_id):
    section = Section.query.get_or_404(section_id)
    require_section_role(section, 'student')
    has_course = section.course_id is not None
    return render_template('student/mode_select.html', section=section, has_course=has_course)


@app.route('/section/<int:section_id>/modules')
@login_required
def section_modules(section_id):
    section = Section.query.get_or_404(section_id)
    require_section_role(section, 'student')
    if not section.course_id:
        flash('This course has no work assigned yet.', 'info')
        return redirect(url_for('section_home', section_id=section_id))
    mods = cur.modules_with_progress(current_user.id, section_id, section)
    return render_template('student/module_list.html', section=section, mods=mods)


@app.route('/section/<int:section_id>/modules/<int:module_id>')
@login_required
def section_module_detail(section_id, module_id):
    section  = Section.query.get_or_404(section_id)
    require_section_role(section, 'student')
    module = Module.query.get_or_404(module_id)
    if section.course_id is None or module.course_id != section.course_id:
        abort(404)
    exercises = cur.effective_exercises(section, module)
    done = cur.completion_map(current_user.id, section_id)
    ex_with_status = []
    for ex in exercises:
        key = (ex['module_exercise_id'], ex['section_exercise_id'])
        completion = cur.get_completion(
            current_user.id, section_id,
            ex['module_exercise_id'], ex['section_exercise_id']
        )
        ex_with_status.append({
            **ex,
            'completed': key in done,
            'best_score': completion.best_score if completion else None,
        })
    for ex in ex_with_status:
        if ex['exercise_type'] == 'melody':
            obj = Melody.query.get(ex['exercise_id'])
        elif ex['exercise_type'] == 'rhythm':
            obj = Rhythm.query.get(ex['exercise_id'])
        elif ex['exercise_type'] == 'harmonic':
            obj = ChordProgression.query.get(ex['exercise_id'])
        elif ex['exercise_type'] == 'holistic':
            obj = HolisticExercise.query.get(ex['exercise_id'])
        else:
            obj = None
        ex['name'] = obj.name if obj else f"Exercise #{ex['exercise_id']}"
    for ex in ex_with_status:
        # Prefer ModuleExercise.name if set
        me_obj = ModuleExercise.query.get(ex['module_exercise_id']) if ex['module_exercise_id'] else None
        if me_obj and me_obj.name:
            ex['name'] = me_obj.name

        # Start URL
        if ex['module_exercise_id']:
            ex['start_url'] = url_for('start_module_exercise',
                                      section_id=section_id,
                                      me_id=ex['module_exercise_id'])
        else:
            type_to_route = {
                'melody':   ('exercise',          'melody_id'),
                'rhythm':   ('rhythm_exercise',   'rhythm_id'),
                'harmonic': ('harmonic_exercise', 'progression_id'),
                'holistic': ('holistic_exercise', 'exercise_id'),
            }
            route_name, param_name = type_to_route.get(ex['exercise_type'], ('section_home', 'section_id'))
            ex['start_url'] = url_for(route_name,
                                      **{param_name: ex['exercise_id']},
                                      section_id=section_id,
                                      me_id='', sme_id=ex['section_exercise_id'] or '')

        # Progress
        me_obj2 = ModuleExercise.query.get(ex['module_exercise_id']) if ex['module_exercise_id'] else None
        criterion = me_obj2.completion_criterion if me_obj2 else {'attempts': 1}
        ex['progress'] = cur.get_progress(
            current_user.id, section_id,
            ex['module_exercise_id'], ex['section_exercise_id'],
            criterion
        )
    return render_template('student/module_detail.html',
                           section=section,
                           module=module,
                           exercises=ex_with_status)


@app.route('/section/<int:section_id>/module_exercise/<int:me_id>/start')
@login_required
def start_module_exercise(section_id, me_id):
    section = Section.query.get_or_404(section_id)
    require_section_role(section, 'student')

    me = ModuleExercise.query.get_or_404(me_id)
    if me.module.course_id != section.course_id:
        abort(404)

    params = me.params
    type_map = {
        'melody':   (Melody,           'exercise',          'melody_id'),
        'rhythm':   (Rhythm,           'rhythm_exercise',   'rhythm_id'),
        'harmonic': (ChordProgression, 'harmonic_exercise', 'progression_id'),
    }

    kp        = request.args.get('kp', '')  # keep_practicing flag — passed through to results
    module_id = me.module_id

    if me.exercise_type == 'holistic':
        return redirect(url_for('holistic_exercise',
                                exercise_id=me.exercise_id,
                                section_id=section_id, me_id=me_id, sme_id='',
                                module_id=module_id, kp=kp))

    model_class, route_name, param_name = type_map[me.exercise_type]
    q = model_class.query.filter(_visible_exercise_filter(model_class))
    q = _apply_exercise_filters(q, model_class, params)
    candidates = q.all()

    if not candidates:
        flash('No exercises match the filters for this module exercise. Ask your teacher to adjust the filters.', 'warning')
        return redirect(url_for('section_module_detail',
                                section_id=section_id, module_id=module_id))

    chosen = random.choice(candidates)
    return redirect(url_for(route_name,
                            **{param_name: chosen.id},
                            section_id=section_id, me_id=me_id, sme_id='',
                            module_id=module_id, kp=kp))


# ---------------------------------------------------------------------------
# Dev helpers
# ---------------------------------------------------------------------------

@app.cli.command('init-db')
def init_db():
    """Create tables."""
    db.create_all()
    print('Database tables created.')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, port=port)
