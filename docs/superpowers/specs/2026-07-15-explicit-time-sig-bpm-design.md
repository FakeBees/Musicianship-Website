# Explicit Time Signature & BPM on Admin Exercise Forms

## Problem

Admin upload/edit forms for exercises let time signature and/or BPM (tempo) be
silently defaulted or omitted, even though these are never inferred from the
uploaded MIDI (MIDI parsing in `midi_to_notes.py` only reads `note_on`/`note_off`
events for pitch/duration — it never reads `set_tempo` or `time_signature` meta
messages). The result: newly created exercises can end up with a wrong or
placeholder time signature (`4/4`) or tempo (`120`/`100`) that the admin never
actually chose, discovered only after the fact.

## Goal

Every admin form that creates or edits an exercise with a `time_signature`
and/or `tempo` field must collect that value explicitly from the admin, with
no client- or server-side default — the request is rejected if the field is
missing. Harmonic exercises (`ChordProgression`) are the one exception: they
have no `time_signature` column today (chord blocks carry their own beat
counts) and this project does not add one. Harmonic still gets an explicit,
required BPM field.

## Scope

| Form | Route | Change |
|---|---|---|
| `templates/admin/melody_upload.html` | `admin_melody_upload` (app.py) | Add required time_signature + tempo fields |
| `templates/admin/harmonic_upload.html` | `admin_harmonic_upload` (app.py) | Add required tempo field |
| `templates/admin/harmonic_edit.html` | `admin_edit_harmonic` (app.py) | Add required tempo field |
| `templates/admin/holistic_upload.html` | `admin_holistic_upload` (app.py) | Add required time_signature + tempo fields |
| `templates/admin/holistic_edit.html` | `admin_edit_holistic` (app.py) | Add required tempo field |
| `templates/admin/rhythm_upload.html` | `admin_rhythm_upload` (app.py) | Remove pre-filled tempo default; standardize time-signature option list |

Out of scope (already collect both fields correctly today, no change needed):
`templates/admin/melody_edit.html`, `templates/admin/rhythm_edit.html`.

No database migration — `time_signature` and `tempo` columns already exist on
every model that needs them (`Melody`, `Rhythm`, `HolisticExercise`,
`ChordProgression.tempo`).

## Field design

**Time signature** — `<select name="time_signature" required>`. First option
is a disabled, unselected placeholder (`<option value="" disabled selected>Choose…</option>`)
so no value is picked by default. Real options, standardized across every
form that has this field:
```
4/4, 3/4, 2/4, 6/8, 9/8, 12/8, 5/4, 7/8
```
This is the union of every time-signature value already in use anywhere in
the app (rhythm upload's existing list plus the module-exercise filter list),
so no existing exercise's value falls outside the dropdown when later edited.

**BPM (tempo)** — `<input type="number" name="tempo" required min="20" max="400" placeholder="e.g. 120">`.
No `value` attribute, so the field starts empty.

## Backend validation

HTML5 `required` is client-side only and can be bypassed (disabled JS, raw
POST). Every affected route must also validate server-side:

```python
time_sig = request.form.get('time_signature', '').strip()
tempo_raw = request.form.get('tempo', '').strip()
if not time_sig:  # skip this check on harmonic routes, which have no time_signature field
    flash('Time signature is required.', 'danger')
    return redirect(url_for(<this route>))
if not tempo_raw or not tempo_raw.isdigit():
    flash('BPM is required and must be a number.', 'danger')
    return redirect(url_for(<this route>))
tempo = int(tempo_raw)
```

This replaces the current pattern of silently falling back to a default or
to the previous value (e.g. `request.form.get('tempo', mel.tempo, type=int) or mel.tempo`
becomes a hard validation failure instead of a silent fallback when blank).

## Testing

Manual verification in the browser: submit each of the 6 affected forms (4
upload, 2 edit) with the time-signature/tempo field left blank and confirm
the request is rejected with a flash message and no record is
created/mutated; then submit with a valid value and confirm it's saved and
reflected on the corresponding edit/detail page. No new automated test
coverage is planned — this is pure form-validation surface with no existing
test coverage of these specific routes to extend (checked `tests/` during
brainstorming; the existing suite covers role guards and school schema, not
admin content-upload routes).
