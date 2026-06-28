import json
import os
import random
import secrets
import string as _string
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from models import db, Melody, Tag, UserAttempt, Rhythm, RhythmAttempt, \
                   ChordProgression, HarmonicAttempt, HolisticExercise, HolisticAttempt, \
                   GenProgression, Container, \
                   User, Class, School, Course, Module, ModuleExercise, \
                   ClassModuleExercise, ModuleCompletion, SchoolMembership
from chord_utils import grade_harmonic_attempt, format_chord_name
import curriculum as cur

_ALPHA = _string.ascii_uppercase + _string.digits

def _random_school_code():
    return ''.join(secrets.choice(_ALPHA) for _ in range(8))

app = Flask(__name__)

# ── Database ─────────────────────────────────────────────────────────────────
# The exercise database is bundled directly in the repository (instance/musicianship.db).
# No external database service is needed.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///musicianship.db'
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


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


# ---------------------------------------------------------------------------
# Module-completion helper
# ---------------------------------------------------------------------------

def _handle_module_completion(class_id, me_id, cme_id, score, keep_practicing=False):
    """
    Called after a drill submission when the student came from a module.
    Records the attempt, checks criterion, returns nav context dict or None.
    """
    if not class_id:
        return None
    try:
        class_id_int = int(class_id)
        klass = Class.query.get(class_id_int)
        if not klass:
            return None
    except (ValueError, TypeError):
        return None

    is_member = current_user in klass.members
    is_own_teacher = klass.teacher_id == current_user.id
    if not is_member and not is_own_teacher and current_user.role != 'admin':
        return None

    me_id_int  = int(me_id)  if me_id  else None
    cme_id_int = int(cme_id) if cme_id else None

    me = ModuleExercise.query.get(me_id_int) if me_id_int else None
    criterion = me.completion_criterion if me else {'attempts': 1}

    # Validate me_id belongs to this class's course (prevent forged me_id)
    if me and (klass.course_id is None or me.module.course_id != klass.course_id):
        return None

    mc, just_completed = cur.record_attempt(
        current_user.id, class_id_int, me_id_int, cme_id_int, score, criterion
    )

    progress = cur.get_progress(
        current_user.id, class_id_int, me_id_int, cme_id_int, criterion
    )

    module = me.module if me else None
    if not module and cme_id_int:
        cme = ClassModuleExercise.query.get(cme_id_int)
        if cme and cme.class_id == class_id_int:
            module = Module.query.get(cme.module_id)

    module_url = url_for('class_module_detail', class_id=class_id_int,
                         module_id=module.id) if module else url_for('class_home', class_id=class_id_int)
    module_name  = module.name if module else None
    exercise_name = me.name if me else None
    keep_practicing_url = url_for('start_module_exercise',
                                  class_id=class_id_int, me_id=me_id_int,
                                  kp='1') if me_id_int else None

    if not module:
        return {
            'next_url': url_for('class_home', class_id=class_id_int),
            'module_url': url_for('class_home', class_id=class_id_int),
            'module_name': None,
            'exercise_name': exercise_name,
            'keep_practicing_url': None,
            'keep_practicing': keep_practicing,
            'module_done': False,
            'complete': mc.is_complete,
            'progress': progress,
            'class_id': class_id_int,
        }

    if mc.is_complete:
        next_ex = cur.next_incomplete(current_user.id, class_id_int, klass, module)
        if next_ex:
            if next_ex['module_exercise_id']:
                next_url = url_for('start_module_exercise',
                                   class_id=class_id_int,
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
                'class_id': class_id_int,
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
                'class_id': class_id_int,
                'module_id': module.id,
            }
    else:
        if me_id_int:
            start_url = url_for('start_module_exercise',
                                class_id=class_id_int, me_id=me_id_int)
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
            'class_id': class_id_int,
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
        scores (dict): individual metric scores, e.g.:
            {"melody_pitch": 85.0, "melody_duration": 72.0,
             "harmony_letter": 90.0, "harmony_quality": 80.0,
             "rhythm_1_duration": 70.0, ...}
        overall (float): simple average of all individual metric scores.
    """
    from chord_utils import grade_harmonic_attempt

    scores = {}

    # Primary melody
    user_melody = user_data.get('melody', [])
    p, d, _ = grade_attempt(exercise.melody_notes, user_melody)
    scores['melody_pitch']    = p
    scores['melody_duration'] = d

    # Harmony
    user_harmony = user_data.get('harmony', [])
    l, q, _ = grade_harmonic_attempt(exercise.harmony_chords, user_harmony)
    scores['harmony_letter']  = l
    scores['harmony_quality'] = q

    # Extra lines
    for line in exercise.extra_lines:
        ltype = line['type']
        lfile = line['file']
        # Derive key from filename: "melody_1.mid" -> "melody_1", "rhythm_1.mid" -> "rhythm_1"
        lkey = lfile.replace('.mid', '')

        user_line = user_data.get(lkey, [])
        correct   = line.get('notes', [])

        if ltype == 'melody':
            p, d, _ = grade_attempt(correct, user_line)
            scores[lkey + '_pitch']    = p
            scores[lkey + '_duration'] = d
        elif ltype == 'rhythm':
            d = grade_rhythm(correct, user_line)
            scores[lkey + '_duration'] = d

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
    for klass in current_user.classes:
        if klass.course_id and klass.course:
            user_school_ids.add(klass.course.school_id)
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
    if params.get('tags'):
        for tag_name in params['tags']:
            query = query.filter(model.tags.any(Tag.name == tag_name))
    return query


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def home():
    user_classes = []
    if current_user.is_authenticated:
        if current_user.role in ('teacher', 'admin'):
            user_classes = list(current_user.classes_taught)
        else:
            user_classes = list(current_user.classes)
    return render_template('home.html', user_classes=user_classes)


@app.route('/sandbox')
def sandbox():
    return render_template('home.html', user_classes=[], sandbox_mode=True)


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

    class_id = data.get('class_id', '')
    me_id    = data.get('me_id', '')
    cme_id   = data.get('cme_id', '')
    return jsonify({'redirect': url_for('results', attempt_id=attempt.id,
                                        class_id=class_id, me_id=me_id, cme_id=cme_id)})


@app.route('/results/<int:attempt_id>')
@login_required
def results(attempt_id):
    attempt = UserAttempt.query.get_or_404(attempt_id)
    if attempt.user_id is not None and attempt.user_id != current_user.id:
        is_teacher = attempt.user and any(
            cls.teacher_id == current_user.id for cls in attempt.user.classes
        )
        if not is_teacher and current_user.role != 'admin':
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

    class_id = request.args.get('class_id')
    me_id    = request.args.get('me_id')
    cme_id   = request.args.get('cme_id')
    kp       = request.args.get('kp', '') == '1'
    module_ctx = None
    if current_user.is_authenticated and class_id:
        module_ctx = _handle_module_completion(class_id, me_id, cme_id, attempt.overall_score,
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

    class_id = data.get('class_id', '')
    me_id    = data.get('me_id', '')
    cme_id   = data.get('cme_id', '')
    return jsonify({'redirect': url_for('rhythm_results', attempt_id=attempt.id,
                                        class_id=class_id, me_id=me_id, cme_id=cme_id)})


@app.route('/rhythm/results/<int:attempt_id>')
@login_required
def rhythm_results(attempt_id):
    attempt = RhythmAttempt.query.get_or_404(attempt_id)
    if attempt.user_id is not None and attempt.user_id != current_user.id:
        is_teacher = attempt.user and any(
            cls.teacher_id == current_user.id for cls in attempt.user.classes
        )
        if not is_teacher and current_user.role != 'admin':
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

    class_id = request.args.get('class_id')
    me_id    = request.args.get('me_id')
    cme_id   = request.args.get('cme_id')
    kp       = request.args.get('kp', '') == '1'
    module_ctx = None
    if current_user.is_authenticated and class_id:
        module_ctx = _handle_module_completion(class_id, me_id, cme_id, attempt.duration_accuracy,
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

    class_id = data.get('class_id', '')
    me_id    = data.get('me_id', '')
    cme_id   = data.get('cme_id', '')
    return jsonify({'redirect': url_for('harmonic_results', attempt_id=attempt.id,
                                        class_id=class_id, me_id=me_id, cme_id=cme_id)})


@app.route('/harmonic/results/<int:attempt_id>')
@login_required
def harmonic_results(attempt_id):
    attempt     = HarmonicAttempt.query.get_or_404(attempt_id)
    if attempt.user_id is not None and attempt.user_id != current_user.id:
        is_teacher = attempt.user and any(
            cls.teacher_id == current_user.id for cls in attempt.user.classes
        )
        if not is_teacher and current_user.role != 'admin':
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

    class_id = request.args.get('class_id')
    me_id    = request.args.get('me_id')
    cme_id   = request.args.get('cme_id')
    kp       = request.args.get('kp', '') == '1'
    module_ctx = None
    if current_user.is_authenticated and class_id:
        module_ctx = _handle_module_completion(class_id, me_id, cme_id, attempt.overall_score,
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
    chords   = exercise.harmony_chords
    unlock_seventh    = any(c.get('seventh')    for c in chords)
    unlock_extensions = any(c.get('extensions') for c in chords)
    unlock_sus        = any(c.get('sus')        for c in chords)
    extra_lines_display = [
        {'key':   l['file'].replace('.mid', ''),
         'type':  l['type'],
         'label': l['label'],
         'clef':  l.get('clef', 'treble')}
        for l in exercise.extra_lines
    ]
    return render_template('holistic_exercise.html',
                           exercise=exercise,
                           unlock_seventh=unlock_seventh,
                           unlock_extensions=unlock_extensions,
                           unlock_sus=unlock_sus,
                           extra_lines_display=extra_lines_display)


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

    class_id = data.get('class_id', '')
    me_id    = data.get('me_id', '')
    cme_id   = data.get('cme_id', '')
    return jsonify({'redirect': url_for('holistic_results', attempt_id=attempt.id,
                                        class_id=class_id, me_id=me_id, cme_id=cme_id)})


@app.route('/holistic/results/<int:attempt_id>')
@login_required
def holistic_results(attempt_id):
    attempt  = HolisticAttempt.query.get_or_404(attempt_id)
    if attempt.user_id is not None and attempt.user_id != current_user.id:
        is_teacher = attempt.user and any(
            cls.teacher_id == current_user.id for cls in attempt.user.classes
        )
        if not is_teacher and current_user.role != 'admin':
            abort(403)
    exercise = attempt.exercise

    class_id = request.args.get('class_id')
    me_id    = request.args.get('me_id')
    cme_id   = request.args.get('cme_id')
    kp       = request.args.get('kp', '') == '1'
    module_ctx = None
    if current_user.is_authenticated and class_id:
        module_ctx = _handle_module_completion(class_id, me_id, cme_id, attempt.overall_score,
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
            password_hash = generate_password_hash(password),
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
        class_count=Class.query.count(),
        melody_count=Melody.query.count(),
        harmonic_count=ChordProgression.query.count(),
        rhythm_count=Rhythm.query.count(),
        holistic_count=HolisticExercise.query.count(),
        gen_prog_count=GenProgression.query.count(),
    )


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
@role_required('admin')
def admin_courses(school_id):
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
@role_required('admin')
def admin_modules(course_id):
    course = Course.query.get_or_404(course_id)
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
@role_required('admin')
def admin_module_exercises(module_id):
    module = Module.query.get_or_404(module_id)
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
            time_sig     = request.form.get('time_signature', '').strip()
            key_sig      = request.form.get('key_signature', '').strip()
            params_dict  = {}
            if difficulties:
                params_dict['difficulty'] = [int(d) for d in difficulties]
            if tags_list:
                params_dict['tags'] = [t for t in tags_list if t]
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
@role_required('admin')
def admin_delete_module_exercise(me_id):
    me = ModuleExercise.query.get_or_404(me_id)
    module_id = me.module_id
    db.session.delete(me)
    db.session.commit()
    flash('Exercise removed.', 'success')
    return redirect(url_for('admin_module_exercises', module_id=module_id))


@app.route('/admin/module_exercises/<int:me_id>/edit', methods=['POST'])
@login_required
@role_required('admin')
def admin_edit_module_exercise(me_id):
    me = ModuleExercise.query.get_or_404(me_id)
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
        time_sig     = request.form.get('time_signature', '').strip()
        key_sig      = request.form.get('key_signature', '').strip()
        params_dict  = {}
        if difficulties:
            params_dict['difficulty'] = [int(d) for d in difficulties]
        if tags_list:
            params_dict['tags'] = [t for t in tags_list if t]
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
@role_required('admin')
def admin_duplicate_module_exercise(me_id):
    src = ModuleExercise.query.get_or_404(me_id)
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
                ClassModuleExercise.query.filter(ClassModuleExercise.module_exercise_id.in_(me_ids)).delete(synchronize_session=False)
            ModuleExercise.query.filter_by(module_id=module.id).delete()
            db.session.delete(module)
        db.session.delete(course)
    db.session.delete(school)
    db.session.commit()
    flash(f'School "{name}" deleted.', 'success')
    return redirect(url_for('admin_schools'))


@app.route('/admin/schools/<int:school_id>/detail', methods=['GET'])
@login_required
@role_required('admin_teacher', 'admin')
def admin_school_detail(school_id):
    school = School.query.get_or_404(school_id)
    if current_user.role == 'admin_teacher':
        mem = SchoolMembership.query.filter_by(
            school_id=school_id, user_id=current_user.id, role='admin_teacher'
        ).first()
        if not mem:
            abort(403)
    memberships = SchoolMembership.query.filter_by(school_id=school_id).all()
    return render_template('admin/school_detail.html',
                           school=school,
                           memberships=memberships,
                           is_full_admin=(current_user.role == 'admin'))


@app.route('/admin/schools/<int:school_id>/set-member-role', methods=['POST'])
@login_required
@role_required('admin_teacher', 'admin')
def admin_set_member_role(school_id):
    school = School.query.get_or_404(school_id)
    user_id  = request.form.get('user_id', type=int)
    new_role = request.form.get('role', '').strip()
    if new_role not in ('student', 'admin_teacher', 'class_teacher'):
        flash('Invalid role.', 'danger')
        return redirect(url_for('admin_school_detail', school_id=school_id))
    if current_user.role == 'admin_teacher':
        mem = SchoolMembership.query.filter_by(
            school_id=school_id, user_id=user_id
        ).first_or_404()
    else:
        mem = SchoolMembership.query.filter_by(
            school_id=school_id, user_id=user_id
        ).first()
        if not mem:
            flash('User is not a member of this school.', 'danger')
            return redirect(url_for('admin_school_detail', school_id=school_id))
    mem.role = new_role
    if new_role in ('admin_teacher', 'class_teacher'):
        from models import User as _User
        target = _User.query.get(user_id)
        if target and target.role == 'student':
            target.role = new_role
    db.session.commit()
    flash('Role updated.', 'success')
    return redirect(url_for('admin_school_detail', school_id=school_id))


@app.route('/admin/schools/<int:school_id>/add-member', methods=['POST'])
@login_required
@role_required('admin')
def admin_add_school_member(school_id):
    school = School.query.get_or_404(school_id)
    email  = request.form.get('email', '').strip()
    role   = request.form.get('role', 'student')
    if role not in ('student', 'admin_teacher', 'class_teacher'):
        role = 'student'
    from models import User as _User
    user = _User.query.filter_by(email=email).first()
    if not user:
        flash(f'No user with email "{email}".', 'danger')
        return redirect(url_for('admin_school_detail', school_id=school_id))
    exists = SchoolMembership.query.filter_by(
        school_id=school_id, user_id=user.id
    ).first()
    if exists:
        flash(f'{email} is already a member.', 'info')
        return redirect(url_for('admin_school_detail', school_id=school_id))
    db.session.add(SchoolMembership(school_id=school_id, user_id=user.id, role=role))
    if role in ('admin_teacher', 'class_teacher') and user.role == 'student':
        user.role = role
    db.session.commit()
    flash(f'Added {email} as {role}.', 'success')
    return redirect(url_for('admin_school_detail', school_id=school_id))


@app.route('/admin/schools/<int:school_id>/regen-join-code', methods=['POST'])
@login_required
@role_required('admin_teacher', 'admin')
def admin_regen_join_code(school_id):
    school = School.query.get_or_404(school_id)
    if current_user.role == 'admin_teacher':
        mem = SchoolMembership.query.filter_by(
            school_id=school_id, user_id=current_user.id, role='admin_teacher'
        ).first()
        if not mem:
            abort(403)
    school.join_code = _random_school_code()
    db.session.commit()
    flash(f'Join code regenerated: {school.join_code}', 'success')
    return redirect(url_for('admin_school_detail', school_id=school_id))


@app.route('/admin/courses/<int:course_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    school_id = course.school_id
    name = course.name
    for module in course.modules.all():
        # Clean up dependent records before deleting ModuleExercise
        me_ids = [me.id for me in ModuleExercise.query.filter_by(module_id=module.id).all()]
        if me_ids:
            ModuleCompletion.query.filter(ModuleCompletion.module_exercise_id.in_(me_ids)).delete(synchronize_session=False)
            ClassModuleExercise.query.filter(ClassModuleExercise.module_exercise_id.in_(me_ids)).delete(synchronize_session=False)
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


@app.route('/admin/courses/<int:course_id>/classes')
@login_required
@role_required('admin_teacher', 'admin')
def admin_course_classes(course_id):
    course = Course.query.get_or_404(course_id)
    classes = Class.query.filter_by(course_id=course_id).all()
    return render_template('admin/course_classes.html',
                           course=course, classes=classes)


@app.route('/admin/modules/<int:module_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_module(module_id):
    module = Module.query.get_or_404(module_id)
    course_id = module.course_id
    name = module.name
    # Clean up dependent records before deleting ModuleExercise
    me_ids = [me.id for me in ModuleExercise.query.filter_by(module_id=module.id).all()]
    if me_ids:
        ModuleCompletion.query.filter(ModuleCompletion.module_exercise_id.in_(me_ids)).delete(synchronize_session=False)
        ClassModuleExercise.query.filter(ClassModuleExercise.module_exercise_id.in_(me_ids)).delete(synchronize_session=False)
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
            time_signature=request.form.get('time_signature', '4/4'),
            min_duration=request.form.get('min_duration', 'q'),
            difficulty=request.form.get('difficulty', 1, type=int),
            tempo=request.form.get('tempo', 100, type=int),
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
        h.time_signature = request.form.get('time_signature', h.time_signature)
        h.melody_clef    = request.form.get('melody_clef', h.melody_clef)
        h.difficulty     = request.form.get('difficulty', h.difficulty, type=int) or h.difficulty
        h.visibility     = request.form.get('visibility', h.visibility)
        tag_ids = request.form.getlist('tag_ids', type=int)
        h.tags = Tag.query.filter(Tag.id.in_(tag_ids)).all() if tag_ids else []
        for field in ('melody_notes_json', 'harmony_chords_json', 'extra_lines_json'):
            raw = request.form.get(field, '').strip()
            if raw:
                try:
                    json.loads(raw)
                    setattr(h, field, raw)
                except ValueError:
                    flash(f'Invalid JSON in {field} — not saved.', 'warning')
        db.session.commit()
        flash('Exercise updated.', 'success')
        return redirect(url_for('admin_edit_holistic', ex_id=ex_id))
    return render_template('admin/holistic_edit.html', h=h, all_tags=all_tags)


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
    # POST — accept WAV (required) + MIDI (optional)
    wav_file = request.files.get('wav_file')
    if not wav_file or not wav_file.filename or not wav_file.filename.lower().endswith('.wav'):
        flash('Please upload a .wav file.', 'danger')
        return redirect(url_for('admin_holistic_upload'))
    midi_file = request.files.get('midi_file')
    if midi_file and midi_file.filename and not midi_file.filename.lower().endswith('.mid'):
        flash('MIDI file must have a .mid extension.', 'danger')
        return redirect(url_for('admin_holistic_upload'))

    import re, shutil, tempfile
    name = request.form.get('name', '').strip() or wav_file.filename.rsplit('.', 1)[0]
    key  = request.form.get('key_signature', 'C').strip()
    base_slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'holistic'

    # Save WAV to a temp location first; move to final slug dir after flush gives us the ID
    wav_tmp_fd, wav_tmp_path = tempfile.mkstemp(suffix='.wav')
    with os.fdopen(wav_tmp_fd, 'wb') as _wf:
        wav_file.save(_wf)

    melody_notes_json = '[]'
    midi_tmp_path = None
    if midi_file and midi_file.filename:
        from midi_to_notes import extract_notes, build_json_list
        try:
            tmp_fd, midi_tmp_path = tempfile.mkstemp(suffix='.mid')
            with os.fdopen(tmp_fd, 'wb') as tmp_f:
                midi_file.save(tmp_f)
            notes = extract_notes(midi_tmp_path)
            note_list = build_json_list(notes, key)
            melody_notes_json = json.dumps(note_list)
        except Exception:
            if midi_tmp_path:
                try:
                    os.unlink(midi_tmp_path)
                except OSError:
                    pass
            midi_tmp_path = None
            raise

    h = HolisticExercise(
        name=name,
        folder='',  # set after flush
        wav_filename='',  # set after flush
        key_signature=key,
        melody_notes_json=melody_notes_json,
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

    if midi_tmp_path:
        midi_dest = os.path.join(dest_dir, f'{slug}.mid')
        shutil.copy(midi_tmp_path, midi_dest)
        try:
            os.unlink(midi_tmp_path)
        except OSError:
            pass

    h.folder = f'holistic/{slug}/'
    h.wav_filename = f'{slug}.wav'
    db.session.commit()
    flash(f'Exercise "{h.name}" uploaded ({h.public_id}).', 'success')
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


@app.route('/teacher/classes/<int:class_id>/delete', methods=['GET', 'POST'])
@login_required
@role_required('admin_teacher', 'admin')
def teacher_delete_class(class_id):
    klass = Class.query.get_or_404(class_id)
    if klass.teacher_id != current_user.id and current_user.role != 'admin':
        abort(403)
    if request.method == 'GET':
        return render_template('teacher/confirm_delete_class.html', cls=klass)
    name = klass.name
    ModuleCompletion.query.filter_by(class_id=class_id).delete()
    ClassModuleExercise.query.filter_by(class_id=class_id).delete()
    klass.members.clear()
    db.session.flush()
    db.session.delete(klass)
    db.session.commit()
    flash(f'Class "{name}" deleted.', 'success')
    return redirect(url_for('teacher_dashboard'))


@app.route('/teacher/class/<int:class_id>/kick/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin_teacher', 'class_teacher', 'admin')
def teacher_kick_student(class_id, user_id):
    klass = Class.query.get_or_404(class_id)
    if current_user.role == 'class_teacher' and klass.assigned_teacher_id != current_user.id:
        abort(403)
    if current_user.role == 'admin_teacher' and klass.teacher_id != current_user.id:
        abort(403)
    student = User.query.get_or_404(user_id)
    if request.method == 'GET':
        return render_template('teacher/confirm_kick_student.html', cls=klass, student=student)
    if student in klass.members:
        klass.members.remove(student)
        db.session.commit()
        flash(f'{student.display_name or student.email} removed from {klass.name}.', 'success')
    return redirect(url_for('teacher_class_detail', class_id=class_id))


@app.route('/class/<int:class_id>/leave', methods=['POST'])
@login_required
def leave_class(class_id):
    klass = Class.query.get_or_404(class_id)
    if current_user not in klass.members:
        flash('You are not in this class.', 'info')
    else:
        klass.members.remove(current_user)
        db.session.commit()
        flash(f'Left "{klass.name}".', 'success')
    return redirect(url_for('my_classes'))


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

    module_progress_by_class = []
    for klass in current_user.classes:
        mods = cur.modules_with_progress(current_user.id, klass.id, klass)
        if mods:
            module_progress_by_class.append({'class': klass, 'modules': mods})

    return render_template('me.html',
                           stats=stats,
                           days=days_int,
                           module_progress_by_class=module_progress_by_class)


@app.route('/teacher')
@login_required
@role_required('admin_teacher', 'class_teacher', 'admin')
def teacher_dashboard():
    if current_user.role == 'class_teacher':
        classes = Class.query.filter_by(assigned_teacher_id=current_user.id).all()
    else:
        classes = Class.query.filter_by(teacher_id=current_user.id).all()
    return render_template('teacher/dashboard.html', classes=classes)


@app.route('/admin/my-school')
@login_required
@role_required('admin_teacher', 'admin')
def admin_my_school():
    # find school where current user is an admin_teacher member
    mem = SchoolMembership.query.filter_by(
        user_id=current_user.id, role='admin_teacher'
    ).first()
    if mem:
        return redirect(url_for('admin_courses', school_id=mem.school_id))
    # full admins: redirect to schools list
    return redirect(url_for('admin_schools'))


@app.route('/my-classes')
@login_required
def my_classes():
    return render_template('student/my_classes.html',
                           classes=current_user.classes)


@app.route('/teacher/class/<int:class_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin_teacher', 'class_teacher', 'admin')
def teacher_edit_class(class_id):
    cls = Class.query.get_or_404(class_id)
    if current_user.role == 'class_teacher' and cls.assigned_teacher_id != current_user.id:
        abort(403)
    if current_user.role == 'admin_teacher' and cls.teacher_id != current_user.id:
        abort(403)
    courses = Course.query.order_by(Course.name).all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        course_id = request.form.get('course_id', type=int)
        if not name:
            flash('Class name is required.', 'danger')
        else:
            cls.name = name
            cls.course_id = course_id or None
            db.session.commit()
            flash('Class updated.', 'success')
        return redirect(url_for('teacher_edit_class', class_id=class_id))

    # Build module/exercise data for override management
    modules_with_exercises = []
    hidden_ids = {cme.module_exercise_id for cme in cls.module_overrides if cme.action == 'hide' and cme.module_exercise_id}
    if cls.course_id and cls.course:
        for mod in cls.course.modules.order_by(Module.order).all():
            exercises = list(mod.exercises.order_by(ModuleExercise.order).all())
            modules_with_exercises.append({'module': mod, 'exercises': exercises})

    return render_template('teacher/edit_class.html', cls=cls, courses=courses,
                           modules_with_exercises=modules_with_exercises,
                           hidden_ids=hidden_ids,
                           overrides=cls.module_overrides)


@app.route('/teacher/class/new', methods=['GET', 'POST'])
@login_required
@role_required('admin_teacher', 'admin')
def teacher_new_class():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        course_id = request.form.get('course_id', type=int)
        if not name:
            flash('Class name is required.', 'danger')
            courses = Course.query.order_by(Course.name).all()
            return render_template('teacher/new_class.html', courses=courses)
        join_code = secrets.token_urlsafe(8)[:8].upper()
        cls = Class(name=name, join_code=join_code,
                    teacher_id=current_user.id,
                    course_id=course_id if course_id else None)
        db.session.add(cls)
        db.session.commit()
        flash(f'Class "{name}" created. Join code: {join_code}', 'success')
        return redirect(url_for('teacher_class_detail', class_id=cls.id))
    courses = Course.query.order_by(Course.name).all()
    return render_template('teacher/new_class.html', courses=courses)


@app.route('/teacher/class/<int:class_id>')
@login_required
@role_required('admin_teacher', 'class_teacher', 'admin')
def teacher_class_detail(class_id):
    cls = Class.query.get_or_404(class_id)
    if current_user.role == 'class_teacher' and cls.assigned_teacher_id != current_user.id:
        abort(403)
    if current_user.role == 'admin_teacher' and cls.teacher_id != current_user.id:
        abort(403)

    roster = []
    for student in cls.members:
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

    return render_template('teacher/class_detail.html', cls=cls, roster=roster)


@app.route('/teacher/classes/<int:class_id>/set_course', methods=['POST'])
@login_required
@role_required('admin_teacher', 'admin')
def teacher_set_course(class_id):
    klass = Class.query.get_or_404(class_id)
    if klass.teacher_id != current_user.id and current_user.role != 'admin':
        abort(403)
    course_id = request.form.get('course_id')
    klass.course_id = int(course_id) if course_id else None
    db.session.commit()
    flash('Course assignment updated.', 'success')
    return redirect(url_for('teacher_class_detail', class_id=class_id))


@app.route('/teacher/classes/<int:class_id>/overrides/add', methods=['POST'])
@login_required
@role_required('admin_teacher', 'class_teacher', 'admin')
def teacher_add_override(class_id):
    klass = Class.query.get_or_404(class_id)
    if current_user.role == 'class_teacher' and klass.assigned_teacher_id != current_user.id:
        abort(403)
    if current_user.role == 'admin_teacher' and klass.teacher_id != current_user.id:
        abort(403)
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
    cme = ClassModuleExercise(
        class_id=class_id,
        action=action,
        module_exercise_id=me_id,
        module_id=module_id,
        exercise_type=ex_type,
        exercise_id=ex_id,
        order=order,
        completion_criterion_json=criterion,
    )
    db.session.add(cme)
    db.session.commit()
    flash('Override added.', 'success')
    return redirect(url_for('teacher_edit_class', class_id=class_id))


@app.route('/teacher/classes/<int:class_id>/overrides/<int:cme_id>/delete', methods=['POST'])
@login_required
@role_required('admin_teacher', 'class_teacher', 'admin')
def teacher_delete_override(class_id, cme_id):
    klass = Class.query.get_or_404(class_id)
    if current_user.role == 'class_teacher' and klass.assigned_teacher_id != current_user.id:
        abort(403)
    if current_user.role == 'admin_teacher' and klass.teacher_id != current_user.id:
        abort(403)
    cme = ClassModuleExercise.query.get_or_404(cme_id)
    if cme.class_id != class_id:
        abort(403)
    db.session.delete(cme)
    db.session.commit()
    flash('Override removed.', 'success')
    return redirect(url_for('teacher_edit_class', class_id=class_id))


@app.route('/teacher/classes/<int:class_id>/modules/<int:module_id>/hide', methods=['POST'])
@login_required
@role_required('admin_teacher', 'class_teacher', 'admin')
def teacher_hide_module(class_id, module_id):
    klass = Class.query.get_or_404(class_id)
    if current_user.role == 'class_teacher' and klass.assigned_teacher_id != current_user.id:
        abort(403)
    if current_user.role == 'admin_teacher' and klass.teacher_id != current_user.id:
        abort(403)
    module = Module.query.get_or_404(module_id)
    for ex in module.exercises:
        exists = ClassModuleExercise.query.filter_by(
            class_id=class_id, module_exercise_id=ex.id, action='hide'
        ).first()
        if not exists:
            db.session.add(ClassModuleExercise(
                class_id=class_id,
                module_id=module_id,
                module_exercise_id=ex.id,
                action='hide'
            ))
    db.session.commit()
    flash(f'Module "{module.name}" hidden for this class.', 'success')
    return redirect(url_for('teacher_edit_class', class_id=class_id))


@app.route('/teacher/classes/<int:class_id>/modules/<int:module_id>/restore', methods=['POST'])
@login_required
@role_required('admin_teacher', 'class_teacher', 'admin')
def teacher_restore_module(class_id, module_id):
    klass = Class.query.get_or_404(class_id)
    if current_user.role == 'class_teacher' and klass.assigned_teacher_id != current_user.id:
        abort(403)
    if current_user.role == 'admin_teacher' and klass.teacher_id != current_user.id:
        abort(403)
    ClassModuleExercise.query.filter_by(
        class_id=class_id, module_id=module_id, action='hide'
    ).delete()
    db.session.commit()
    flash('Module restored.', 'success')
    return redirect(url_for('teacher_edit_class', class_id=class_id))


@app.route('/teacher/classes/<int:class_id>/module_exercises/add', methods=['POST'])
@login_required
@role_required('admin_teacher', 'class_teacher', 'admin')
def teacher_add_module_exercise(class_id):
    klass = Class.query.get_or_404(class_id)
    if current_user.role == 'class_teacher' and klass.assigned_teacher_id != current_user.id:
        abort(403)
    if current_user.role == 'admin_teacher' and klass.teacher_id != current_user.id:
        abort(403)
    module_id = request.form.get('module_id', type=int)
    exercise_type = request.form.get('exercise_type', '').strip()
    exercise_id = request.form.get('exercise_id', type=int)
    name = request.form.get('name', '').strip()
    order = request.form.get('order', type=int) or 0
    if not all([module_id, exercise_type, exercise_id]):
        flash('All fields required.', 'danger')
        return redirect(url_for('teacher_edit_class', class_id=class_id))
    me = ModuleExercise(
        module_id=module_id,
        exercise_type=exercise_type,
        exercise_id=exercise_id,
        name=name or exercise_type,
        order=order,
    )
    db.session.add(me)
    db.session.commit()
    flash(f'Exercise "{me.name}" added to module.', 'success')
    return redirect(url_for('teacher_edit_class', class_id=class_id))


@app.route('/teacher/join', methods=['POST'])
@login_required
def join_class():
    code = request.form.get('join_code', '').strip().upper()
    if not code:
        flash('Please enter a join code.', 'danger')
        return redirect(url_for('me'))
    cls  = Class.query.filter_by(join_code=code).first()
    if not cls:
        flash('Invalid join code.', 'danger')
    elif current_user in cls.members:
        flash('You are already in this class.', 'info')
    else:
        cls.members.append(current_user)
        db.session.commit()
        flash(f'Joined "{cls.name}".', 'success')
    return redirect(url_for('me'))


# ---------------------------------------------------------------------------
# Student class routes
# ---------------------------------------------------------------------------

@app.route('/class/<int:class_id>')
@login_required
def class_home(class_id):
    klass = Class.query.get_or_404(class_id)
    is_member = current_user in klass.members
    is_own_teacher = klass.teacher_id == current_user.id
    if not is_member and not is_own_teacher and current_user.role != 'admin':
        abort(403)
    has_course = klass.course_id is not None
    return render_template('student/mode_select.html', klass=klass, has_course=has_course)


@app.route('/class/<int:class_id>/modules')
@login_required
def class_modules(class_id):
    klass = Class.query.get_or_404(class_id)
    is_member = current_user in klass.members
    is_own_teacher = klass.teacher_id == current_user.id
    if not is_member and not is_own_teacher and current_user.role != 'admin':
        abort(403)
    if not klass.course_id:
        flash('This class has no course assigned yet.', 'info')
        return redirect(url_for('class_home', class_id=class_id))
    mods = cur.modules_with_progress(current_user.id, class_id, klass)
    return render_template('student/module_list.html', klass=klass, mods=mods)


@app.route('/class/<int:class_id>/modules/<int:module_id>')
@login_required
def class_module_detail(class_id, module_id):
    klass  = Class.query.get_or_404(class_id)
    is_member = current_user in klass.members
    is_own_teacher = klass.teacher_id == current_user.id
    if not is_member and not is_own_teacher and current_user.role != 'admin':
        abort(403)
    module = Module.query.get_or_404(module_id)
    if klass.course_id is None or module.course_id != klass.course_id:
        abort(404)
    exercises = cur.effective_exercises(klass, module)
    done = cur.completion_map(current_user.id, class_id)
    ex_with_status = []
    for ex in exercises:
        key = (ex['module_exercise_id'], ex['class_exercise_id'])
        completion = cur.get_completion(
            current_user.id, class_id,
            ex['module_exercise_id'], ex['class_exercise_id']
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
                                      class_id=class_id,
                                      me_id=ex['module_exercise_id'])
        else:
            type_to_route = {
                'melody':   ('exercise',          'melody_id'),
                'rhythm':   ('rhythm_exercise',   'rhythm_id'),
                'harmonic': ('harmonic_exercise', 'progression_id'),
                'holistic': ('holistic_exercise', 'exercise_id'),
            }
            route_name, param_name = type_to_route.get(ex['exercise_type'], ('class_home', 'class_id'))
            ex['start_url'] = url_for(route_name,
                                      **{param_name: ex['exercise_id']},
                                      class_id=class_id,
                                      me_id='', cme_id=ex['class_exercise_id'] or '')

        # Progress
        me_obj2 = ModuleExercise.query.get(ex['module_exercise_id']) if ex['module_exercise_id'] else None
        criterion = me_obj2.completion_criterion if me_obj2 else {'attempts': 1}
        ex['progress'] = cur.get_progress(
            current_user.id, class_id,
            ex['module_exercise_id'], ex['class_exercise_id'],
            criterion
        )
    return render_template('student/module_detail.html',
                           klass=klass,
                           module=module,
                           exercises=ex_with_status)


@app.route('/class/<int:class_id>/module_exercise/<int:me_id>/start')
@login_required
def start_module_exercise(class_id, me_id):
    klass = Class.query.get_or_404(class_id)
    is_member = current_user in klass.members
    is_own_teacher = klass.teacher_id == current_user.id
    if not is_member and not is_own_teacher and current_user.role != 'admin':
        abort(403)

    me = ModuleExercise.query.get_or_404(me_id)
    if me.module.course_id != klass.course_id:
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
                                class_id=class_id, me_id=me_id, cme_id='',
                                module_id=module_id, kp=kp))

    model_class, route_name, param_name = type_map[me.exercise_type]
    q = model_class.query.filter(_visible_exercise_filter(model_class))
    q = _apply_exercise_filters(q, model_class, params)
    candidates = q.all()

    if not candidates:
        flash('No exercises match the filters for this module exercise. Ask your teacher to adjust the filters.', 'warning')
        return redirect(url_for('class_module_detail',
                                class_id=class_id, module_id=module_id))

    chosen = random.choice(candidates)
    return redirect(url_for(route_name,
                            **{param_name: chosen.id},
                            class_id=class_id, me_id=me_id, cme_id='',
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
