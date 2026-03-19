# Holistic Dictation — Implementation Plan

## Overview

Add a Holistic Dictation mode to the Musicianship Trainer. Each exercise is a real audio recording (WAV) the user listens to and then transcribes across multiple simultaneous layers: a primary melody staff, any number of additional melody or rhythm staves, and a chord block row beneath all staves. Everything is laid out in synchronized systems (like a real conductor's score) that scroll vertically. The results page offers both per-line MIDI playback and the original WAV.

Read this document fully before writing any code. Cross-reference `HARMONIC_DICTATION_PLAN.md` for chord block logic — holistic dictation reuses the same chord-building system with one addition (note durations on blocks).

---

## 1. Dependencies

No new Python packages beyond those already added for harmonic dictation (`mido`, `midiutil`). For generating a test WAV file in the seeding script, use Python's built-in `wave` and `struct` modules (no external dependencies).

---

## 2. Folder structure for exercise assets

Each exercise lives in a subfolder under `static/holistic/`. The folder name becomes the DB lookup key.

```
static/
  holistic/
    waltz_c_major/
      audio.wav          ← primary listening file (required)
      melody.mid         ← primary melody line (required)
      harmony.mid        ← chord progression (required)
      melody_1.mid       ← additional melody/countermelody (optional)
      melody_2.mid       ← (optional, and so on)
      rhythm_1.mid       ← rhythm/percussion line (optional)
      rhythm_2.mid       ← (optional, and so on)
```

Filenames are fixed conventions — `melody.mid`, `harmony.mid`, `melody_N.mid`, `rhythm_N.mid`. The DB stores the folder name and the extra-line metadata; individual filenames are derived by convention.

---

## 3. Database — additions to `models.py`

### 3a. Association table

```python
holistic_tags = db.Table(
    'holistic_tags',
    db.Column('exercise_id', db.Integer, db.ForeignKey('holistic_exercise.id'), primary_key=True),
    db.Column('tag_id',      db.Integer, db.ForeignKey('tag.id'),               primary_key=True),
)
```

### 3b. `HolisticExercise` model

```python
class HolisticExercise(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(100), nullable=False)
    description    = db.Column(db.String(300))

    # Path to the exercise folder, relative to static/
    # e.g. "holistic/waltz_c_major/"
    folder         = db.Column(db.String(200), nullable=False)

    # WAV filename within the folder, e.g. "audio.wav"
    wav_filename   = db.Column(db.String(100), nullable=False, default='audio.wav')

    key_signature  = db.Column(db.String(10),  default='C')
    time_signature = db.Column(db.String(10),  default='4/4')
    tempo          = db.Column(db.Integer,     default=120)
    difficulty     = db.Column(db.Integer,     default=1)   # 1–5
    is_major       = db.Column(db.Boolean,     default=True) # True=major, False=minor

    # Clef for the primary melody line
    melody_clef    = db.Column(db.String(10),  default='treble')

    # Parsed correct answers (JSON), generated at seed time from MIDI files.
    # Array of {key, duration[, dotted]} objects — same format as Melody.notes_json
    melody_notes_json  = db.Column(db.Text, nullable=False, default='[]')

    # Parsed chord progression — same format as ChordProgression.chords_json
    harmony_chords_json = db.Column(db.Text, nullable=False, default='[]')

    # Extra lines metadata + parsed answer data.
    # JSON array. Each element:
    #   For a melody line:
    #     {"type": "melody", "file": "melody_1.mid", "label": "Alto", "clef": "treble",
    #      "notes": [{key, duration[, dotted]}, ...]}
    #   For a rhythm line:
    #     {"type": "rhythm", "file": "rhythm_1.mid", "label": "Kick drum",
    #      "notes": [{duration[, dotted]}, ...]}
    extra_lines_json = db.Column(db.Text, nullable=False, default='[]')

    tags = db.relationship('Tag', secondary=holistic_tags,
                           backref='holistic_exercises', lazy='subquery')

    @property
    def melody_notes(self):
        return json.loads(self.melody_notes_json)

    @property
    def harmony_chords(self):
        return json.loads(self.harmony_chords_json)

    @property
    def extra_lines(self):
        return json.loads(self.extra_lines_json)

    @property
    def wav_url_path(self):
        """Relative URL path for the WAV file, suitable for url_for('static', ...)."""
        return self.folder.rstrip('/') + '/' + self.wav_filename

    @property
    def total_beats(self):
        beat_map = {'w': 4, 'h': 2, 'q': 1, '8': 0.5, '16': 0.25}
        total = 0.0
        for n in self.melody_notes:
            base = beat_map.get(n['duration'].rstrip('r'), 1)
            total += base * 1.5 if n.get('dotted') else base
        return total

    @property
    def num_measures(self):
        numerator   = int(self.time_signature.split('/')[0])
        denominator = int(self.time_signature.split('/')[1])
        beats_per_measure = numerator * (4.0 / denominator)
        return max(1, int(self.total_beats / beats_per_measure + 0.9999))

    def __repr__(self):
        return f'<HolisticExercise {self.name}>'
```

### 3c. `HolisticAttempt` model

User input is stored as a JSON dict keyed by line identifier. The keys are:
- `"melody"` — primary melody
- `"melody_1"`, `"melody_2"`, etc. — extra melody lines (matching `extra_lines` order)
- `"rhythm_1"`, `"rhythm_2"`, etc. — rhythm lines
- `"harmony"` — chord blocks

```python
class HolisticAttempt(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    exercise_id = db.Column(db.Integer, db.ForeignKey('holistic_exercise.id'), nullable=False)
    exercise    = db.relationship('HolisticExercise', backref='attempts')

    # JSON dict: {"melody": [...notes...], "harmony": [...chords...],
    #             "melody_1": [...], "rhythm_1": [...], ...}
    user_data_json = db.Column(db.Text, nullable=False, default='{}')

    # JSON dict of individual scores: {"melody_pitch": 85.0, "melody_duration": 72.0,
    #   "harmony_letter": 90.0, "harmony_quality": 80.0,
    #   "melody_1_pitch": 60.0, "melody_1_duration": 50.0,
    #   "rhythm_1_duration": 70.0}
    scores_json    = db.Column(db.Text, nullable=False, default='{}')

    overall_score  = db.Column(db.Float, default=0.0)
    created_at     = db.Column(db.DateTime, server_default=db.func.now())

    @property
    def user_data(self):
        return json.loads(self.user_data_json)

    @property
    def scores(self):
        return json.loads(self.scores_json)

    def __repr__(self):
        return f'<HolisticAttempt ex={self.exercise_id} score={self.overall_score:.1f}>'
```

---

## 4. Grading helper — additions to `app.py`

```python
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
            scores[f'{lkey}_pitch']    = p
            scores[f'{lkey}_duration'] = d
        elif ltype == 'rhythm':
            d = grade_rhythm(correct, user_line)
            scores[f'{lkey}_duration'] = d

    overall = round(sum(scores.values()) / len(scores), 1) if scores else 0.0
    return scores, overall
```

---

## 5. New module — `generate_holistic_exercises.py`

Create `generate_holistic_exercises.py` in the project root. This script:

1. Creates the folder `static/holistic/` if it doesn't exist.
2. For each sample exercise defined in the script:
   a. Creates the exercise subfolder.
   b. Uses `midiutil.MIDIFile` to write `melody.mid` and `harmony.mid`.
   c. Generates a test WAV file programmatically using Python's built-in `wave` + `struct` modules (sine-wave synthesis, no external dependencies). The WAV plays each chord tone simultaneously for the correct duration. Quality is rough but functional for testing — the developer should replace it with a real recording.
   d. Parses the MIDI files using existing utilities (`midi_to_notes.py` for melody, `chord_utils.infer_chords_from_midi` for harmony).
   e. Seeds the `HolisticExercise` table using Flask app context.

### WAV generation approach

Use 44100 Hz, mono, 16-bit PCM. For each chord in the progression:
- Compute the chord tones (MIDI pitch numbers).
- Synthesise N samples = `int(chord_duration_seconds * 44100)` by summing sine waves for each pitch with a simple amplitude envelope (short attack, slight decay).
- Write to the WAV file sequentially.

```python
import wave, struct, math

def generate_wav(filepath, chords_with_durations, tempo_bpm, sample_rate=44100):
    """
    chords_with_durations: list of (midi_pitches, duration_beats)
    """
    frames = []
    seconds_per_beat = 60.0 / tempo_bpm
    for pitches, beats in chords_with_durations:
        n_samples = int(beats * seconds_per_beat * sample_rate)
        for i in range(n_samples):
            t = i / sample_rate
            amp_env = min(1.0, t * 20) * max(0.0, 1 - t * 0.3)  # simple envelope
            sample = sum(math.sin(2 * math.pi * (440 * 2**((p - 69) / 12)) * t)
                         for p in pitches) / max(len(pitches), 1) * amp_env
            frames.append(struct.pack('<h', int(sample * 16000)))
    with wave.open(filepath, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join(frames))
```

### Sample exercises to seed — exactly 2

**Exercise 1 — `simple_melody_with_chords` (C major, 4/4, difficulty 1)**

- Folder: `holistic/simple_c_major/`
- Key: C major, Tempo: 80, Time sig: 4/4, Difficulty: 1, is_major: True
- Melody clef: treble
- No extra lines (melody + harmony only)
- Primary melody (8 quarter notes): C4–E4–G4–E4–F4–D4–G4–C4 (2 measures)
- Harmony (half-note chords): I (C, 2 beats), V (G, 2 beats), IV (F, 2 beats), I (C, 2 beats)
- Melody MIDI voicings: single notes as above
- Harmony MIDI voicings: same as `harm_c_major_I_IV_V_I.mid` but with half-note durations
- WAV: generated using `generate_wav` with the harmony chord tones + melody sine wave mixed
- Tags: none
- MIDI filenames: `melody.mid`, `harmony.mid`

**Exercise 2 — `melody_with_bass_and_chords` (G major, 4/4, difficulty 2)**

- Folder: `holistic/g_major_melody_bass/`
- Key: G major, Tempo: 88, Time sig: 4/4, Difficulty: 2, is_major: True
- Melody clef: treble
- Extra lines:
  - `{"type": "melody", "file": "melody_1.mid", "label": "Bass line", "clef": "bass", "notes": [...]}`
- Primary melody (8 quarter notes): G4–A4–B4–G4–A4–C5–B4–G4 (2 measures)
- Bass line (whole notes): G2, D2 (one note per measure)
- Harmony (half-note chords): I (G, 2 beats), V (D, 2 beats), IV (C, 2 beats), I (G, 2 beats)
- WAV: mix of melody + bass + chord tones synthesised together
- Tags: none

---

## 6. Routes — additions to `app.py`

### 6a. Index / selection page

```python
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
```

### 6b. Exercise page

```python
@app.route('/holistic/exercise/<int:exercise_id>')
def holistic_exercise(exercise_id):
    exercise = HolisticExercise.query.get_or_404(exercise_id)
    chords   = exercise.harmony_chords
    unlock_seventh    = any(c.get('seventh')    for c in chords)
    unlock_extensions = any(c.get('extensions') for c in chords)
    unlock_sus        = any(c.get('sus')        for c in chords)
    return render_template('holistic_exercise.html',
                           exercise=exercise,
                           unlock_seventh=unlock_seventh,
                           unlock_extensions=unlock_extensions,
                           unlock_sus=unlock_sus)
```

### 6c. Submit endpoint

```python
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
```

### 6d. Results page

```python
@app.route('/holistic/results/<int:attempt_id>')
def holistic_results(attempt_id):
    attempt  = HolisticAttempt.query.get_or_404(attempt_id)
    exercise = attempt.exercise
    return render_template('holistic_results.html',
                           attempt=attempt,
                           exercise=exercise)
```

### 6e. Update imports in `app.py`

```python
from models import db, Melody, Tag, UserAttempt, Rhythm, RhythmAttempt, \
                   ChordProgression, HarmonicAttempt, HolisticExercise, HolisticAttempt
```

---

## 7. Template — `templates/holistic_index.html`

Extend `base.html`. This page is a **browse-and-select** interface, not a random redirect.

### Layout:

**Filter sidebar** (left, same Bootstrap column pattern as other index pages):
- Time signature (checkboxes, populated from DB)
- Tonality: Major / Minor (checkboxes)
- Contains chord (checkboxes, from `contains:` tags, strip prefix for display as in harmonic index)
- Difficulty (checkboxes 1–5)
- "Other tags" section for any remaining tags

**Exercise list** (right, main column):
- A card or table row for each exercise that matches the active filters.
- Filter logic is **client-side JavaScript** (no page reload): as the user checks/unchecks filters, the list updates in real time. Each exercise row has `data-` attributes for `time_signature`, `is_major`, `difficulty`, and `tags` so JS can filter without hitting the server.
- Each row shows: Exercise name, Key, Time sig, Difficulty badge, tag chips.
- Clicking a row (or a "Start" button on the row) navigates to `/holistic/exercise/<id>`.
- If no exercises match the filters, show a "No exercises match your filters" message.

---

## 8. Template — `templates/holistic_exercise.html`

Extend `base.html`. Load VexFlow, Tone.js, and `@tonejs/midi` from the same CDNs used in `exercise.html`.

### Layout:

**Breadcrumb:** Holistic Dictation > [Exercise Name]

**Listen card:**
- **Play WAV / Stop buttons** — controls an HTML `<audio>` element (see §9a). Label: "Play Recording".
- **Play count badge** (same as other exercises).
- **Key Reference button** — same as harmonic exercise: plays I–IV–V–I (or i–iv–V–i) using `HARM_KEY_REFERENCE` from `harmonic.js`. This requires `harmonic.js` to be loaded on this page.
- **Key display badge** (same as harmonic exercise — plain text, e.g., "Key: G major").
- Instructional text: "Listen as many times as needed before submitting."

**Staff visibility controls card:**
- A row of toggle checkboxes, one per staff + one for harmony:
  - "Melody" (always present, checked by default)
  - "[Label]" for each extra line (checked by default)
  - "Harmony" (checked by default)
- Toggling a checkbox hides/shows the corresponding staff or harmony row in the score area.
- **Hiding does NOT remove from submission or grading** — it is a display-only toggle for focus.

**Score area (the main working area):**

The score area renders a continuous sequence of **systems** stacked vertically. Each system contains all active (visible) staves for a group of measures, followed immediately by the chord row below the last staff. The number of measures per system is determined adaptively at render time.

```
┌────────────────────────────────────────────────────────┐
│ [Treble clef] [Key sig] [Time sig]  |  measure 1  |  measure 2  │  ← primary melody staff
│ [Bass clef]   [Key sig]             |  measure 1  |  measure 2  │  ← extra melody line (if any)
│ [Perc clef]                         | ○  ○   ○    |   ○   ○     │  ← rhythm line (if any)
│ ─────────────────────────────────────────────────────  │
│ HARMONY: [block A      ][block B][block C         ]    │  ← chord row (same width as staves above)
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│  (next system: measures 3 & 4)                         │
│  ...                                                   │
└────────────────────────────────────────────────────────┘
```

**Staff labels:** Each staff has a short label to the left of the clef: "Melody", or the custom label from `extra_lines_json` (e.g., "Alto", "Bass line", "Kick drum"). The chord row has a label "Harmony" on the left.

**Palette & modifier panel** (below the score area, sticky at bottom of page or in a fixed panel):
Structured the same as the harmonic exercise's Build Your Answer card, with the following changes:
- **Duration selector row** is added (same as melodic exercise: 16th, 8th, Qtr, Half, Whole, Dot button) — this sets the duration of the next chord block placed.
- The diatonic palette, modifier panel, and notation toggle are identical to harmonic dictation.
- **Undo / Clear** buttons apply only to the harmony row.
- Note that when editing melody staves, the user interacts directly with VexFlow notation as in the melodic exercise (click staff, drag notes). The palette/modifier panel is only for harmony.

**Submit / Back buttons** at bottom of page.

### Template data injected from Flask:

```html
<script>
  const EXERCISE_ID       = {{ exercise.id }};
  const WAV_URL           = "{{ url_for('static', filename=exercise.wav_url_path) }}";
  const KEY_SIGNATURE     = "{{ exercise.key_signature }}";
  const TIME_SIG_TOP      = {{ exercise.time_signature.split('/')[0] }};
  const TIME_SIG_BOTTOM   = {{ exercise.time_signature.split('/')[1] }};
  const NUM_MEASURES      = {{ exercise.num_measures }};
  const MELODY_CLEF       = "{{ exercise.melody_clef }}";

  // Extra lines metadata (without correct answer data — those stay server-side)
  const EXTRA_LINES = {{ exercise.extra_lines | map(attribute='type')
                         | zip(exercise.extra_lines | map(attribute='label'))
                         | zip(exercise.extra_lines | map(attribute='file'))
                         | list | tojson }};
  // NOTE: Use a route-computed variable instead of complex Jinja. See below.

  const UNLOCK_SEVENTH    = {{ unlock_seventh | tojson }};
  const UNLOCK_EXTENSIONS = {{ unlock_extensions | tojson }};
  const UNLOCK_SUS        = {{ unlock_sus | tojson }};
</script>
```

**Preferred approach** — compute `EXTRA_LINES` in the route as a simplified list (no correct answer data, just display info):

```python
extra_lines_display = [
    {'key':   l['file'].replace('.mid', ''),
     'type':  l['type'],
     'label': l['label'],
     'clef':  l.get('clef', 'treble')}
    for l in exercise.extra_lines
]
```

Pass `extra_lines_display` to the template and use `{{ extra_lines_display | tojson }}` for the JS constant.

---

## 9. JavaScript — `static/js/holistic.js`

This is the largest and most complex file. It coordinates three separate subsystems: WAV playback, VexFlow staff notation (reusing logic from `notation.js`), and the chord block row (reusing logic from `harmonic.js`).

### 9a. WAV playback

Use an HTML `<audio>` element:

```html
<audio id="wav-player" src="{{ wav_url }}" preload="auto"></audio>
```

The Play button calls `document.getElementById('wav-player').play()`. The Stop button calls `.pause()` and resets `.currentTime = 0`. Update the play count badge on each play event.

This is intentionally simple — no Tone.js or MIDI involved for the main listening experience.

### 9b. System layout engine

The score area is rendered by a `renderScore()` function that:

1. **Determines measures per system** by binary-searching for the largest M such that a VexFlow formatter with M measures fits within the container width. Practically: start with M=4 and decrease until the formatter succeeds without overflow.

2. **For each system (group of M measures):**
   a. Creates a `<div class="score-system">` container.
   b. Inside it, creates one `<canvas>` or `<svg>` per staff using VexFlow. Each staff is rendered at the same horizontal width so all staves in a system are exactly aligned.
   c. After rendering all staves, reads the x-coordinates of the measure bar lines from the VexFlow `Stave` objects. These give the exact pixel x-position of each measure boundary.
   d. Creates the chord row div (see §9c) using these x-coordinates to align chord measure cells.

3. **Note interaction** (click to place, drag to change pitch) is set up per-stave the same way as in `notation.js`. Each stave tracks its own `notes` array. Line key (e.g., `"melody"`, `"melody_1"`) is stored as a data attribute on the stave container.

### 9c. Chord row

The chord row is a `<div class="holistic-chord-row">` placed immediately below the last staff in each system. It contains one `<div class="chord-measure-cell">` per measure in the system, with width in pixels matching the VexFlow measure widths obtained in §9b.

Within each measure cell, chord blocks are positioned using absolute pixel offsets calculated from their beat position:
```
block_left_px = (beat_offset / beats_per_measure) * cell_width_px
block_width_px = (chord_duration_beats / beats_per_measure) * cell_width_px
```

Chord blocks snap to beat positions (1-beat granularity by default; allow 0.5-beat snapping for eighth-note chords). A block cannot extend past its measure boundary — if the remaining duration exceeds the measure end, it is clipped and a continuation block is placed in the next measure cell.

The duration selector (from the palette panel) sets the duration of the next block to be placed. Clicking within a chord measure cell places a chord block at the nearest beat position.

Block selection, modifier panel, and notation toggle are identical to `harmonic.js`. Extract the chord-block logic from `harmonic.js` into a shared module `chord_block_utils.js` so both `harmonic.js` and `holistic.js` can import it without duplicating code.

> **Implementation note:** `chord_block_utils.js` should export: `formatChordName`, `computeChordTones`, `applyModifier`, `renderChordBlock`. Both `harmonic.js` and `holistic.js` load this file and call its functions.

### 9d. Submission

Collect all line data into a single dict:

```js
async function submitAttempt() {
  const lines = {};

  // Melody staves (one per staff container)
  document.querySelectorAll('[data-line-key]').forEach(el => {
    lines[el.dataset.lineKey] = getNotesForStave(el);
  });

  // Harmony
  lines['harmony'] = getChordBlocks();

  const response = await fetch(`/holistic/submit/${EXERCISE_ID}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ lines })
  });
  const data = await response.json();
  if (data.redirect) window.location.href = data.redirect;
}
```

---

## 10. Template — `templates/holistic_results.html`

Extend `base.html`. Load VexFlow, Tone.js, `@tonejs/midi`, and the same CDN scripts as `exercise.html`.

### Layout:

**Breadcrumb:** Holistic Dictation > Results > [Exercise Name]

**Score summary card** (top):
```
Overall: XX%
Melody — Pitch: XX%  Rhythm: XX%
Harmony — Letter: XX%  Quality: XX%
[Label] — Pitch: XX%  Rhythm: XX%  (per extra melody line)
[Label] — Rhythm: XX%              (per rhythm line)
```
Scores are passed from the route via `attempt.scores` (already a dict).

**Playback card:**
Three playback options in a button group or tab:
1. **Original Recording** — plays the WAV file (`<audio>` element, same as exercise page).
2. **Correct Answer (MIDI)** — plays the correct MIDI data using Tone.js:
   - Melody + extra melody lines: use `playNoteArray` from `player.js` for each, sequentially or with a selector.
   - Harmony: use `playChordArray` from `harmonic.js`.
   - Rhythm lines: use a click/tick sound. Implement `playRhythmArray(notes, bpm, onDone)` in `holistic.js` using `Tone.MembraneSynth` (a kick-drum-like synth) at pitch C1. One hit per note onset.
   - A "Play all lines together" button mixes all lines simultaneously using Tone.js scheduling.
3. **My Answer (MIDI)** — same as above but using the user's submitted data.

> **Implementation note:** "Play all lines together" requires scheduling all note events on the Tone.js timeline simultaneously. Use `Tone.Transport` with absolute time positions (in beats) for each event across all lines, then start Transport. Use a separate Tone.js synth per line to avoid conflicts.

**Correct Answer score** (staves and chord row rendered read-only):
- Render all staves showing the correct notes in green, same system layout as the exercise page.
- Below each system, the correct chord blocks in green.
- Label each staff with its name as on the exercise page.

**Your Answer score** (staves and chord row rendered read-only):
- Same layout as correct answer, but:
  - Each note is coloured green (correct pitch + duration), yellow (correct pitch, wrong duration), orange (wrong pitch, correct duration), or red (both wrong).
  - Each chord block is coloured green (letter + quality correct), yellow (letter correct, quality wrong), or red (letter wrong).

**Back / Next button:** "Try Another" links back to `/holistic` (the selection page, not a random redirect, since holistic dictation is browse-based).

---

## 11. CSS additions — `static/css/style.css`

```css
/* Score system container */
.score-system {
  margin-bottom: 1.5rem;
  position: relative;
}

/* Chord row below staves */
.holistic-chord-row {
  display: flex;
  align-items: stretch;
  min-height: 52px;
  border-top: 2px solid #dee2e6;
  background: #f8f9fa;
}

/* Label column on the left of each staff row and chord row */
.staff-label {
  width: 80px;
  flex-shrink: 0;
  font-size: 0.75rem;
  font-weight: 600;
  color: #6c757d;
  display: flex;
  align-items: center;
  padding-left: 4px;
}

/* Individual measure cell in the chord row */
.chord-measure-cell {
  position: relative;
  border-right: 1px solid #ced4da;
  flex-shrink: 0;
  /* width is set inline by JS to match VexFlow measure width */
}
.chord-measure-cell:last-child { border-right: none; }

/* Chord blocks in holistic view (extend the base .chord-block styles) */
.chord-block.holistic {
  position: absolute;
  height: 44px;
  top: 4px;
  /* left and width set inline by JS */
  min-width: 32px;
}

/* Staff visibility toggle row */
.staff-toggle-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: center;
  padding: 0.5rem 0;
}

/* Results: note colour coding */
.note-correct        { fill: #198754 !important; }
.note-pitch-wrong    { fill: #dc3545 !important; }
.note-duration-wrong { fill: #ffc107 !important; }
.note-both-wrong     { fill: #dc3545 !important; }
```

---

## 12. Home page update — `templates/home.html`

Update the Holistic Dictation card to be active (same pattern as Harmonic Dictation was activated). Use **cyan** for the card footer:

```html
<a href="{{ url_for('holistic_index') }}" class="text-decoration-none">
  <div class="card shadow-sm h-100 border-0 home-card">
    <div class="card-body p-4 text-center">
      <h2 class="h4 fw-bold mb-2">Holistic Dictation</h2>
      <p class="text-muted mb-0">
        Full musical passage dictation combining melody, harmony, and rhythm
        into a complete transcription exercise.
      </p>
    </div>
    <div class="card-footer text-white text-center fw-semibold py-2" style="background: #0dcaf0; color: #000 !important;">
      Start &rarr;
    </div>
  </div>
</a>
```

Note: Bootstrap's `bg-info` is `#0dcaf0` (cyan). Use `color: #000 !important` since cyan is light and white text would be hard to read.

---

## 13. Shared module — `static/js/chord_block_utils.js`

Before implementing `harmonic.js` changes or `holistic.js`, **refactor** the chord-block logic from `harmonic.js` into this shared utility file. Functions to extract:

- `formatChordName(chord, mode, keySignature)` — chord display name calculation
- `computeChordTones(chord)` — returns set of pitch classes in the chord (for bass button colouring)
- `diatonicPalette(keySignature)` — returns the 7 diatonic triad objects for a key
- `applyQualityChange(block, newQuality)` — applies quality change with correct modifier reset rules (from plan §8d)
- `HARM_KEY_REFERENCE` — the key reference lookup table

Update `harmonic.js` to `import`/load `chord_block_utils.js` first and use its exports. Update `holistic_exercise.html` to also load `chord_block_utils.js` before `holistic.js`.

Since these are plain JS files (not ES modules), use a simple pattern: `chord_block_utils.js` assigns to `window.ChordBlockUtils = { ... }`, and both consumer files call `window.ChordBlockUtils.formatChordName(...)`.

---

## 14. Key edge cases and constraints

1. **No extra lines** — many exercises will have just melody + harmony. The system layout must work correctly with only one staff.
2. **Rhythm line staves** — use a single-line percussion staff in VexFlow (`Stave` with `addClef('percussion')`). Notes are placed on the center line only; pitch is ignored for grading.
3. **Chord block spanning a system break** — if a chord block's duration causes it to extend past the last measure in a system, it continues in the first chord cell of the next system. Render a visual "continuation" indicator (a small arrow or dashed right edge) on the block end, and an "incoming" indicator at the start of the next system.
4. **WAV file missing** — if the WAV file is not found at the expected URL (404), the Play button should display an error state ("Audio not available") rather than silently failing.
5. **Key signature rendering in VexFlow** — all staves in a system must display the same key signature. The key signature is shown on the first system only (first measure of each staff), per standard notation convention.
6. **Holistic exercises with no harmony** — if `harmony.mid` is empty (no chords), the chord row should still render but show a "No harmony" placeholder message.
7. **Performance** — the score rendering uses VexFlow, which can be slow for many measures. Render lazily: only render systems currently in or near the viewport. Use an IntersectionObserver to trigger rendering of off-screen systems.

---

## 15. File checklist

New files to create:
- [ ] `generate_holistic_exercises.py`
- [ ] `templates/holistic_index.html`
- [ ] `templates/holistic_exercise.html`
- [ ] `templates/holistic_results.html`
- [ ] `static/js/holistic.js`
- [ ] `static/js/chord_block_utils.js`

Files to modify:
- [ ] `models.py` — add `HolisticExercise`, `HolisticAttempt`, `holistic_tags`
- [ ] `app.py` — add 4 new routes + `grade_holistic_attempt` helper, update imports
- [ ] `static/js/harmonic.js` — refactor shared chord-block logic out into `chord_block_utils.js`
- [ ] `templates/home.html` — activate Holistic Dictation card with cyan footer
- [ ] `static/css/style.css` — add holistic score layout styles
