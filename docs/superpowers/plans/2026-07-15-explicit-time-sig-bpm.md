# Explicit Time Signature & BPM on Admin Forms Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every admin form that creates or edits an exercise with a `time_signature` and/or `tempo` field collects that value explicitly from the admin, with no client- or server-side default — the request is rejected if the field is missing.

**Architecture:** Pure form + route changes, no new files, no database migration (every column already exists). Each task touches one template + its one Flask route in `app.py`.

**Tech Stack:** Flask, Jinja2, vanilla HTML forms (Bootstrap 5 classes already in use).

## Global Constraints

- Standardized time-signature dropdown options (every form that has this field uses this exact list, in this order): `4/4, 3/4, 2/4, 6/8, 9/8, 12/8, 5/4, 7/8`
- Time-signature `<select>` starts on a disabled, unselected placeholder: `<option value="" disabled selected>Choose…</option>`
- BPM is `<input type="number" name="tempo" required min="20" max="400" placeholder="e.g. 120">` with no `value` attribute
- Server-side validation is required on every affected route in addition to HTML5 `required` — reject with `flash(..., 'danger')` + redirect back to the same form if the field is blank, never fall back to a default or to the previous value
- Harmonic (`ChordProgression`) gets BPM only — it has no `time_signature` column and none is being added
- No automated test coverage is being added (per approved spec — existing suite covers role guards/school schema, not these routes); every task ends with a manual browser verification step instead

---

### Task 1: Rhythm upload form — remove silent tempo default, standardize time-signature list

**Files:**
- Modify: `templates/admin/rhythm_upload.html`
- Modify: `app.py` (`admin_rhythm_upload`, currently at line 1817)

**Interfaces:**
- Produces: the canonical time-signature option list (`4/4, 3/4, 2/4, 6/8, 9/8, 12/8, 5/4, 7/8`) that Tasks 2 and 5 must reuse verbatim.

- [ ] **Step 1: Update the template**

In `templates/admin/rhythm_upload.html`, replace the Time Signature and Tempo blocks:

```html
      <div class="col-md-4"><label class="form-label fw-semibold">Time Signature</label>
        <select name="time_signature" class="form-select">
          {% for ts in ['4/4','3/4','2/4','6/8','5/4','7/8'] %}<option>{{ ts }}</option>{% endfor %}
        </select></div>
```
becomes:
```html
      <div class="col-md-4"><label class="form-label fw-semibold">Time Signature</label>
        <select name="time_signature" class="form-select" required>
          <option value="" disabled selected>Choose…</option>
          {% for ts in ['4/4','3/4','2/4','6/8','9/8','12/8','5/4','7/8'] %}<option>{{ ts }}</option>{% endfor %}
        </select></div>
```

and:
```html
    <div class="mb-3"><label class="form-label fw-semibold">Tempo</label>
      <input name="tempo" type="number" class="form-control" value="100" style="max-width:120px"></div>
```
becomes:
```html
    <div class="mb-3"><label class="form-label fw-semibold">Tempo (BPM)</label>
      <input name="tempo" type="number" class="form-control" required min="20" max="400" placeholder="e.g. 100" style="max-width:120px"></div>
```

- [ ] **Step 2: Add server-side validation to the route**

In `app.py`, inside `admin_rhythm_upload` (around line 1817), immediately after the existing MIDI-file check:
```python
    f = request.files.get('midi_file')
    if not f or not f.filename or not f.filename.endswith('.mid'):
        flash('Please upload a .mid file.', 'danger')
        return redirect(url_for('admin_rhythm_upload'))
```
add:
```python
    time_sig = request.form.get('time_signature', '').strip()
    tempo_raw = request.form.get('tempo', '').strip()
    if not time_sig:
        flash('Time signature is required.', 'danger')
        return redirect(url_for('admin_rhythm_upload'))
    if not tempo_raw.isdigit():
        flash('BPM is required and must be a number.', 'danger')
        return redirect(url_for('admin_rhythm_upload'))
```

Then change the `Rhythm(...)` construction (around line 1839-1846) from:
```python
        rhy = Rhythm(
            name=name,
            notes_json=json.dumps(note_list),
            time_signature=request.form.get('time_signature', '4/4'),
            min_duration=request.form.get('min_duration', 'q'),
            difficulty=request.form.get('difficulty', 1, type=int),
            tempo=request.form.get('tempo', 100, type=int),
        )
```
to:
```python
        rhy = Rhythm(
            name=name,
            notes_json=json.dumps(note_list),
            time_signature=time_sig,
            min_duration=request.form.get('min_duration', 'q'),
            difficulty=request.form.get('difficulty', 1, type=int),
            tempo=int(tempo_raw),
        )
```

- [ ] **Step 3: Manually verify in the browser**

Start the dev server (`.venv/bin/python app.py` or the configured preview), log in as admin, navigate to `/admin/rhythms/upload`.
- Submit with Time Signature left on "Choose…" and/or Tempo blank → expect a red flash ("Time signature is required." or "BPM is required and must be a number.") and no new rhythm created.
- Submit with a valid MIDI, Time Signature `3/4`, Tempo `90` → expect success flash with the new rhythm's public ID, and confirm on `/admin/rhythms/<id>/edit` that Time Signature shows `3/4` and Tempo shows `90`.

- [ ] **Step 4: Commit**

```bash
git add templates/admin/rhythm_upload.html app.py
git commit -m "fix: require explicit time signature and BPM on rhythm upload"
```

---

### Task 2: Melody upload — add required time signature + BPM fields

**Files:**
- Modify: `templates/admin/melody_upload.html`
- Modify: `app.py` (`admin_melody_upload`, currently at line 1540)

**Interfaces:**
- Consumes: the canonical time-signature option list from Task 1.

- [ ] **Step 1: Update the template**

In `templates/admin/melody_upload.html`, after the Key Signature block (ends at line 27 `</div>`), insert two new field blocks before the `<div class="d-flex gap-2">` submit-buttons row:

```html
    <div class="mb-3">
      <label class="form-label">Key Signature</label>
      <select name="key_signature" class="form-select">
        {% for k in ['C','G','D','A','E','B','F#','F','Bb','Eb','Ab','Db'] %}
        <option value="{{ k }}" {% if k == 'C' %}selected{% endif %}>{{ k }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="d-flex gap-2">
```
becomes:
```html
    <div class="mb-3">
      <label class="form-label">Key Signature</label>
      <select name="key_signature" class="form-select">
        {% for k in ['C','G','D','A','E','B','F#','F','Bb','Eb','Ab','Db'] %}
        <option value="{{ k }}" {% if k == 'C' %}selected{% endif %}>{{ k }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="mb-3">
      <label class="form-label">Time Signature</label>
      <select name="time_signature" class="form-select" required>
        <option value="" disabled selected>Choose…</option>
        {% for ts in ['4/4','3/4','2/4','6/8','9/8','12/8','5/4','7/8'] %}<option>{{ ts }}</option>{% endfor %}
      </select>
    </div>
    <div class="mb-3">
      <label class="form-label">Tempo (BPM)</label>
      <input name="tempo" type="number" class="form-control" required min="20" max="400" placeholder="e.g. 120" style="max-width:160px">
    </div>
    <div class="d-flex gap-2">
```

- [ ] **Step 2: Add server-side validation and pass values through to the model**

In `app.py`, inside `admin_melody_upload` (around line 1540), after the existing MIDI-file check:
```python
    f = request.files.get('midi_file')
    if not f or not f.filename or not f.filename.endswith('.mid'):
        flash('Please upload a .mid file.', 'danger')
        return redirect(url_for('admin_melody_upload'))
    name = request.form.get('name', '').strip() or f.filename.rsplit('.', 1)[0]
    key  = request.form.get('key_signature', 'C').strip()
```
add immediately after the `key = ...` line:
```python
    time_sig = request.form.get('time_signature', '').strip()
    tempo_raw = request.form.get('tempo', '').strip()
    if not time_sig:
        flash('Time signature is required.', 'danger')
        return redirect(url_for('admin_melody_upload'))
    if not tempo_raw.isdigit():
        flash('BPM is required and must be a number.', 'danger')
        return redirect(url_for('admin_melody_upload'))
```

Then change the `Melody(...)` construction (around line 1564-1569) from:
```python
        mel = Melody(
            name=name,
            midi_filename='',  # set after flush
            notes_json=json.dumps(note_list),
            key_signature=key,
        )
```
to:
```python
        mel = Melody(
            name=name,
            midi_filename='',  # set after flush
            notes_json=json.dumps(note_list),
            key_signature=key,
            time_signature=time_sig,
            tempo=int(tempo_raw),
        )
```

- [ ] **Step 3: Manually verify in the browser**

Navigate to `/admin/melodies/upload`.
- Submit with Time Signature on "Choose…" and/or Tempo blank → expect rejection with a red flash, no new melody created.
- Submit with a valid MIDI, Time Signature `6/8`, Tempo `140` → expect success, and confirm on `/admin/melodies/<id>/edit` that Time Signature shows `6/8` and Tempo shows `140`.

- [ ] **Step 4: Commit**

```bash
git add templates/admin/melody_upload.html app.py
git commit -m "feat: require explicit time signature and BPM on melody upload"
```

---

### Task 3: Harmonic upload — add required BPM field (no time signature)

**Files:**
- Modify: `templates/admin/harmonic_upload.html`
- Modify: `app.py` (`admin_harmonic_upload`, currently at line 2163)

- [ ] **Step 1: Update the template**

In `templates/admin/harmonic_upload.html`, after the Category block (ends before the Difficulty block), insert a Tempo field:

```html
    <div class="mb-3">
      <label class="form-label fw-semibold">Category</label>
      <select name="category" class="form-select">
        {% for cat in ['diatonic','chromatic','modal','blues','jazz','other'] %}
        <option>{{ cat }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="mb-3">
      <label class="form-label fw-semibold">Difficulty</label>
```
becomes:
```html
    <div class="mb-3">
      <label class="form-label fw-semibold">Category</label>
      <select name="category" class="form-select">
        {% for cat in ['diatonic','chromatic','modal','blues','jazz','other'] %}
        <option>{{ cat }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="mb-3">
      <label class="form-label fw-semibold">Tempo (BPM)</label>
      <input name="tempo" type="number" class="form-control" required min="20" max="400" placeholder="e.g. 80" style="max-width:160px">
    </div>
    <div class="mb-3">
      <label class="form-label fw-semibold">Difficulty</label>
```

- [ ] **Step 2: Add server-side validation and pass tempo through to the model**

In `app.py`, inside `admin_harmonic_upload` (around line 2163), after:
```python
    name = request.form.get('name', '').strip() or f.filename.rsplit('.', 1)[0]
    key  = request.form.get('key_signature', 'C').strip()
```
add:
```python
    tempo_raw = request.form.get('tempo', '').strip()
    if not tempo_raw.isdigit():
        flash('BPM is required and must be a number.', 'danger')
        return redirect(url_for('admin_harmonic_upload'))
```

Then change the `ChordProgression(...)` construction (around line 2188-2195) from:
```python
        prog = ChordProgression(
            name=name,
            midi_filename='',  # set after flush
            chords_json=json.dumps(chords_list),
            key_signature=key,
            difficulty=request.form.get('difficulty', 1, type=int),
            category=request.form.get('category', 'diatonic'),
        )
```
to:
```python
        prog = ChordProgression(
            name=name,
            midi_filename='',  # set after flush
            chords_json=json.dumps(chords_list),
            key_signature=key,
            difficulty=request.form.get('difficulty', 1, type=int),
            category=request.form.get('category', 'diatonic'),
            tempo=int(tempo_raw),
        )
```

- [ ] **Step 3: Manually verify in the browser**

Navigate to `/admin/harmonics/upload`.
- Submit with Tempo blank → expect rejection with a red flash, no new progression created.
- Submit with a valid MIDI and Tempo `72` → expect success, and confirm on `/admin/harmonics/<id>/edit` — note this page doesn't show tempo yet (that's Task 4); verify via `.venv/bin/python -c "..."` querying `instance/musicianship.db` for the new row's `tempo` column instead.

- [ ] **Step 4: Commit**

```bash
git add templates/admin/harmonic_upload.html app.py
git commit -m "feat: require explicit BPM on harmonic upload"
```

---

### Task 4: Harmonic edit — expose and require BPM field

**Files:**
- Modify: `templates/admin/harmonic_edit.html`
- Modify: `app.py` (`admin_edit_harmonic`, currently at line 2124)

- [ ] **Step 1: Update the template**

In `templates/admin/harmonic_edit.html`, the Key field block:
```html
      <div class="col-md-3">
        <label class="form-label fw-semibold">Key</label>
        <input name="key_signature" class="form-control" value="{{ prog.key_signature }}">
      </div>
```
becomes (adding a Tempo field alongside it):
```html
      <div class="col-md-3">
        <label class="form-label fw-semibold">Key</label>
        <input name="key_signature" class="form-control" value="{{ prog.key_signature }}">
      </div>
      <div class="col-md-3">
        <label class="form-label fw-semibold">Tempo (BPM)</label>
        <input name="tempo" type="number" class="form-control" required min="20" max="400" value="{{ prog.tempo }}">
      </div>
```

- [ ] **Step 2: Add server-side validation to the route**

In `app.py`, inside `admin_edit_harmonic` (around line 2124), the existing POST handling:
```python
        prog.key_signature = request.form.get('key_signature', prog.key_signature)
        prog.difficulty    = request.form.get('difficulty', prog.difficulty, type=int) or prog.difficulty
```
becomes:
```python
        prog.key_signature = request.form.get('key_signature', prog.key_signature)
        tempo_raw = request.form.get('tempo', '').strip()
        if not tempo_raw.isdigit():
            flash('BPM is required and must be a number.', 'danger')
            return redirect(url_for('admin_edit_harmonic', prog_id=prog_id))
        prog.tempo          = int(tempo_raw)
        prog.difficulty    = request.form.get('difficulty', prog.difficulty, type=int) or prog.difficulty
```

- [ ] **Step 3: Manually verify in the browser**

Navigate to `/admin/harmonics/<id>/edit` for the progression created in Task 3 (tempo `72`).
- Confirm the Tempo field pre-fills with `72`.
- Clear it and submit → expect rejection with a red flash, value unchanged in the DB.
- Change it to `100` and submit → expect success, field shows `100` on reload.

- [ ] **Step 4: Commit**

```bash
git add templates/admin/harmonic_edit.html app.py
git commit -m "feat: expose and require BPM on harmonic edit form"
```

---

### Task 5: Holistic upload — add required time signature + BPM fields

**Files:**
- Modify: `templates/admin/holistic_upload.html`
- Modify: `app.py` (`admin_holistic_upload`, currently at line 1933)

**Interfaces:**
- Consumes: the canonical time-signature option list from Task 1.

- [ ] **Step 1: Update the template**

In `templates/admin/holistic_upload.html`, the Key Signature column:
```html
      <div class="col-md-6"><label class="form-label fw-semibold">Key Signature</label>
        <input name="key_signature" class="form-control" value="C" placeholder="C"></div>
```
becomes (splitting into two `col-md-4`s and adding a third):
```html
      <div class="col-md-4"><label class="form-label fw-semibold">Key Signature</label>
        <input name="key_signature" class="form-control" value="C" placeholder="C"></div>
      <div class="col-md-4"><label class="form-label fw-semibold">Time Signature</label>
        <select name="time_signature" class="form-select" required>
          <option value="" disabled selected>Choose…</option>
          {% for ts in ['4/4','3/4','2/4','6/8','9/8','12/8','5/4','7/8'] %}<option>{{ ts }}</option>{% endfor %}
        </select></div>
      <div class="col-md-4"><label class="form-label fw-semibold">Tempo (BPM)</label>
        <input name="tempo" type="number" class="form-control" required min="20" max="400" placeholder="e.g. 120"></div>
```

- [ ] **Step 2: Add server-side validation and pass values through to the model**

In `app.py`, inside `admin_holistic_upload` (around line 1933), after:
```python
    name = request.form.get('name', '').strip() or wav_file.filename.rsplit('.', 1)[0]
    key  = request.form.get('key_signature', 'C').strip()
```
add:
```python
    time_sig = request.form.get('time_signature', '').strip()
    tempo_raw = request.form.get('tempo', '').strip()
    if not time_sig:
        flash('Time signature is required.', 'danger')
        return redirect(url_for('admin_holistic_upload'))
    if not tempo_raw.isdigit():
        flash('BPM is required and must be a number.', 'danger')
        return redirect(url_for('admin_holistic_upload'))
```

Then change the `HolisticExercise(...)` construction (around line 1979-1985) from:
```python
    h = HolisticExercise(
        name=name,
        folder='',  # set after flush
        wav_filename='',  # set after flush
        key_signature=key,
        melody_notes_json=melody_notes_json,
    )
```
to:
```python
    h = HolisticExercise(
        name=name,
        folder='',  # set after flush
        wav_filename='',  # set after flush
        key_signature=key,
        time_signature=time_sig,
        tempo=int(tempo_raw),
        melody_notes_json=melody_notes_json,
    )
```

- [ ] **Step 3: Manually verify in the browser**

Navigate to `/admin/holistic/upload`.
- Submit with Time Signature on "Choose…" and/or Tempo blank → expect rejection with a red flash, no new exercise created (and no orphaned WAV file left in `static/holistic/` — check the route only writes the WAV to its final slug directory *after* the `HolisticExercise` row is flushed, which happens after this validation, so an early return means no file is written).
- Submit with a WAV file, Time Signature `9/8`, Tempo `110` → expect success, and confirm on `/admin/holistic/<id>/edit` that Time Signature shows `9/8`.

- [ ] **Step 4: Commit**

```bash
git add templates/admin/holistic_upload.html app.py
git commit -m "feat: require explicit time signature and BPM on holistic upload"
```

---

### Task 6: Holistic edit — expose and require BPM field

**Files:**
- Modify: `templates/admin/holistic_edit.html`
- Modify: `app.py` (`admin_edit_holistic`, currently at line 1889)

- [ ] **Step 1: Update the template**

In `templates/admin/holistic_edit.html`, the Time Signature column:
```html
      <div class="col-md-3"><label class="form-label fw-semibold">Time Signature</label>
        <input name="time_signature" class="form-control" value="{{ h.time_signature }}"></div>
```
becomes (adding `required` and a new Tempo column right after it):
```html
      <div class="col-md-3"><label class="form-label fw-semibold">Time Signature</label>
        <input name="time_signature" class="form-control" required value="{{ h.time_signature }}"></div>
      <div class="col-md-3"><label class="form-label fw-semibold">Tempo (BPM)</label>
        <input name="tempo" type="number" class="form-control" required min="20" max="400" value="{{ h.tempo }}"></div>
```

- [ ] **Step 2: Add server-side validation to the route**

In `app.py`, inside `admin_edit_holistic` (around line 1889), the existing POST handling:
```python
        h.key_signature  = request.form.get('key_signature', h.key_signature)
        h.time_signature = request.form.get('time_signature', h.time_signature)
        h.melody_clef    = request.form.get('melody_clef', h.melody_clef)
```
becomes:
```python
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
        h.melody_clef    = request.form.get('melody_clef', h.melody_clef)
```

- [ ] **Step 3: Manually verify in the browser**

Navigate to `/admin/holistic/<id>/edit` for the exercise created in Task 5 (time signature `9/8`, tempo `110`).
- Confirm both fields pre-fill correctly.
- Clear Tempo and submit → expect rejection with a red flash, values unchanged.
- Change Tempo to `95` and submit → expect success, field shows `95` on reload.

- [ ] **Step 4: Commit**

```bash
git add templates/admin/holistic_edit.html app.py
git commit -m "feat: expose and require BPM on holistic edit form"
```

---

### Task 7: Full regression pass

**Files:** none (verification only)

- [ ] **Step 1: Run the full automated test suite**

```bash
.venv/bin/python -m pytest -q
```
Expected: all existing tests still pass (this project's changes don't touch anything the current suite covers, but confirm no accidental breakage — e.g. an unrelated import error from an app.py edit).

- [ ] **Step 2: Spot-check the four other upload/edit forms untouched by this plan**

Confirm `templates/admin/melody_edit.html` and `templates/admin/rhythm_edit.html` (out of scope, already correct) still load and save without errors — navigate to each in the browser and submit unchanged.

- [ ] **Step 3: Commit (if any fixes were needed)**

Only if Step 1 or 2 surfaced a regression that required a fix:
```bash
git add -A
git commit -m "fix: regression from time-sig/BPM required-fields change"
```
