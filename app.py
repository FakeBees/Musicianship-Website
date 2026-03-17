import json
import os
import random
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from models import db, Melody, Tag, UserAttempt, Rhythm, RhythmAttempt

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
