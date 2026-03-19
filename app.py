import json
import os
import random
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from models import db, Melody, Tag, UserAttempt, Rhythm, RhythmAttempt, \
                   ChordProgression, HarmonicAttempt, HolisticExercise, HolisticAttempt
from chord_utils import grade_harmonic_attempt, format_chord_name

app = Flask(__name__)

# ── Database ─────────────────────────────────────────────────────────────────
# Render (and most PaaS providers) supply a DATABASE_URL env var pointing to
# their managed Postgres instance.  SQLAlchemy requires the scheme to be
# "postgresql://" rather than the legacy "postgres://" that some providers emit.
_db_url = os.environ.get('DATABASE_URL', 'sqlite:///musicianship.db')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ── Secret key ───────────────────────────────────────────────────────────────
# In production set the SECRET_KEY environment variable to a long random string.
# Locally it falls back to the dev placeholder (sessions are not sensitive here).
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

db.init_app(app)


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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def home():
    return render_template('home.html')


@app.route('/absolute-pitch')
def absolute_pitch():
    return render_template('absolute_pitch.html')


@app.route('/melodic')
def melodic_index():
    all_tags = Tag.query.order_by(Tag.name).all()
    melodies = Melody.query.all()
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
    )
    db.session.add(attempt)
    db.session.commit()

    return jsonify({'redirect': url_for('results', attempt_id=attempt.id)})


@app.route('/results/<int:attempt_id>')
def results(attempt_id):
    attempt = UserAttempt.query.get_or_404(attempt_id)
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

    return render_template('results.html', attempt=attempt, melody=melody,
                           comparison=comparison, next_url=next_url)


# ---------------------------------------------------------------------------
# Rhythm routes
# ---------------------------------------------------------------------------

@app.route('/rhythm')
def rhythm_index():
    all_tags = Tag.query.filter(Tag.rhythms.any()).order_by(Tag.name).all()
    rhythms = Rhythm.query.all()
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
    )
    db.session.add(attempt)
    db.session.commit()

    return jsonify({'redirect': url_for('rhythm_results', attempt_id=attempt.id)})


@app.route('/rhythm/results/<int:attempt_id>')
def rhythm_results(attempt_id):
    attempt = RhythmAttempt.query.get_or_404(attempt_id)
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
    return render_template('rhythm_results.html', attempt=attempt, rhythm=rhythm,
                           comparison=comparison, next_url=next_url)


# ---------------------------------------------------------------------------
# Harmonic Dictation routes
# ---------------------------------------------------------------------------

@app.route('/harmonic')
def harmonic_index():
    all_tags     = Tag.query.filter(Tag.progressions.any()).order_by(Tag.name).all()
    contains_tags = [t for t in all_tags if t.name.startswith('contains:')]
    other_tags    = [t for t in all_tags if not t.name.startswith('contains:')]
    progressions = ChordProgression.query.all()
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
    )
    db.session.add(attempt)
    db.session.commit()

    return jsonify({'redirect': url_for('harmonic_results', attempt_id=attempt.id)})


@app.route('/harmonic/results/<int:attempt_id>')
def harmonic_results(attempt_id):
    attempt     = HarmonicAttempt.query.get_or_404(attempt_id)
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

    return render_template('harmonic_results.html',
                           attempt=attempt,
                           progression=progression,
                           comparison=comparison,
                           correct_formatted=correct_formatted,
                           user_formatted=user_formatted,
                           next_url=next_url,
                           correct_chords_json=json.dumps(correct_chords),
                           user_chords_json=json.dumps(user_chords))


# ---------------------------------------------------------------------------
# Holistic Dictation routes
# ---------------------------------------------------------------------------

@app.route('/holistic')
def holistic_index():
    exercises = HolisticExercise.query.all()
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
    )
    db.session.add(attempt)
    db.session.commit()

    return jsonify({'redirect': url_for('holistic_results', attempt_id=attempt.id)})


@app.route('/holistic/results/<int:attempt_id>')
def holistic_results(attempt_id):
    attempt  = HolisticAttempt.query.get_or_404(attempt_id)
    exercise = attempt.exercise
    return render_template('holistic_results.html',
                           attempt=attempt,
                           exercise=exercise)


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
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, port=port)
