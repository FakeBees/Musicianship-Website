# Holistic Dictation — Line Data Model & Admin Builder (Spec A of 2)

## Problem

Holistic exercises today store their content in a rigid, ad hoc shape on
`HolisticExercise`: one required primary melody line (`melody_notes_json`),
one fixed harmony field (`harmony_chords_json`), and an unstructured
`extra_lines_json` array for anything beyond that. There is no admin UI to
add a line — it's hand-edited JSON in a textarea. There is no persisted
ordering an admin can drag, no per-line MIDI upload/parse flow, and harmony
is not a peer of melody/rhythm — it's a special-cased single field.

This spec (A of 2) replaces that with a proper ordered collection of lines,
each independently typed, named, and MIDI-uploaded, with an admin UI to add
and reorder them. Spec B (separate, follow-on) replaces the *student-facing
rendering* with the true stacked-staff/aligned-chord-block engine; this spec
only has to keep student rendering working, unchanged in appearance, on top
of the new data.

## Goal

- A `HolisticLine` model: any number of melody, rhythm, or harmonic lines,
  each named, ordered, and backed by its own uploaded MIDI file.
- Admin UI: "Add Line" (name, type, clef if melodic, MIDI upload — parses
  immediately) and drag-to-reorder via SortableJS.
- Migration: every existing `HolisticExercise`'s `melody_notes_json` /
  `harmony_chords_json` / `extra_lines_json` becomes `HolisticLine` rows;
  those columns and `melody_clef` are then dropped.
- Grading (`grade_holistic_attempt`) and attempt storage
  (`HolisticAttempt.user_data_json`) key by line ID instead of ad hoc
  string keys (`"melody"`, `"rhythm_1"`).
- Student rendering keeps today's appearance (independent per-line canvas,
  harmony as its own widget) — it only changes *where it reads data from*.

## Data model

```python
class HolisticLine(db.Model):
    id                    = db.Column(db.Integer, primary_key=True)
    holistic_exercise_id  = db.Column(db.Integer, db.ForeignKey('holistic_exercise.id'), nullable=False)
    line_type             = db.Column(db.String(10), nullable=False)   # 'melody' | 'rhythm' | 'harmonic'
    name                  = db.Column(db.String(100), nullable=False)  # e.g. "Soprano", "Kick Drum", "Harmony"
    order                 = db.Column(db.Integer, nullable=False, default=0)
    clef                  = db.Column(db.String(10), nullable=True)    # melody only; null for rhythm/harmonic
    midi_filename         = db.Column(db.String(200), nullable=False)
    content_json          = db.Column(db.Text, nullable=False, default='[]')
    # melody:   [{key, duration[, dotted]}, ...]        (Melody.notes_json shape)
    # rhythm:   [{duration[, dotted]}, ...]              (Rhythm.notes_json shape)
    # harmonic: [{root, quality, ...}, ...]              (ChordProgression.chords_json shape)

    exercise = db.relationship('HolisticExercise', backref=db.backref(
        'lines', order_by='HolisticLine.order', cascade='all, delete-orphan'))

    @property
    def content(self):
        return json.loads(self.content_json)
```

`HolisticExercise` drops `melody_notes_json`, `harmony_chords_json`,
`extra_lines_json`, `melody_clef`, and the `melody_notes`/`harmony_chords`/
`extra_lines` properties. `total_beats`/`num_measures` are recomputed from
`max(line beats across all lines)` instead of `melody_notes` alone, since
after this change melody is no longer guaranteed to be the longest or even
present.

`HolisticAttempt.user_data_json` becomes `{"<line_id>": [...], ...}` (dict
keyed by `HolisticLine.id` as a string, since JSON object keys are always
strings). `scores_json` becomes `{"<line_id>_pitch": ..., "<line_id>_duration": ..., "<line_id>_letter": ..., "<line_id>_quality": ...}`
depending on line type, replacing the current `melody_pitch`/`harmony_letter`/etc.
naming.

## Migration

A one-off script (`migrate_holistic_lines.py`, following this repo's
existing `migrate_*.py` pattern) that, per `HolisticExercise`:
1. Creates the `holistic_line` table (`db.create_all()` picks up the new
   model).
2. For each existing exercise: inserts a `HolisticLine(line_type='melody',
   name='Melody', order=0, clef=h.melody_clef,
   midi_filename=(f'{h.folder}{slug}.mid' if that file exists on disk else ''),
   content_json=h.melody_notes_json)` — the primary-melody MIDI upload was
   always optional, so exercises created without one simply get an empty
   `midi_filename`; `content_json` (already parsed) remains authoritative
   either way.
3. For each entry in `json.loads(h.extra_lines_json)`: inserts a
   `HolisticLine` preserving `type`→`line_type`, `label`→`name`,
   `clef`→`clef` (melody only), `file`→`midi_filename`, `notes`→`content_json`,
   with `order` continuing from the primary melody's `order + 1`.
4. If `h.harmony_chords_json` is non-empty and not just `'[]'`: inserts a
   final `HolisticLine(line_type='harmonic', name='Harmony', midi_filename='',
   content_json=h.harmony_chords_json)`.
5. After all exercises are migrated and verified (row counts match), drops
   `melody_notes_json`, `harmony_chords_json`, `extra_lines_json`,
   `melody_clef` from `holistic_exercise` via raw `ALTER TABLE` (SQLite
   requires table rebuild for column drops — follow the same pattern
   `migrate_phase4_schema.py` already uses for column changes).

## Admin builder UI

Replaces `templates/admin/holistic_upload.html` (unchanged: name, key
signature, time signature, tempo, WAV upload — no per-line data at
creation) and `templates/admin/holistic_edit.html` (currently three raw
JSON textareas — removed entirely).

New section on the edit page: **Lines**, showing each `HolisticLine` as a
draggable card (SortableJS via CDN, matching the CDN-script pattern already
used for VexFlow/Tone.js) with name, type badge, clef (if melodic), and a
Remove button. A warning banner appears once line count exceeds 8 ("many
lines may be hard to read — consider trimming"). An "Add Line" form below:
Name (required), Type (select: Melodic/Rhythmic/Harmonic), Clef (select,
shown only when Type=Melodic), MIDI file (required). Submitting POSTs to a
new route that parses the MIDI immediately — `extract_notes`/`build_json_list`
for melody/rhythm (same as existing melody/rhythm upload routes),
`infer_chords_from_midi` for harmonic (same as the harmonic upload route)
— and creates the `HolisticLine` row. Drag-reordering POSTs the new
`order` values to another new route in one batch request.

## Grading rewrite

`grade_holistic_attempt(exercise, user_data)` (app.py:268-314) currently
special-cases `"melody"`/`"harmony"` and derives extra-line keys from MIDI
filenames. It becomes a single loop over `exercise.lines`, keyed by
`str(line.id)`:
```python
def grade_holistic_attempt(exercise, user_data):
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

## Student-side bridge (no visual change)

`holistic_exercise()` (app.py:871-889) and `holistic_exercise.html` /
`static/js/holistic.js` currently branch on a fixed "melody" line, a fixed
"harmony" widget, and a Jinja loop over `extra_lines_display`. This spec
changes the *source* to `exercise.lines` (one Jinja loop covering every
line, including what used to be "the melody" and "the harmony"), each
still rendered with today's independent-canvas/harmony-widget approach —
`renderStaveForLine()` keyed by `line.id` instead of a filename-derived
key, harmony lines rendered via the existing flexbox chord-block widget
keyed by `line.id` instead of the fixed `"harmony"` key. No layout or
visual change; Spec B replaces this renderer entirely.

## Testing

- New tests for the migration script: build an in-memory `HolisticExercise`
  in the old shape (melody + 2 extra lines + harmony), run the migration
  function, assert the resulting `HolisticLine` rows match in count, order,
  type, and content.
- New tests for `grade_holistic_attempt`'s rewritten generic loop: one
  exercise with a melody line, a rhythm line, and a harmonic line; assert
  per-line score keys and overall average are computed correctly.
- Manual verification in the browser: admin creates a 3-line exercise
  (melody + rhythm + harmonic) via the new builder UI, reorders them via
  drag, and a student completes and submits the exercise, confirming
  scores appear correctly on the results page.
