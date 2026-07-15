# Holistic Dictation — Line Data Model & Admin Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace holistic exercises' fixed melody+harmony+extra_lines JSON blob with an ordered `HolisticLine` table (any number of melody/rhythm/harmonic lines), an admin UI to add/name/reorder lines with per-line MIDI upload, generic per-line grading, and a student-facing renderer that reads the new data with no visual change (the actual stacked-staff rendering redesign is a separate follow-on spec).

**Architecture:** New `HolisticLine` model + migration script that converts existing exercises' old columns into rows and drops those columns. Admin gets new routes/templates for line CRUD + SortableJS drag-reorder. Grading and student rendering switch from special-cased `"melody"`/`"harmony"` keys to generic iteration over `exercise.lines`, keyed by `line.id`.

**Tech Stack:** Flask, SQLAlchemy, SQLite, Jinja2, vanilla JS, SortableJS (new, via CDN).

## Global Constraints

- Any number of lines of any type (melody/rhythm/harmonic) in any mix — no hard cap; soft warning banner in the admin UI once line count exceeds 8
- Harmonic line MIDI upload auto-infers chord blocks via `chord_utils.infer_chords_from_midi` (same as the existing harmonic-exercise upload), matching melody/rhythm's auto-parse-on-upload behavior
- Drag-to-reorder uses SortableJS loaded via CDN `<script>` tag (same pattern as VexFlow/Tone.js elsewhere in this app) — no new local dependency
- `HolisticAttempt.user_data_json` and `scores_json` key by `str(line.id)`, not ad hoc strings
- Exercise-level fields (`name`, `key_signature`, `time_signature`, `tempo`, `wav_filename`) are unchanged from the prior time-sig/BPM work — this plan does not touch them except removing the now-unused MIDI-at-upload path
- Student-facing appearance must not change in this plan — same independent-canvas-per-line layout, same harmony chord-block widget look — only the underlying data source and support for N harmony instances

---

### Task 1: `HolisticLine` model + `HolisticExercise` cleanup

**Files:**
- Modify: `models.py`

**Interfaces:**
- Produces: `HolisticLine` model with fields `id`, `holistic_exercise_id`, `line_type` (`'melody'|'rhythm'|'harmonic'`), `name`, `order`, `clef` (nullable), `midi_filename`, `content_json`, and a `.content` property (`json.loads(content_json)`). `HolisticExercise.lines` — ordered relationship (`order_by='HolisticLine.order'`) that later tasks rely on.

- [ ] **Step 1: Add the `HolisticLine` model**

In `models.py`, immediately after the `HolisticExercise` class's closing `__repr__` method (currently ending at line 277, right before `class HolisticAttempt(db.Model):`), insert:

```python
class HolisticLine(db.Model):
    id                    = db.Column(db.Integer, primary_key=True)
    holistic_exercise_id  = db.Column(db.Integer, db.ForeignKey('holistic_exercise.id'), nullable=False)
    line_type             = db.Column(db.String(10), nullable=False)   # 'melody' | 'rhythm' | 'harmonic'
    name                  = db.Column(db.String(100), nullable=False)
    order                 = db.Column(db.Integer, nullable=False, default=0)
    clef                  = db.Column(db.String(10), nullable=True)    # melody only
    midi_filename         = db.Column(db.String(200), nullable=False, default='')
    content_json          = db.Column(db.Text, nullable=False, default='[]')

    exercise = db.relationship('HolisticExercise', backref=db.backref(
        'lines', order_by='HolisticLine.order', cascade='all, delete-orphan'))

    @property
    def content(self):
        return json.loads(self.content_json)

    def __repr__(self):
        return '<HolisticLine {} ({})>'.format(self.name, self.line_type)
```

- [ ] **Step 2: Remove the old fields and properties from `HolisticExercise`**

In `models.py`, within the `HolisticExercise` class (lines 198-277), delete these lines entirely:
```python
    # Clef for the primary melody line
    melody_clef    = db.Column(db.String(10),  default='treble')

    # Parsed correct answers (JSON), generated at seed time from MIDI files.
    # Array of {key, duration[, dotted]} objects -- same format as Melody.notes_json
    melody_notes_json  = db.Column(db.Text, nullable=False, default='[]')

    # Parsed chord progression -- same format as ChordProgression.chords_json
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
```
and delete the three properties:
```python
    @property
    def melody_notes(self):
        return json.loads(self.melody_notes_json)

    @property
    def harmony_chords(self):
        return json.loads(self.harmony_chords_json)

    @property
    def extra_lines(self):
        return json.loads(self.extra_lines_json)
```

- [ ] **Step 3: Recompute `total_beats`/`num_measures` from all lines, not just melody**

Replace:
```python
    @property
    def total_beats(self):
        beat_map = {'w': 4, 'h': 2, 'q': 1, '8': 0.5, '16': 0.25}
        total = 0.0
        for n in self.melody_notes:
            base = beat_map.get(n['duration'].rstrip('r'), 1)
            total += base * 1.5 if n.get('dotted') else base
        return total
```
with:
```python
    @property
    def total_beats(self):
        beat_map = {'w': 4, 'h': 2, 'q': 1, '8': 0.5, '16': 0.25}
        max_total = 0.0
        for line in self.lines:
            if line.line_type not in ('melody', 'rhythm'):
                continue
            total = 0.0
            for n in line.content:
                base = beat_map.get(n['duration'].rstrip('r'), 1)
                total += base * 1.5 if n.get('dotted') else base
            max_total = max(max_total, total)
        return max_total
```
`num_measures` (immediately below, computing from `self.total_beats` and `self.time_signature`) is unchanged — it already only reads `total_beats` and `time_signature`, both of which still exist.

- [ ] **Step 4: Verify the app still imports cleanly**

Run: `.venv/bin/python -c "import app"`
Expected: no output, exit code 0 (import succeeds — this catches any syntax errors from the edit, though the DB schema itself isn't migrated yet, so don't run the app against the real DB in this task).

- [ ] **Step 5: Commit**

```bash
git add models.py
git commit -m "feat: add HolisticLine model, remove fixed melody/harmony/extra_lines fields"
```

---

### Task 2: Migration script

**Files:**
- Create: `migrate_holistic_lines.py`

**Interfaces:**
- Consumes: `HolisticLine`, `HolisticExercise` from Task 1 (must be run only after Task 1's model changes are committed, since it calls `db.create_all()` to create the `holistic_line` table from the new model).

- [ ] **Step 1: Write the migration script**

Create `migrate_holistic_lines.py` following the existing `migrate_phase4_schema.py` pattern in this repo (raw SQLite connection for schema changes, `app.app_context()` for ORM access):

```python
"""
Holistic lines migration
=========================
Converts each HolisticExercise's melody_notes_json / harmony_chords_json /
extra_lines_json into HolisticLine rows, then drops those columns plus
melody_clef from holistic_exercise.

Run once: python3 migrate_holistic_lines.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from app import app
from models import db, HolisticExercise, HolisticLine


def col_exists(conn, table, col):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == col for r in rows)


with app.app_context():
    conn = db.engine.raw_connection()
    cur = conn.cursor()

    # 1. Create holistic_line table if it doesn't exist yet.
    db.create_all()

    # 2. Skip entirely if already migrated (old columns already gone).
    if not col_exists(cur, 'holistic_exercise', 'melody_notes_json'):
        print("holistic_exercise already migrated — skipped.")
    else:
        exercises = cur.execute(
            "SELECT id, folder, melody_clef, melody_notes_json, harmony_chords_json, extra_lines_json "
            "FROM holistic_exercise"
        ).fetchall()

        for ex_id, folder, melody_clef, melody_notes_json, harmony_chords_json, extra_lines_json in exercises:
            order = 0

            # Primary melody line
            slug_mid = os.path.join('static', folder.rstrip('/'), os.path.basename(folder.rstrip('/')) + '.mid')
            midi_filename = ''
            if os.path.isfile(slug_mid):
                midi_filename = folder.rstrip('/') + '/' + os.path.basename(folder.rstrip('/')) + '.mid'
            cur.execute(
                "INSERT INTO holistic_line (holistic_exercise_id, line_type, name, \"order\", clef, midi_filename, content_json) "
                "VALUES (?, 'melody', 'Melody', ?, ?, ?, ?)",
                (ex_id, order, melody_clef or 'treble', midi_filename, melody_notes_json or '[]')
            )
            order += 1

            # Extra lines
            for line in json.loads(extra_lines_json or '[]'):
                cur.execute(
                    "INSERT INTO holistic_line (holistic_exercise_id, line_type, name, \"order\", clef, midi_filename, content_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (ex_id, line['type'], line.get('label', line['type'].capitalize()), order,
                     line.get('clef') if line['type'] == 'melody' else None,
                     line.get('file', ''), json.dumps(line.get('notes', [])))
                )
                order += 1

            # Harmony, if non-trivial
            harmony_chords = json.loads(harmony_chords_json or '[]')
            if harmony_chords:
                cur.execute(
                    "INSERT INTO holistic_line (holistic_exercise_id, line_type, name, \"order\", clef, midi_filename, content_json) "
                    "VALUES (?, 'harmonic', 'Harmony', ?, NULL, '', ?)",
                    (ex_id, order, harmony_chords_json)
                )
                order += 1

        print(f"Migrated {len(exercises)} holistic exercise(s) into holistic_line rows.")

        # 3. Drop old columns via table rebuild (SQLite has no DROP COLUMN before 3.35;
        #    rebuild is the portable approach and matches this repo's other migrations).
        cur.execute("""
            CREATE TABLE holistic_exercise_new (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           VARCHAR(100) NOT NULL,
                description    VARCHAR(300),
                folder         VARCHAR(200) NOT NULL,
                wav_filename   VARCHAR(100) NOT NULL DEFAULT 'audio.wav',
                source_key     VARCHAR(100),
                key_signature  VARCHAR(10) DEFAULT 'C',
                time_signature VARCHAR(10) DEFAULT '4/4',
                tempo          INTEGER DEFAULT 120,
                difficulty     INTEGER DEFAULT 1,
                visibility     VARCHAR(20) NOT NULL DEFAULT 'public',
                school_id      INTEGER,
                is_major       BOOLEAN DEFAULT 1,
                public_id      VARCHAR(12) UNIQUE
            )
        """)
        cur.execute("""
            INSERT INTO holistic_exercise_new
                (id, name, description, folder, wav_filename, source_key, key_signature,
                 time_signature, tempo, difficulty, visibility, school_id, is_major, public_id)
            SELECT id, name, description, folder, wav_filename, source_key, key_signature,
                   time_signature, tempo, difficulty, visibility, school_id, is_major, public_id
            FROM holistic_exercise
        """)
        cur.execute("DROP TABLE holistic_exercise")
        cur.execute("ALTER TABLE holistic_exercise_new RENAME TO holistic_exercise")
        print("Dropped melody_notes_json, harmony_chords_json, extra_lines_json, melody_clef from holistic_exercise.")

    conn.commit()
    conn.close()
    print("Migration complete.")
```

- [ ] **Step 2: Back up the dev database before running**

```bash
cp instance/musicianship.db "instance/musicianship.db.bak-holistic-migration-$(date +%Y%m%d%H%M%S)"
```

- [ ] **Step 3: Run the migration and verify**

```bash
.venv/bin/python migrate_holistic_lines.py
.venv/bin/python -c "
from app import app
from models import db, HolisticExercise, HolisticLine
with app.app_context():
    for ex in HolisticExercise.query.all():
        print(ex.id, ex.name, '->', [(l.line_type, l.name, l.order) for l in ex.lines])
"
```
Expected: each of the 4 seeded holistic exercises prints at least one `('melody', 'Melody', 0)` line, and any exercise that had `extra_lines_json`/non-trivial harmony shows those as additional lines with increasing `order`. No errors.

- [ ] **Step 4: Confirm the old columns are gone**

```bash
.venv/bin/python -c "
import sqlite3
con = sqlite3.connect('instance/musicianship.db')
cols = [r[1] for r in con.execute('PRAGMA table_info(holistic_exercise)')]
assert 'melody_notes_json' not in cols
assert 'harmony_chords_json' not in cols
assert 'extra_lines_json' not in cols
assert 'melody_clef' not in cols
print('old columns confirmed dropped:', cols)
"
```
Expected: prints the remaining column list with no errors from the `assert` statements.

- [ ] **Step 5: Commit**

```bash
git add migrate_holistic_lines.py
git commit -m "feat: add migration converting holistic exercises to HolisticLine rows"
```

---

### Task 3: Rewrite `grade_holistic_attempt` and attempt key convention

**Files:**
- Modify: `app.py:268-314` (`grade_holistic_attempt`)
- Modify: `models.py` (`HolisticAttempt` docstring comments only — no schema change)
- Test: `tests/test_holistic_grading.py`

**Interfaces:**
- Consumes: `HolisticLine.content`, `HolisticLine.line_type`, `HolisticLine.id` from Task 1.
- Produces: `grade_holistic_attempt(exercise, user_data)` returns `(scores: dict, overall: float)` where `scores` keys are `f'{line.id}_pitch'`/`f'{line.id}_duration'` (melody), `f'{line.id}_duration'` (rhythm), `f'{line.id}_letter'`/`f'{line.id}_quality'` (harmonic) — later tasks (student submit/results) rely on this exact key format.

- [ ] **Step 1: Write the failing test**

Create `tests/test_holistic_grading.py`:
```python
import pytest
from app import app
from models import db, HolisticExercise, HolisticLine

@pytest.fixture(autouse=True)
def ctx():
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def _make_exercise():
    ex = HolisticExercise(name='Test', folder='holistic/test/', wav_filename='audio.wav')
    db.session.add(ex)
    db.session.flush()
    mel = HolisticLine(
        holistic_exercise_id=ex.id, line_type='melody', name='Melody', order=0, clef='treble',
        midi_filename='', content_json='[{"key":"c/4","duration":"q"},{"key":"d/4","duration":"q"}]'
    )
    rhy = HolisticLine(
        holistic_exercise_id=ex.id, line_type='rhythm', name='Kick', order=1,
        midi_filename='', content_json='[{"duration":"q"},{"duration":"q"}]'
    )
    harm = HolisticLine(
        holistic_exercise_id=ex.id, line_type='harmonic', name='Harmony', order=2,
        midi_filename='', content_json='[{"root_pc":0,"quality":"major","duration":"w"}]'
    )
    db.session.add_all([mel, rhy, harm])
    db.session.commit()
    return ex, mel, rhy, harm


def test_grade_holistic_attempt_keys_by_line_id():
    from app import grade_holistic_attempt
    ex, mel, rhy, harm = _make_exercise()

    user_data = {
        str(mel.id): [{"key": "c/4", "duration": "q"}, {"key": "d/4", "duration": "q"}],  # perfect
        str(rhy.id): [{"duration": "q"}, {"duration": "q"}],  # perfect
        str(harm.id): [{"root_pc": 0, "quality": "major", "duration": "w"}],  # perfect
    }
    scores, overall = grade_holistic_attempt(ex, user_data)

    assert scores[f'{mel.id}_pitch'] == 100.0
    assert scores[f'{mel.id}_duration'] == 100.0
    assert scores[f'{rhy.id}_duration'] == 100.0
    assert scores[f'{harm.id}_letter'] == 100.0
    assert scores[f'{harm.id}_quality'] == 100.0
    assert overall == 100.0


def test_grade_holistic_attempt_missing_line_data_scores_zero():
    from app import grade_holistic_attempt
    ex, mel, rhy, harm = _make_exercise()

    scores, overall = grade_holistic_attempt(ex, {})

    assert scores[f'{mel.id}_pitch'] == 0.0
    assert scores[f'{rhy.id}_duration'] == 0.0
    assert overall < 50.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_holistic_grading.py -v`
Expected: FAIL — `grade_holistic_attempt` isn't importable this way yet, or its current implementation reads `exercise.melody_notes`/`exercise.harmony_chords`/`exercise.extra_lines`, none of which exist anymore after Task 1, so this errors with `AttributeError`.

- [ ] **Step 3: Rewrite `grade_holistic_attempt`**

In `app.py`, replace the entire function (currently lines 268-314):
```python
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
```

- [ ] **Step 4: Update `HolisticAttempt`'s docstring comments in `models.py`**

Replace:
```python
    # JSON dict: {"melody": [...notes...], "harmony": [...chords...],
    #             "melody_1": [...], "rhythm_1": [...], ...}
    user_data_json = db.Column(db.Text, nullable=False, default='{}')

    # JSON dict of individual scores: {"melody_pitch": 85.0, "melody_duration": 72.0,
    #   "harmony_letter": 90.0, "harmony_quality": 80.0,
    #   "melody_1_pitch": 60.0, "melody_1_duration": 50.0,
    #   "rhythm_1_duration": 70.0}
    scores_json    = db.Column(db.Text, nullable=False, default='{}')
```
with:
```python
    # JSON dict keyed by HolisticLine id (as string): {"3": [...notes...], "5": [...chords...], ...}
    user_data_json = db.Column(db.Text, nullable=False, default='{}')

    # JSON dict of individual scores, keyed by line id: {"3_pitch": 85.0, "3_duration": 72.0,
    #   "5_letter": 90.0, "5_quality": 80.0, "4_duration": 70.0}
    scores_json    = db.Column(db.Text, nullable=False, default='{}')
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_holistic_grading.py -v`
Expected: PASS (2/2)

- [ ] **Step 6: Commit**

```bash
git add app.py models.py tests/test_holistic_grading.py
git commit -m "feat: rewrite grade_holistic_attempt to iterate lines generically, keyed by line id"
```

---

### Task 4: Admin backend routes for line CRUD + strip MIDI-at-upload

**Files:**
- Modify: `app.py` (`admin_holistic_upload` at ~line 1951, `admin_edit_holistic` at ~line 1908)
- Create route: `admin_add_holistic_line`, `admin_reorder_holistic_lines`, `admin_delete_holistic_line`

**Interfaces:**
- Consumes: `HolisticLine` from Task 1.
- Produces: `POST /admin/holistic/<int:ex_id>/lines/add`, `POST /admin/holistic/<int:ex_id>/lines/reorder`, `POST /admin/holistic/lines/<int:line_id>/delete` — Task 5's templates submit to these route names via `url_for`.

- [ ] **Step 1: Strip MIDI-at-upload from `admin_holistic_upload`**

In `app.py`, the current route (~line 1951) validates and optionally parses a `midi_file` into `melody_notes_json`. Replace the whole function body from `if request.method == 'GET':` through the final `return redirect(...)` with:
```python
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
```
(This removes the `midi_file` handling and `melody_notes_json` entirely — lines are added afterward via the routes in Step 3.)

- [ ] **Step 2: Rewrite `admin_edit_holistic`**

Replace the current `admin_edit_holistic` function body's POST handling — remove the `for field in ('melody_notes_json', 'harmony_chords_json', 'extra_lines_json'): ...` loop and the `h.melody_clef = ...` line entirely (those fields no longer exist on the model). The route becomes:
```python
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
```

- [ ] **Step 3: Add the three line-management routes**

Immediately after `admin_edit_holistic` in `app.py`, add:
```python
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
```

- [ ] **Step 4: Add `HolisticLine` to the top-of-file model import**

In `app.py`, find the import line `from models import db, Melody, Tag, UserAttempt, Rhythm, RhythmAttempt, \` (and its continuation lines including `HolisticExercise, HolisticAttempt,`). Add `HolisticLine` to that continuation, e.g. change `HolisticExercise, HolisticAttempt,` to `HolisticExercise, HolisticAttempt, HolisticLine,`.

- [ ] **Step 5: Manually verify in the browser**

Start the dev server, log in as admin, navigate to `/admin/holistic/upload`, submit a WAV with a valid time signature and tempo — confirm it redirects to the edit page with a "Now add lines below" flash. On the edit page (once Task 5's template exists — if testing before Task 5, use `curl`/`test_client` directly against the new routes instead): POST to `/admin/holistic/<id>/lines/add` with a melody MIDI file, name "Melody", type "melody" — confirm a `HolisticLine` row is created with parsed `content_json`.

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: add holistic line CRUD routes, strip MIDI-at-upload from holistic exercise creation"
```

---

### Task 5: Admin templates — Lines UI with drag-reorder

**Files:**
- Modify: `templates/admin/holistic_upload.html`
- Modify: `templates/admin/holistic_edit.html`

**Interfaces:**
- Consumes: `admin_add_holistic_line`, `admin_reorder_holistic_lines`, `admin_delete_holistic_line` route names from Task 4; `lines` template variable (ordered list of `HolisticLine`) passed by `admin_edit_holistic`.

- [ ] **Step 1: Remove the MIDI file field from the upload template**

In `templates/admin/holistic_upload.html`, delete this block (lines are added afterward, not at upload time):
```html
      <div class="col-12"><label class="form-label fw-semibold">MIDI File <span class="text-muted small">(optional — parses melody notes)</span></label>
        <input type="file" name="midi_file" class="form-control" accept=".mid"></div>
```

- [ ] **Step 2: Rewrite `holistic_edit.html`'s JSON-textarea section into a Lines UI**

In `templates/admin/holistic_edit.html`, replace these three blocks:
```html
      <div class="col-12"><label class="form-label fw-semibold">Melody Notes JSON</label>
        <textarea name="melody_notes_json" class="form-control font-monospace small" rows="6">{{ h.melody_notes_json }}</textarea></div>
      <div class="col-12"><label class="form-label fw-semibold">Harmony Chords JSON</label>
        <textarea name="harmony_chords_json" class="form-control font-monospace small" rows="4">{{ h.harmony_chords_json }}</textarea></div>
      <div class="col-12"><label class="form-label fw-semibold">Extra Lines JSON</label>
        <textarea name="extra_lines_json" class="form-control font-monospace small" rows="4">{{ h.extra_lines_json }}</textarea></div>
```
with:
```html
      <div class="col-12">
        <label class="form-label fw-semibold">Lines</label>
        {% if lines|length > 8 %}
        <div class="alert alert-warning small py-2">This exercise has {{ lines|length }} lines — many lines may be hard to read for students. Consider trimming.</div>
        {% endif %}
        <ul id="lines-list" class="list-group mb-3">
          {% for line in lines %}
          <li class="list-group-item d-flex justify-content-between align-items-center" data-line-id="{{ line.id }}" style="cursor:grab">
            <span>
              <i class="bi bi-grip-vertical text-muted me-2"></i>
              <strong>{{ line.name }}</strong>
              <span class="badge {{ {'melody': 'bg-primary', 'rhythm': 'bg-warning text-dark', 'harmonic': 'bg-success'}.get(line.line_type, 'bg-secondary') }} ms-2">{{ line.line_type }}</span>
              {% if line.clef %}<span class="text-muted small ms-1">({{ line.clef }})</span>{% endif %}
            </span>
            <form method="post" action="{{ url_for('admin_delete_holistic_line', line_id=line.id) }}"
                  onsubmit="return confirm('Remove this line?')">
              <button class="btn btn-sm btn-outline-danger">Remove</button>
            </form>
          </li>
          {% else %}
          <li class="list-group-item text-muted">No lines yet — add one below.</li>
          {% endfor %}
        </ul>
        <form method="post" action="{{ url_for('admin_add_holistic_line', ex_id=h.id) }}"
              enctype="multipart/form-data" class="p-3 border rounded bg-light">
          <div class="row g-2 align-items-end">
            <div class="col-md-3">
              <label class="form-label small fw-semibold">Name</label>
              <input name="name" class="form-control form-control-sm" required>
            </div>
            <div class="col-md-3">
              <label class="form-label small fw-semibold">Type</label>
              <select name="line_type" class="form-select form-select-sm" id="new-line-type" required>
                <option value="melody">Melodic</option>
                <option value="rhythm">Rhythmic</option>
                <option value="harmonic">Harmonic</option>
              </select>
            </div>
            <div class="col-md-2" id="new-line-clef-wrap">
              <label class="form-label small fw-semibold">Clef</label>
              <select name="clef" class="form-select form-select-sm">
                <option value="treble">Treble</option>
                <option value="bass">Bass</option>
                <option value="alto">Alto</option>
                <option value="tenor">Tenor</option>
              </select>
            </div>
            <div class="col-md-3">
              <label class="form-label small fw-semibold">MIDI File</label>
              <input type="file" name="midi_file" accept=".mid" class="form-control form-control-sm" required>
            </div>
            <div class="col-md-1">
              <button type="submit" class="btn btn-sm btn-primary w-100">Add</button>
            </div>
          </div>
        </form>
      </div>
```

- [ ] **Step 3: Add SortableJS and the reorder script**

At the bottom of `templates/admin/holistic_edit.html`, before the closing `{% endblock %}` of the file (after the existing `</form>` and `</div>` that close the page), add:
```html
<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js"></script>
<script>
  const linesList = document.getElementById('lines-list');
  if (linesList) {
    new Sortable(linesList, {
      animation: 150,
      onEnd: function () {
        const lineIds = [...linesList.querySelectorAll('[data-line-id]')].map(el => parseInt(el.dataset.lineId));
        fetch('{{ url_for("admin_reorder_holistic_lines", ex_id=h.id) }}', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ line_ids: lineIds }),
        });
      },
    });
  }
  const typeSelect = document.getElementById('new-line-type');
  const clefWrap = document.getElementById('new-line-clef-wrap');
  function toggleClefField() {
    clefWrap.style.display = typeSelect.value === 'melody' ? '' : 'none';
  }
  typeSelect.addEventListener('change', toggleClefField);
  toggleClefField();
</script>
```

- [ ] **Step 4: Manually verify in the browser**

Navigate to `/admin/holistic/<id>/edit` for an exercise with 0 lines (fresh from Task 4's upload flow). Add a melody line (name "Soprano", type Melodic, clef Treble, valid MIDI) — confirm it appears in the list. Add a rhythm line and a harmonic line. Drag to reorder — reload the page and confirm the new order persisted (check via `HolisticLine.query.filter_by(holistic_exercise_id=...).order_by(HolisticLine.order).all()` in a Python shell, or visually in the list order after reload).

- [ ] **Step 5: Commit**

```bash
git add templates/admin/holistic_upload.html templates/admin/holistic_edit.html
git commit -m "feat: admin Lines UI with SortableJS drag-reorder for holistic exercises"
```

---

### Task 6: Student route + template — generic line loop

**Files:**
- Modify: `app.py` (`holistic_exercise` route, ~line 872)
- Modify: `templates/holistic_exercise.html`

**Interfaces:**
- Produces: `lines_display` template variable — a list of dicts `{'id': int, 'key': str(line.id), 'type': str, 'label': str, 'clef': str|None}` in `order` order, that Task 7's JS reads via the `EXTRA_LINES`-equivalent JS constant.

- [ ] **Step 1: Rewrite the `holistic_exercise` route**

Replace:
```python
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
```
with:
```python
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
```

- [ ] **Step 2: Rewrite the template's staff sections**

In `templates/holistic_exercise.html`, delete the "Staff visibility toggles" melody-specific checkbox (lines 84-88: the `toggle-melody` block with hardcoded `data-line-key="melody"`), the "Primary melody stave" block (lines 112-144), the `{% for line in extra_lines_display %}` loop (lines 147-179), and the entire "Harmony row" block (lines 181-230). Replace all four with two loops driven by `lines_display`:

```html
    <div class="staff-toggle-row">
      {% for line in lines_display %}
        <div class="form-check form-check-inline">
          <input class="form-check-input staff-visibility-check" type="checkbox"
                 id="toggle-{{ line.key }}" data-line-key="{{ line.key }}" checked>
          <label class="form-check-label" for="toggle-{{ line.key }}">{{ line.label }}</label>
        </div>
      {% endfor %}
    </div>
```
(replaces the old staff-toggle-row content, keeping the surrounding card wrapper from lines 76-83/101-103 as-is).

For the "Transcribe" card body (replacing lines 112-230), for each line render either a stave-editor block (melody/rhythm) or a harmony chord-block widget (harmonic):
```html
    {% for line in lines_display %}
    <div id="staff-section-{{ line.key }}" class="mb-4">
      {% if line.type in ('melody', 'rhythm') %}
      <div class="d-flex align-items-center mb-1 gap-2">
        <span class="staff-label fw-semibold">{{ line.label }}</span>
        <div class="d-flex flex-wrap gap-1 align-items-center" data-line-key="{{ line.key }}">
          <button class="btn btn-outline-primary btn-sm holistic-dur-btn" data-dur="16">16th</button>
          <button class="btn btn-outline-primary btn-sm holistic-dur-btn" data-dur="8">8th</button>
          <button class="btn btn-outline-primary btn-sm holistic-dur-btn active" data-dur="q">Qtr</button>
          <button class="btn btn-outline-primary btn-sm holistic-dur-btn" data-dur="h">Half</button>
          <button class="btn btn-outline-primary btn-sm holistic-dur-btn" data-dur="w">Whole</button>
          <button class="btn btn-outline-secondary btn-sm holistic-dot-btn ms-1">• Dot</button>
          <button class="btn btn-outline-secondary btn-sm holistic-rest-btn ms-1">Rest</button>
          <button class="btn btn-outline-warning btn-sm holistic-undo-btn ms-2">
            <i class="bi bi-backspace"></i> Undo
          </button>
          <button class="btn btn-outline-danger btn-sm holistic-clear-btn">
            <i class="bi bi-trash"></i> Clear
          </button>
          <div class="holistic-sel-controls d-flex flex-wrap gap-1 align-items-center ms-2" style="display:none">
            <span class="small fw-semibold">Selected:</span>
            <button class="btn btn-outline-secondary btn-sm holistic-sel-sharp">&#9839;</button>
            <button class="btn btn-outline-secondary btn-sm holistic-sel-flat">&#9837;</button>
            <button class="btn btn-outline-secondary btn-sm holistic-sel-natural">&#9838;</button>
            <button class="btn btn-outline-secondary btn-sm holistic-sel-deselect">&#10005;</button>
          </div>
        </div>
      </div>
      <div id="{{ line.key }}-container"
           class="notation-area border rounded"
           data-stave-line-key="{{ line.key }}"
           data-clef="{{ line.clef }}"></div>
      {% else %}
      <hr class="my-3">
      <div class="d-flex align-items-center mb-2 gap-2">
        <span class="staff-label fw-semibold">{{ line.label }}</span>
        <span class="fw-semibold small me-1">Notation:</span>
        <button class="btn btn-outline-secondary btn-sm holistic-notation-btn active" data-mode="roman" data-harm-line="{{ line.key }}">Roman</button>
        <button class="btn btn-outline-secondary btn-sm holistic-notation-btn" data-mode="nashville" data-harm-line="{{ line.key }}">Nashville</button>
        <button class="btn btn-outline-secondary btn-sm holistic-notation-btn" data-mode="lead" data-harm-line="{{ line.key }}">Lead Sheet</button>
      </div>
      <div class="d-flex flex-wrap gap-1 align-items-center mb-2">
        <span class="small text-muted me-1">Duration:</span>
        <button class="btn btn-outline-secondary btn-sm holistic-harm-dur-btn" data-dur="w" data-harm-line="{{ line.key }}">Whole</button>
        <button class="btn btn-outline-secondary btn-sm holistic-harm-dur-btn active" data-dur="h" data-harm-line="{{ line.key }}">Half</button>
        <button class="btn btn-outline-secondary btn-sm holistic-harm-dur-btn" data-dur="q" data-harm-line="{{ line.key }}">Qtr</button>
        <button class="btn btn-outline-secondary btn-sm holistic-harm-dur-btn" data-dur="8" data-harm-line="{{ line.key }}">8th</button>
      </div>
      <div class="mb-2">
        <span class="small text-muted d-block mb-1">Diatonic Chords — click to add:</span>
        <div id="holistic-diatonic-palette-{{ line.key }}" class="d-flex flex-wrap gap-2"></div>
      </div>
      <div id="holistic-modifier-panel-{{ line.key }}" class="mb-2">
        <p class="text-muted small mb-0">Select a chord block below to modify it.</p>
      </div>
      <div class="mb-1">
        <span class="small text-muted d-block mb-1">Your {{ line.label }} Answer:</span>
        <div id="holistic-harmony-area-{{ line.key }}"
             class="d-flex flex-wrap gap-2 min-height-72 align-items-center p-2 bg-light rounded border border-dashed"
             style="min-height:72px; border-style:dashed !important;"></div>
      </div>
      <div class="d-flex gap-2 mt-2">
        <button class="btn btn-outline-warning btn-sm btn-harm-undo" data-harm-line="{{ line.key }}">
          <i class="bi bi-backspace me-1"></i>Undo Last
        </button>
        <button class="btn btn-outline-danger btn-sm btn-harm-clear" data-harm-line="{{ line.key }}">
          <i class="bi bi-trash me-1"></i>Clear All
        </button>
      </div>
      {% endif %}
    </div>
    {% endfor %}
```

- [ ] **Step 3: Update the script-block JS constants**

In `templates/holistic_exercise.html`'s `{% block scripts %}`, replace:
```html
  const MELODY_CLEF       = "{{ exercise.melody_clef }}";
  const EXTRA_LINES       = {{ extra_lines_display | tojson }};
```
with:
```html
  const LINES_DISPLAY     = {{ lines_display | tojson }};
```
(`MELODY_CLEF` and `EXTRA_LINES` are no longer used anywhere after Task 7 rewrites `holistic.js` to consume `LINES_DISPLAY` instead — this step and Task 7 must land together, see Task 7 Step 1.)

- [ ] **Step 4: Commit**

```bash
git add app.py templates/holistic_exercise.html
git commit -m "feat: generic per-line rendering in holistic_exercise route and template"
```
(This intentionally leaves `holistic.js` still referencing the now-removed `MELODY_CLEF`/`EXTRA_LINES` and the old fixed harmony DOM ids — Task 7 fixes that in the same working tree before any manual verification is meaningful. Do not attempt to manually verify this task's rendering in isolation; verify at the end of Task 7.)

---

### Task 7: `holistic.js` — consume `LINES_DISPLAY`, genericize the harmony subsystem for N lines

**Files:**
- Modify: `static/js/holistic.js`

**Interfaces:**
- Consumes: `LINES_DISPLAY` (from Task 6) — array of `{id, key, type, label, clef}` in display order.
- Produces: harmony state and DOM queries keyed per `harmLineKey`, so Task 8's submit function can collect N independent harmony answers.

This is the largest single change in the plan: the melody/rhythm stave-editing code (`renderStaveForLine`, `bindStaveControls`, the init loop, etc.) already keys everything off a generic `lineKey` parameter and `data-line-key`/`data-stave-line-key` DOM attributes — that part needs no change beyond removing the now-dead `EXTRA_LINES` reference. The harmony subsystem (`initHarmonyPanel` and everything it calls, currently lines 822-1155) is the opposite: every piece of state and every DOM query is a single global instance. This step converts it to be keyed by harmony line, the same way the stave code is keyed by `lineKey`.

- [ ] **Step 1: Remove the dead `EXTRA_LINES`/`MELODY_CLEF` references**

`static/js/holistic.js` doesn't currently reference `EXTRA_LINES` or `MELODY_CLEF` directly (the init loop at the bottom of the file already iterates `document.querySelectorAll('[data-stave-line-key]')` generically, driven by the DOM, not by those JS constants) — confirm this with:
```bash
grep -n "EXTRA_LINES\|MELODY_CLEF" static/js/holistic.js
```
Expected: no matches. If there are matches, remove them (they'd be stray references to constants Task 6 deleted).

- [ ] **Step 2: Replace global harmony state with a per-line map**

Replace:
```javascript
let harmonyBlocks  = [];
let harmSelectedIdx = null;
let harmNotationMode = 'roman';
let harmSelectedDur  = 'h';   // default: half-note chord blocks
```
with:
```javascript
const harmonyState = {};  // harmLineKey -> { blocks: [], selectedIdx: null, notationMode: 'roman', selectedDur: 'h' }

function getHarmonyState(harmLineKey) {
  if (!harmonyState[harmLineKey]) {
    harmonyState[harmLineKey] = { blocks: [], selectedIdx: null, notationMode: 'roman', selectedDur: 'h' };
  }
  return harmonyState[harmLineKey];
}
```

- [ ] **Step 3: Rewrite `initHarmonyPanel` to set up one instance per harmonic line**

Replace the whole function:
```javascript
function initHarmonyPanel() {
  buildHarmonyPalette();
  renderHarmonyArea();
  renderHarmonyModifier();

  // Notation toggles
  document.querySelectorAll('.holistic-notation-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      harmNotationMode = btn.dataset.mode;
      document.querySelectorAll('.holistic-notation-btn').forEach(b =>
        b.classList.toggle('active', b === btn));
      buildHarmonyPalette();
      renderHarmonyArea();
    });
  });

  // Duration selector for harmony blocks
  document.querySelectorAll('.holistic-harm-dur-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      harmSelectedDur = btn.dataset.dur;
      document.querySelectorAll('.holistic-harm-dur-btn').forEach(b =>
        b.classList.toggle('active', b === btn));
    });
  });

  // Undo / Clear
  document.getElementById('btn-harm-undo')?.addEventListener('click', () => {
    if (harmonyBlocks.length) {
      harmonyBlocks.pop();
      if (harmSelectedIdx !== null && harmSelectedIdx >= harmonyBlocks.length) {
        harmSelectedIdx = harmonyBlocks.length > 0 ? harmonyBlocks.length - 1 : null;
      }
      renderHarmonyArea();
      renderHarmonyModifier();
    }
  });
  document.getElementById('btn-harm-clear')?.addEventListener('click', () => {
    harmonyBlocks = [];
    harmSelectedIdx = null;
    renderHarmonyArea();
    renderHarmonyModifier();
  });
}
```
with:
```javascript
function initHarmonyPanel() {
  const harmLineKeys = LINES_DISPLAY.filter(l => l.type === 'harmonic').map(l => l.key);

  harmLineKeys.forEach(harmLineKey => {
    getHarmonyState(harmLineKey);
    buildHarmonyPalette(harmLineKey);
    renderHarmonyArea(harmLineKey);
    renderHarmonyModifier(harmLineKey);

    document.querySelectorAll(`.holistic-notation-btn[data-harm-line="${harmLineKey}"]`).forEach(btn => {
      btn.addEventListener('click', () => {
        const st = getHarmonyState(harmLineKey);
        st.notationMode = btn.dataset.mode;
        document.querySelectorAll(`.holistic-notation-btn[data-harm-line="${harmLineKey}"]`).forEach(b =>
          b.classList.toggle('active', b === btn));
        buildHarmonyPalette(harmLineKey);
        renderHarmonyArea(harmLineKey);
      });
    });

    document.querySelectorAll(`.holistic-harm-dur-btn[data-harm-line="${harmLineKey}"]`).forEach(btn => {
      btn.addEventListener('click', () => {
        const st = getHarmonyState(harmLineKey);
        st.selectedDur = btn.dataset.dur;
        document.querySelectorAll(`.holistic-harm-dur-btn[data-harm-line="${harmLineKey}"]`).forEach(b =>
          b.classList.toggle('active', b === btn));
      });
    });

    document.querySelector(`.btn-harm-undo[data-harm-line="${harmLineKey}"]`)?.addEventListener('click', () => {
      const st = getHarmonyState(harmLineKey);
      if (st.blocks.length) {
        st.blocks.pop();
        if (st.selectedIdx !== null && st.selectedIdx >= st.blocks.length) {
          st.selectedIdx = st.blocks.length > 0 ? st.blocks.length - 1 : null;
        }
        renderHarmonyArea(harmLineKey);
        renderHarmonyModifier(harmLineKey);
      }
    });
    document.querySelector(`.btn-harm-clear[data-harm-line="${harmLineKey}"]`)?.addEventListener('click', () => {
      const st = getHarmonyState(harmLineKey);
      st.blocks = [];
      st.selectedIdx = null;
      renderHarmonyArea(harmLineKey);
      renderHarmonyModifier(harmLineKey);
    });
  });
}
```

- [ ] **Step 4: Genericize `buildHarmonyPalette`, `makeHarmChord`, `addHarmBlock`, `renderHarmonyArea`**

Replace:
```javascript
function buildHarmonyPalette() {
  const container = document.getElementById('holistic-diatonic-palette');
  if (!container) return;
  container.innerHTML = '';

  const scale = DIATONIC_SCALES[KEY_SIGNATURE] || DIATONIC_SCALES['C'];
  const isMinor = KEY_SIGNATURE.endsWith('m');
  const qualities = isMinor ? DIATONIC_QUALITIES_MINOR : DIATONIC_QUALITIES_MAJOR;

  scale.forEach((pc, idx) => {
    const quality = qualities[idx];
    const chord = makeHarmChord(pc, quality);
    const label = formatChordName(chord, harmNotationMode, KEY_SIGNATURE);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-outline-secondary palette-btn btn-sm';
    btn.textContent = label;
    btn.addEventListener('click', () => addHarmBlock(makeHarmChord(pc, quality)));
    container.appendChild(btn);
  });
}

function makeHarmChord(rootPc, quality) {
  return {
    root_pc:     rootPc,
    root_name:   noteNameForPc(rootPc, KEY_SIGNATURE),
    quality:     quality,
    bass_pc:     rootPc,
    bass_name:   noteNameForPc(rootPc, KEY_SIGNATURE),
    seventh:     null,
    extensions:  [],
    sus:         null,
    prefer_sharp: null,
    duration:    harmSelectedDur,
  };
}

function addHarmBlock(chord) {
  chord.duration = harmSelectedDur;
  harmonyBlocks.push(chord);
  harmSelectedIdx = harmonyBlocks.length - 1;
  renderHarmonyArea();
  renderHarmonyModifier();
}

function renderHarmonyArea() {
  const area = document.getElementById('holistic-harmony-area');
  if (!area) return;
  area.innerHTML = '';

  if (harmonyBlocks.length === 0) {
    const msg = document.createElement('span');
    msg.className = 'placeholder-text text-muted small';
    msg.textContent = 'Click a chord above to add it here…';
    area.appendChild(msg);
    return;
  }

  harmonyBlocks.forEach((b, i) => {
    const el = document.createElement('div');
    el.className = 'chord-block' + (i === harmSelectedIdx ? ' selected' : '');
    const durLabel = {w:'whole',h:'half',q:'qtr','8':'8th','16':'16th'}[b.duration] || b.duration;
    el.textContent = formatChordName(b, harmNotationMode, KEY_SIGNATURE);
    el.title = durLabel;
    el.addEventListener('click', () => {
      harmSelectedIdx = (harmSelectedIdx === i) ? null : i;
      renderHarmonyArea();
      renderHarmonyModifier();
    });
    area.appendChild(el);
  });
}
```
with:
```javascript
function buildHarmonyPalette(harmLineKey) {
  const container = document.getElementById('holistic-diatonic-palette-' + harmLineKey);
  if (!container) return;
  container.innerHTML = '';

  const st = getHarmonyState(harmLineKey);
  const scale = DIATONIC_SCALES[KEY_SIGNATURE] || DIATONIC_SCALES['C'];
  const isMinor = KEY_SIGNATURE.endsWith('m');
  const qualities = isMinor ? DIATONIC_QUALITIES_MINOR : DIATONIC_QUALITIES_MAJOR;

  scale.forEach((pc, idx) => {
    const quality = qualities[idx];
    const chord = makeHarmChord(harmLineKey, pc, quality);
    const label = formatChordName(chord, st.notationMode, KEY_SIGNATURE);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-outline-secondary palette-btn btn-sm';
    btn.textContent = label;
    btn.addEventListener('click', () => addHarmBlock(harmLineKey, makeHarmChord(harmLineKey, pc, quality)));
    container.appendChild(btn);
  });
}

function makeHarmChord(harmLineKey, rootPc, quality) {
  const st = getHarmonyState(harmLineKey);
  return {
    root_pc:     rootPc,
    root_name:   noteNameForPc(rootPc, KEY_SIGNATURE),
    quality:     quality,
    bass_pc:     rootPc,
    bass_name:   noteNameForPc(rootPc, KEY_SIGNATURE),
    seventh:     null,
    extensions:  [],
    sus:         null,
    prefer_sharp: null,
    duration:    st.selectedDur,
  };
}

function addHarmBlock(harmLineKey, chord) {
  const st = getHarmonyState(harmLineKey);
  chord.duration = st.selectedDur;
  st.blocks.push(chord);
  st.selectedIdx = st.blocks.length - 1;
  renderHarmonyArea(harmLineKey);
  renderHarmonyModifier(harmLineKey);
}

function renderHarmonyArea(harmLineKey) {
  const area = document.getElementById('holistic-harmony-area-' + harmLineKey);
  if (!area) return;
  area.innerHTML = '';
  const st = getHarmonyState(harmLineKey);

  if (st.blocks.length === 0) {
    const msg = document.createElement('span');
    msg.className = 'placeholder-text text-muted small';
    msg.textContent = 'Click a chord above to add it here…';
    area.appendChild(msg);
    return;
  }

  st.blocks.forEach((b, i) => {
    const el = document.createElement('div');
    el.className = 'chord-block' + (i === st.selectedIdx ? ' selected' : '');
    const durLabel = {w:'whole',h:'half',q:'qtr','8':'8th','16':'16th'}[b.duration] || b.duration;
    el.textContent = formatChordName(b, st.notationMode, KEY_SIGNATURE);
    el.title = durLabel;
    el.addEventListener('click', () => {
      st.selectedIdx = (st.selectedIdx === i) ? null : i;
      renderHarmonyArea(harmLineKey);
      renderHarmonyModifier(harmLineKey);
    });
    area.appendChild(el);
  });
}
```

- [ ] **Step 5: Genericize `renderHarmonyModifier` and its inline chord-modifier click handlers**

`renderHarmonyModifier` (currently lines 944 onward, ~150 lines including the modifier-panel HTML generation and the click handlers for chromatic/quality/sus/seventh/extensions/bass-note/duration/delete that follow it) currently reads and writes the global `harmonyBlocks`/`harmSelectedIdx`. Apply the exact same transformation pattern used in Steps 3-4: add a `harmLineKey` parameter to `renderHarmonyModifier` and every function it calls or that calls it; replace every bare `harmonyBlocks`/`harmSelectedIdx` reference with `getHarmonyState(harmLineKey).blocks`/`getHarmonyState(harmLineKey).selectedIdx`; replace `document.getElementById('holistic-modifier-panel')` with `document.getElementById('holistic-modifier-panel-' + harmLineKey)`; every inline `onclick`/`addEventListener` handler generated inside `renderHarmonyModifier`'s HTML string must close over `harmLineKey` (they already close over the surrounding function scope, so adding the parameter to the function signature is sufficient — no other change needed for closures). Read the current `renderHarmonyModifier` function body with `sed -n '944,1155p' static/js/holistic.js` before editing to see the exact current code, since it wasn't reproduced here in full.

- [ ] **Step 6: Update the two callers of `renderHarmonyModifier`/`renderHarmonyArea` outside the harmony subsystem itself**

Search for any remaining bare (no-argument) calls:
```bash
grep -n "renderHarmonyArea()\|renderHarmonyModifier()\|buildHarmonyPalette()" static/js/holistic.js
```
Every match must gain the relevant `harmLineKey` argument from its enclosing scope (all call sites are inside functions from Steps 3-5 that now receive `harmLineKey` as a parameter).

- [ ] **Step 7: Verify no global harmony state remains**

```bash
grep -n "^let harmonyBlocks\|^let harmSelectedIdx\|^let harmNotationMode\|^let harmSelectedDur" static/js/holistic.js
```
Expected: no matches (Step 2 replaced all four with `harmonyState`/`getHarmonyState`).

- [ ] **Step 8: Commit**

```bash
git add static/js/holistic.js
git commit -m "feat: genericize holistic.js harmony subsystem to support any number of harmonic lines"
```

---

### Task 8: Submit/results — collect N lines by id, update `holistic_results.html`

**Files:**
- Modify: `static/js/holistic.js` (`submitHolisticAttempt`, init loop)
- Modify: `templates/holistic_results.html`

**Interfaces:**
- Consumes: `harmonyState`, `getHarmonyState` from Task 7; `grade_holistic_attempt`'s `f'{line_id}_pitch'`/etc. key format from Task 3.

- [ ] **Step 1: Rewrite `submitHolisticAttempt`**

Replace:
```javascript
async function submitHolisticAttempt() {
  const btn = document.getElementById('btn-holistic-submit');
  if (btn) { btn.disabled = true; btn.textContent = 'Submitting…'; }

  const lines = {};

  // Collect melody line notes
  document.querySelectorAll('[data-stave-line-key]').forEach(el => {
    const lk = el.dataset.staveLineKey;
    lines[lk] = lineNotes[lk] || [];
  });

  // Harmony
  lines['harmony'] = harmonyBlocks;
```
with:
```javascript
async function submitHolisticAttempt() {
  const btn = document.getElementById('btn-holistic-submit');
  if (btn) { btn.disabled = true; btn.textContent = 'Submitting…'; }

  const lines = {};

  // Collect melody/rhythm line notes
  document.querySelectorAll('[data-stave-line-key]').forEach(el => {
    const lk = el.dataset.staveLineKey;
    lines[lk] = lineNotes[lk] || [];
  });

  // Collect each harmonic line's blocks
  LINES_DISPLAY.filter(l => l.type === 'harmonic').forEach(l => {
    lines[l.key] = getHarmonyState(l.key).blocks;
  });
```
(the rest of the function — the `fetch('/holistic/submit/' + EXERCISE_ID, ...)` call onward — is unchanged).

- [ ] **Step 2: Update the init block**

Replace:
```javascript
document.addEventListener('DOMContentLoaded', () => {
  initWavPlayback();
  initKeyReference();
  initVisibilityToggles();
  initHarmonyPanel();

  // Render all melody stave containers
  document.querySelectorAll('[data-stave-line-key]').forEach(containerEl => {
```
with (only the comment changes, to reflect that this loop now covers every melody/rhythm line, not just "melody"):
```javascript
document.addEventListener('DOMContentLoaded', () => {
  initWavPlayback();
  initKeyReference();
  initVisibilityToggles();
  initHarmonyPanel();

  // Render every melody/rhythm stave container (harmonic lines have no stave — handled by initHarmonyPanel)
  document.querySelectorAll('[data-stave-line-key]').forEach(containerEl => {
```

- [ ] **Step 3: Rewrite `holistic_results.html`'s score display and JS constants**

Replace the fixed score tiles:
```html
        <div class="fs-4 fw-bold text-primary">{{ scores.get('melody_pitch', 0) | int }}%</div>
```
```html
        <div class="fs-4 fw-bold text-info">{{ scores.get('melody_duration', 0) | int }}%</div>
```
```html
        <div class="fs-4 fw-bold text-success">{{ scores.get('harmony_letter', 0) | int }}%</div>
```
```html
        <div class="fs-4 fw-bold text-warning">{{ scores.get('harmony_quality', 0) | int }}%</div>
```
and the `{% for line in exercise.extra_lines %}` loops (there are three — at the score-tiles section and two further down in the page, likely for playback/comparison rendering) with a single `{% for line in exercise.lines %}` loop per section, using `scores.get(line.id|string + '_pitch', 0)` (Jinja string concatenation: `scores.get(line.id ~ '_pitch', 0)`) style lookups instead of the old fixed/`lkey`-based ones. Since the exact surrounding HTML for the two lower loops (lines ~125, ~153) wasn't captured in this plan's research, read them with `sed -n '1,200p' templates/holistic_results.html` before editing, and apply the same `line.id ~ '_pitch'`/`line.id ~ '_duration'`/`line.id ~ '_letter'`/`line.id ~ '_quality'` key-lookup pattern (matching Task 3's `grade_holistic_attempt` output keys) to whatever each loop currently does per-line.

Replace the JS constants:
```html
const CORRECT_MELODY  = {{ exercise.melody_notes_json | tojson }};
const CORRECT_HARMONY = {{ exercise.harmony_chords_json | tojson }};
const CORRECT_EXTRA   = {{ exercise.extra_lines_json | tojson }};  // [{type,file,label,clef,notes}]
```
with:
```html
const CORRECT_LINES = {{ exercise.lines | map(attribute='content') | list | tojson }};
const LINES_META     = [{% for line in exercise.lines %}{id: {{ line.id }}, type: "{{ line.line_type }}", label: {{ line.name | tojson }}, clef: {{ (line.clef or 'treble') | tojson }}}{{ ", " if not loop.last }}{% endfor %}];
```
Any JS below this block that referenced `CORRECT_MELODY`/`CORRECT_HARMONY`/`CORRECT_EXTRA` by name must be updated to look up the matching entry from `CORRECT_LINES`/`LINES_META` by index or by `id` instead — read the rest of `templates/holistic_results.html`'s script block to find every such reference (`grep -n "CORRECT_MELODY\|CORRECT_HARMONY\|CORRECT_EXTRA" templates/holistic_results.html`) and update each one, using the same "look up by matching `LINES_META[i].id`" pattern consistently.

- [ ] **Step 4: Manually verify end-to-end in the browser**

As admin, create a holistic exercise (Task 4/5's flow) with one melody line, one rhythm line, and one harmonic line. As a student (or admin, since admin bypasses membership checks), open the exercise, enter some notes on the melody/rhythm staves and some chords on the harmonic line, submit, and confirm the results page shows non-error scores for all three lines with correct labels.

- [ ] **Step 5: Commit**

```bash
git add static/js/holistic.js templates/holistic_results.html
git commit -m "feat: collect and display per-line-id scores for any number of holistic lines"
```

---

### Task 9: Regression pass

**Files:** none (verification only)

- [ ] **Step 1: Run the full automated test suite**

```bash
.venv/bin/python -m pytest -q
```
Expected: all tests pass, including the two new `tests/test_holistic_grading.py` tests from Task 3.

- [ ] **Step 2: End-to-end manual walkthrough**

Repeat Task 8 Step 4's walkthrough once more from a clean exercise, this time also verifying: the admin edit page's line-count warning banner appears once you add a 9th line; deleting a line via the Remove button actually removes it from the list and the student page; the WAV playback and key-reference controls (unrelated to lines, should be untouched) still work on the student exercise page.

- [ ] **Step 3: Commit (only if Step 1 or 2 surfaced a fix)**

```bash
git add -A
git commit -m "fix: regression from holistic line data model change"
```
