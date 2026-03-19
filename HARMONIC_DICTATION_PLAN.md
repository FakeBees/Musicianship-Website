# Harmonic Dictation — Implementation Plan

## Overview

Add a fully functional Harmonic Dictation mode to the Musicianship Trainer. The user listens to a chord progression played on piano (from a MIDI file), then assembles their answer using a "chord block" building interface — no sheet music notation required. Grading is split into chord letter accuracy and chord quality accuracy.

This document is written for a Claude Code agent. Read it fully before writing any code.

---

## 1. Dependencies

Add `mido` to `requirements.txt`. This is needed for MIDI parsing during database seeding.

```
mido
```

The existing `@tonejs/midi` CDN script used in `exercise.html` already handles MIDI playback in the browser, so no new front-end MIDI library is needed.

---

## 2. Database — `models.py`

### 2a. New association table

```python
# Many-to-many: ChordProgression <-> Tag
progression_tags = db.Table(
    'progression_tags',
    db.Column('progression_id', db.Integer, db.ForeignKey('chord_progression.id'), primary_key=True),
    db.Column('tag_id',         db.Integer, db.ForeignKey('tag.id'),               primary_key=True),
)
```

### 2b. `ChordProgression` model

Each chord in `chords_json` is a JSON object with the following shape:

```json
{
  "root_pc":    0,          // pitch class 0–11 (C=0, C#=1, … B=11)
  "root_name":  "C",        // canonical name used for display
  "quality":    "major",    // "major" | "minor" | "diminished" | "augmented"
  "bass_pc":    0,          // pitch class of lowest note (for inversions)
  "bass_name":  "C",        // name of bass note
  "seventh":    null,       // null | "major7" | "minor7" | "diminished7"
  "extensions": [],         // list from: "9","b9","#9","11","#11","13","b13"
  "sus":        null        // null | "sus2" | "sus4"
}
```

```python
class ChordProgression(db.Model):
    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(100), nullable=False)
    description     = db.Column(db.String(300))
    midi_filename   = db.Column(db.String(100), nullable=False)
    key_signature   = db.Column(db.String(10), default='C')   # e.g. "C", "Am", "Bb"
    tempo           = db.Column(db.Integer, default=80)
    difficulty      = db.Column(db.Integer, default=1)        # 1–5
    # "diatonic" | "chromatic" | "mode_mixture" | "modal"
    category        = db.Column(db.String(30), default='diatonic')
    chords_json     = db.Column(db.Text, nullable=False)      # JSON array of chord objects
    tags            = db.relationship('Tag', secondary=progression_tags,
                                      backref='progressions', lazy='subquery')

    @property
    def chords(self):
        return json.loads(self.chords_json)

    def __repr__(self):
        return f'<ChordProgression {self.name}>'
```

### 2c. `HarmonicAttempt` model

```python
class HarmonicAttempt(db.Model):
    id                    = db.Column(db.Integer, primary_key=True)
    progression_id        = db.Column(db.Integer, db.ForeignKey('chord_progression.id'), nullable=False)
    progression           = db.relationship('ChordProgression', backref='attempts')
    user_chords_json      = db.Column(db.Text, nullable=False, default='[]')
    chord_letter_accuracy = db.Column(db.Float, default=0.0)
    chord_quality_accuracy= db.Column(db.Float, default=0.0)
    overall_score         = db.Column(db.Float, default=0.0)
    created_at            = db.Column(db.DateTime, server_default=db.func.now())

    @property
    def user_chords(self):
        return json.loads(self.user_chords_json)

    def __repr__(self):
        return f'<HarmonicAttempt prog={self.progression_id} score={self.overall_score:.1f}>'
```

### 2d. Update `Tag` model backref

The new `backref='progressions'` on `ChordProgression.tags` adds a `.progressions` accessor on `Tag`. No other change needed in `Tag` itself.

---

## 3. New Module — `chord_utils.py`

Create `chord_utils.py` in the project root. This module has two responsibilities:

### 3a. MIDI chord inference (`infer_chords_from_midi`)

Called once at seeding time to parse a MIDI file and produce the `chords_json` array.

**Algorithm:**

1. Use `mido.MidiFile` to open the file and collect all note-on/note-off events across all tracks, building a timeline of `(start_tick, pitch_set)` events.
2. Group simultaneous notes into "chords" — a new chord event starts whenever the set of currently sounding notes changes. Ignore very short overlaps (< 10% of a quarter-note tick duration) to avoid false chord changes on legato playing.
3. Filter out chord events shorter than one quarter note so passing tones or grace notes don't register as separate chords.
4. For each distinct pitch set, call `analyse_chord(pitch_set, key_signature)` (see §3b).
5. Return a list of chord dicts in the format described in §2b.

```python
def infer_chords_from_midi(midi_path: str, key_signature: str) -> list[dict]:
    ...
```

### 3b. Chord analysis (`analyse_chord`)

Given a set of MIDI pitch numbers and a key signature string, returns a chord dict.

**Algorithm:**

1. Convert all pitches to pitch classes (pitch % 12). Remove duplicate pitch classes (unison doublings, octave doublings).
2. Try all 12 possible roots (each pitch class in the set) to find the best root that produces a recognised chord quality. Priority: match a known interval pattern (see below) over the smallest number of "unrecognised" tones.
3. Known interval patterns from root (in semitones above root):
   - Major triad: {0, 4, 7}
   - Minor triad: {0, 3, 7}
   - Diminished triad: {0, 3, 6}
   - Augmented triad: {0, 4, 8}
   - Sus2: {0, 2, 7}
   - Sus4: {0, 5, 7}
   - (Seventh intervals added on top of these: maj7=11, min7=10, dim7=9)
4. **Enharmonic interval disambiguation — ♭5 vs. ♯4 (and similar pairs):**
   Ambiguous intervals (those that are 6, 8, or other semitone counts away from the root that could be spelled two ways) must be resolved by determining the pitch's **role in the chord**, not its raw semitone count alone. The rule is:

   - **If the ambiguous interval is serving as the chord's fifth:** use the spelling dictated by the chord quality.
     - Diminished/half-diminished fifth = **♭5** (6 semitones). B-D-F: the F is always ♭5, never ♯4.
     - Augmented fifth = **♯5** (8 semitones). C-E-G♯: the G♯ is always ♯5, never ♭6.
   - **If the chord already has a perfect or quality-defined fifth AND the ambiguous interval is a leftover pitch (extension):** use the extension naming convention.
     - 6 semitones above root when a perfect fifth is also present → **♯11** (e.g., Cmaj7♯11 has both G as the fifth and F♯ as ♯11 — the F♯ is NOT a ♭5, because the fifth is already occupied by G).
     - 8 semitones above root when a major third + perfect fifth are present → **♭13** (e.g., C7♭13: G is the fifth, A♭ is ♭13).
   - **General decision rule:** Identify the core triad first (step 3). Once the triad quality is known, the fifth's spelling is fixed by convention. Any remaining pitch classes are then named as extensions using the following interval-to-extension map (all intervals measured in semitones above the root, after the core triad tones are accounted for):

     | Semitones above root | Extension name | Notes |
     |---|---|---|
     | 1 | ♭9 | |
     | 2 | 9  | (also diatonic second; context determines) |
     | 3 | ♯9 | (only if quality is major/dominant; else it's the minor third) |
     | 5 | 11 | |
     | 6 | ♯11 | **only if a perfect fifth (7 semitones) is also present**; otherwise it would be the diminished fifth, already handled as core triad quality |
     | 8 | ♭13 | **only if a major third (4 semitones) is also present**; otherwise it could be the augmented fifth, already handled |
     | 9 | 13 | |
     | 10 | ♭7 / min7 | part of seventh, not extension list |
     | 11 | maj7 | part of seventh, not extension list |

   This two-pass approach (triad → seventh → extensions) guarantees that ♭5 and ♯11 are never confused with each other.

5. Identify extensions: any remaining pitch classes after the core triad/seventh are mapped using the table in step 4.
6. Identify bass note: the lowest MIDI pitch in the original pitch set. Set `bass_pc` and `bass_name`.
7. Set `root_name` using the key signature's preferred accidental spelling (sharps vs. flats). Use the `KEY_SPELLING` map defined in this file.
8. Return the completed chord dict.

```python
def analyse_chord(pitches: set[int], key_signature: str) -> dict:
    ...
```

### 3c. Chord display name formatting (`format_chord_name`)

Given a chord dict and a notation mode string (`'roman'`, `'nashville'`, or `'lead'`), and the key signature, return a human-readable chord symbol string. Examples:

| Chord dict | Roman (C major) | Nashville (C major) | Lead sheet |
|---|---|---|---|
| C major | I | 1 | C |
| D minor | ii | 2 | Dm |
| B diminished | vii° | 7° | Bdim |
| F# major (chromatic) | #IV | #4 | F# |
| G dominant 7 | V⁷ | 5⁷ | G7 |
| Bb major (mode mix) | ♭VII | ♭7 | B♭ |
| C/E (1st inv) | I/3 | 1/3 | C/E |
| Dm7 | ii⁷ | 2⁷ | Dm7 |
| Bdim7 | vii°⁷ | 7°⁷ | Bdim7 |
| Cmaj7 | Imaj⁷ | 1maj⁷ | Cmaj7 |

**Rules for chord name calculation (do NOT just concatenate the input):**

- Quality suffixes: major = "" (uppercase Roman/Nashville), minor = "m" (lowercase Roman/Nashville), dim = "°", aug = "+", sus2 = "sus2", sus4 = "sus4"
- Seventh suffixes: maj7 = "maj7", min7 = "7" (e.g., G7, not Gmin7), dim7 = "°7" (e.g., Bdim7, not B°(dim7))
- Minor 7 on minor triad = "m7" (e.g., Dm7, not Dm(b7))
- Major 7 on major triad = "maj7" (e.g., Cmaj7)
- Half-diminished = "ø7" or "m7b5" — use "m7b5" for lead sheet, "ø⁷" for Roman/Nashville
- Extensions are appended after the seventh in ascending order
- Bass/inversion: append "/X" where X is the bass note in the current notation system
  - Lead sheet: "/E" (note name)
  - Roman: "/3" (scale degree of bass note relative to the key)
  - Nashville: "/3"
- Chromatic alterations: prepend "♭" or "♯" to the Roman numeral / Nashville number for non-diatonic roots

```python
def format_chord_name(chord: dict, mode: str, key_signature: str) -> str:
    ...

# Helper: compute scale degree (0-indexed) of a pitch class in a given key
def pitch_class_to_scale_degree(pc: int, key_signature: str) -> int | None:
    ...
```

### 3d. Grading (`grade_harmonic_attempt`)

```python
def grade_harmonic_attempt(correct_chords: list[dict], user_chords: list[dict]) -> tuple[float, float, float]:
    """
    Returns (chord_letter_accuracy, chord_quality_accuracy, overall_score) as percentages.

    chord_letter_accuracy: % of chords where root_pc matches (enharmonic-aware).
    chord_quality_accuracy: % of chords where triad quality matches (major/minor/dim/aug/sus2/sus4).
    overall_score: average of the two.

    Extensions (seventh, extensions list) are NOT penalised in chord_quality_accuracy —
    they are shown on the results page for reference but do not affect the score.
    Extra or missing chords count as wrong.
    """
    ...
```

---

## 4. New Module — `generate_harmonic_midi.py`

Create `generate_harmonic_midi.py` in the project root. This script:

1. Defines several sample chord progressions as Python data (root, quality, bass, seventh, extensions, sus, duration in beats).
2. Uses `midiutil.MIDIFile` (same library as `generate_midi.py`) to write each progression as a MIDI file in `static/midi/`.
3. Uses `chord_utils.infer_chords_from_midi` to parse each newly written MIDI file back into chord dicts.
4. Seeds the `ChordProgression` table using Flask app context (same pattern as `generate_midi.py`).

**Voicing helper:** Write a helper function `voice_chord(root_pc, quality, bass_pc, seventh, extensions)` that, given chord data, returns a list of MIDI note numbers for a reasonable closed-position piano voicing with the correct bass note in the lowest position. Use the register around C4 (MIDI 60) for the upper voices.

**Sample progressions to seed — exactly 4, one per category/difficulty tier:**

Each chord is voiced with the bass note in octave 3 and upper voices clustered around octave 4. Each chord lasts 2 beats (half note) at the given tempo. Use the `voice_chord` helper to produce the MIDI note list for each chord.

---

**Progression 1 — `c_major_I_IV_V_I`**
- Key: C major, Tempo: 72, Time sig: 4/4, Difficulty: 1, Category: diatonic
- Chords (in order): I (C major), IV (F major), V (G major), I (C major)
- Exact voicings (MIDI note numbers):
  - I:  bass=C3 (48), upper=E4 (64), G4 (67), C5 (72)
  - IV: bass=F3 (53), upper=A4 (69), C5 (72), F5 (77)
  - V:  bass=G3 (55), upper=B4 (71), D5 (74), G5 (79)
  - I:  bass=C3 (48), upper=E4 (64), G4 (67), C5 (72)
- MIDI filename: `harm_c_major_I_IV_V_I.mid`
- Tags: none

---

**Progression 2 — `g_major_I_V_vi_IV`**
- Key: G major, Tempo: 76, Time sig: 4/4, Difficulty: 1, Category: diatonic
- Chords: I (G major), V (D major), vi (E minor), IV (C major)
- Exact voicings:
  - I:  bass=G3 (55), upper=B4 (71), D5 (74), G5 (79)
  - V:  bass=D3 (50), upper=F#4 (66), A4 (69), D5 (74)
  - vi: bass=E3 (52), upper=G4 (67), B4 (71), E5 (76)
  - IV: bass=C3 (48), upper=E4 (64), G4 (67), C5 (72)
- MIDI filename: `harm_g_major_I_V_vi_IV.mid`
- Tags: none

---

**Progression 3 — `c_major_ii7_V7_Imaj7`**
- Key: C major, Tempo: 80, Time sig: 4/4, Difficulty: 2, Category: diatonic
- Chords: ii⁷ (D minor 7), V⁷ (G dominant 7), Imaj⁷ (C major 7)
- Exact voicings:
  - ii⁷:   bass=D3 (50), upper=F4 (65), A4 (69), C5 (72)
  - V⁷:    bass=G3 (55), upper=B4 (71), D5 (74), F5 (77)
  - Imaj⁷: bass=C3 (48), upper=E4 (64), G4 (67), B4 (71)
- MIDI filename: `harm_c_major_ii7_V7_Imaj7.mid`
- Tags: `contains:V7`

---

**Progression 4 — `c_major_I_bVII_IV_I`**
- Key: C major, Tempo: 72, Time sig: 4/4, Difficulty: 3, Category: mode_mixture
- Chords: I (C major), ♭VII (B♭ major — borrowed from C mixolydian/Dorian), IV (F major), I (C major)
- Exact voicings:
  - I:   bass=C3 (48), upper=E4 (64), G4 (67), C5 (72)
  - ♭VII: bass=Bb2 (46), upper=D4 (62), F4 (65), Bb4 (70)
  - IV:  bass=F3 (53), upper=A4 (69), C5 (72), F5 (77)
  - I:   bass=C3 (48), upper=E4 (64), G4 (67), C5 (72)
- MIDI filename: `harm_c_major_I_bVII_IV_I.mid`
- Tags: `contains:bVII`

---

For any tag named with "contains:" (e.g., `contains:V7`, `contains:bVII`), create the `Tag` record if it doesn't already exist and associate it with the progression.

**Usage:**

```
python generate_harmonic_midi.py
```

---

## 5. Routes — additions to `app.py`

Add the following imports at the top if not already present:

```python
from models import db, Melody, Tag, UserAttempt, Rhythm, RhythmAttempt, \
                   ChordProgression, HarmonicAttempt
from chord_utils import grade_harmonic_attempt, format_chord_name
```

### 5a. Index page

```python
@app.route('/harmonic')
def harmonic_index():
    all_tags        = Tag.query.filter(Tag.progressions.any()).order_by(Tag.name).all()
    progressions    = ChordProgression.query.all()
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
                           all_tags=all_tags,
                           progressions_data=progressions_data,
                           categories=categories)
```

### 5b. Random progression redirect

```python
@app.route('/harmonic/random')
def random_harmonic():
    categories  = request.args.getlist('category')
    difficulties= request.args.getlist('difficulty', type=int)
    tags        = request.args.getlist('tag')

    session['last_harmonic_categories']  = categories
    session['last_harmonic_difficulties']= difficulties
    session['last_harmonic_tags']        = tags

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
```

### 5c. Exercise page

```python
@app.route('/harmonic/exercise/<int:progression_id>')
def harmonic_exercise(progression_id):
    progression = ChordProgression.query.get_or_404(progression_id)
    chords = progression.chords
    unlock_seventh    = any(c.get('seventh')                    for c in chords)
    unlock_extensions = any(c.get('extensions')                 for c in chords)
    unlock_sus        = any(c.get('sus')                        for c in chords)
    show_chord_count  = session.get('last_harmonic_show_chord_count', False)
    return render_template('harmonic_exercise.html',
                           progression=progression,
                           unlock_seventh=unlock_seventh,
                           unlock_extensions=unlock_extensions,
                           unlock_sus=unlock_sus,
                           show_chord_count=show_chord_count,
                           num_chords=len(chords))
```

### 5d. Submit endpoint

```python
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
```

### 5e. Results page

```python
@app.route('/harmonic/results/<int:attempt_id>')
def harmonic_results(attempt_id):
    attempt        = HarmonicAttempt.query.get_or_404(attempt_id)
    progression    = attempt.progression
    correct_chords = progression.chords
    user_chords    = attempt.user_chords

    comparison = []
    total = max(len(correct_chords), len(user_chords))
    for i in range(total):
        c = correct_chords[i] if i < len(correct_chords) else None
        u = user_chords[i]    if i < len(user_chords)    else None
        comparison.append({
            'index':        i + 1,
            'correct':      c,
            'user':         u,
            'letter_match': (c and u and c['root_pc'] == u['root_pc']),
            'quality_match':(c and u and c['quality'] == u['quality']),
        })

    # Build next URL from session
    from urllib.parse import urlencode
    cats   = session.get('last_harmonic_categories', [])
    diffs  = session.get('last_harmonic_difficulties', [])
    tags   = session.get('last_harmonic_tags', [])
    params = (
        [('category',   c) for c in cats]
        + [('difficulty', d) for d in diffs]
        + [('tag',        t) for t in tags]
    )
    next_url = url_for('random_harmonic')
    if params:
        next_url += '?' + urlencode(params)

    return render_template('harmonic_results.html',
                           attempt=attempt,
                           progression=progression,
                           comparison=comparison,
                           next_url=next_url)
```

### 5f. Update `home.html`

Remove the `style="opacity:0.55;cursor:default;"` and `Coming Soon` footer from the Harmonic Dictation card. Replace with an active `<a href="{{ url_for('harmonic_index') }}">` wrapper and a `bg-warning text-dark` footer saying `Start →`.

---

## 6. Template — `templates/harmonic_index.html`

Extend `base.html`. Mirror the structure of `rhythm_index.html` (filter sidebar + start button), adapted for harmonic dictation filters.

**Filters available:**
- Category (checkboxes): Diatonic, Chromatic, Mode Mixture, Modal
- Difficulty (checkboxes): 1, 2, 3, 4, 5
- Tags (checkboxes, dynamically populated from DB): show tags whose name starts with "contains:" separately under a "Contains Chord" section, stripping the "contains:" prefix for display (e.g., the tag `contains:bVII` displays as `♭VII`). Show all other tags under "Other Tags".
- **Show chord count** (toggle/checkbox, default off): When enabled, the exercise building area pre-fills with the exact number of empty placeholder slots, so the user knows how many chords are in the progression. When disabled, the building area starts completely empty. This setting is stored in the session as `last_harmonic_show_chord_count` and persists across exercises until changed.

The form `GET`s to `/harmonic/random` with the selected filter params. Include `show_chord_count` as an additional query param (value `1` or `0`). The `random_harmonic` route must read this param and store it in `session['last_harmonic_show_chord_count']`, then pass it to the exercise route. Update `build_next_harmonic_url` accordingly.

---

## 7. Template — `templates/harmonic_exercise.html`

Extend `base.html`. Load `@tonejs/midi` and `Tone.js` from the same CDNs used in `exercise.html`.

### Layout (top to bottom):

**Breadcrumb:** Harmonic Dictation > Exercise

**Listen card** (identical to `exercise.html` listen card):
- Play / Stop buttons
- Play count badge
- **Key Reference button** — plays a I–IV–V–I cadence in the current key (i–iv–V–i for minor keys, using a major V from harmonic minor). See below for voicing spec and implementation.
- **Key display:** Show the key as a plain-text badge in the Listen card header (no staff notation). Example: `Key: C major` or `Key: A minor`. Use Bootstrap `badge bg-info text-dark` or similar. The key string should be derived from `progression.key_signature` — if it ends in 'm' display as minor (e.g., `"Am"` → `"A minor"`), otherwise as major (e.g., `"C"` → `"C major"`, `"Bb"` → `"B♭ major"`). Note: flat symbols in key names should render as `♭` not the letter `b` wherever displayed.

#### Key Reference — chord playback spec

The reference plays four chords (half-note duration each, at 72 BPM) using Tone.js. Because chords require simultaneous notes, this **cannot** use the existing `playNoteArray` function from `player.js` (which is monophonic/sequential). Implement a separate `playChordArray(chords, bpm, onDone)` function in `harmonic.js`, where `chords` is an array of arrays of note name strings (e.g. `[["C3","E4","G4","C5"], ...]`).

**Voicing principle:** Each chord has a single bass note approximately one octave below the triad. The three upper voices form a close-position triad and move with minimal voice movement (parsimonious leading) between chords. Do NOT just stack root-position triads mechanically — voice the upper notes so each moves to the nearest available chord tone.

**Standard upper-voice motion for major I–IV–V–I:**
- I → IV: one common tone stays, other two move up by step
- IV → V: upper voices move by step, mixing up and down motion to avoid parallel fifths
- V → I: leading tone (7th scale degree) resolves up by half step; fifth stays or moves down

**Standard upper-voice motion for minor i–iv–V–i** (V is major, raised 7th):
- Same principle; the raised 7th of the harmonic minor scale acts as the leading tone and resolves up to the tonic.

**`HARM_KEY_REFERENCE` lookup table** in `harmonic.js`: Define a JS object keyed by key signature string (same keys as `KEY_SCALES` in `exercise.html`) where each value is an array of 4 chord note arrays. Example entries:

```js
const HARM_KEY_REFERENCE = {
  // Major keys — I, IV, V, I
  'C':  [['C3','E4','G4','C5'], ['F3','F4','A4','C5'], ['G3','G4','B4','D5'], ['C3','E4','G4','C5']],
  'G':  [['G2','B3','D4','G4'], ['C3','C4','E4','G4'], ['D3','D4','F#4','A4'],['G2','B3','D4','G4']],
  'F':  [['F2','A3','C4','F4'], ['Bb2','Bb3','D4','F4'],['C3','C4','E4','G4'], ['F2','A3','C4','F4']],
  'Bb': [['Bb2','D4','F4','Bb4'],['Eb3','Eb4','G4','Bb4'],['F3','F4','A4','C5'],['Bb2','D4','F4','Bb4']],
  'D':  [['D3','F#4','A4','D5'], ['G3','G4','B4','D5'], ['A3','A4','C#5','E5'],['D3','F#4','A4','D5']],
  // ... (continue for all keys present in KEY_SCALES: E, A, B, Eb, Ab, Db, Gb, F#)
  // Minor keys — i, iv, V (major), i
  'Am': [['A2','E4','A4','C5'], ['D3','F4','A4','D5'], ['E3','E4','G#4','B4'],['A2','E4','A4','C5']],
  'Em': [['E3','B3','E4','G4'], ['A3','A4','C5','E5'], ['B3','B4','D#5','F#5'],['E3','B3','E4','G4']],
  'Dm': [['D3','A3','D4','F4'], ['G3','G4','Bb4','D5'], ['A3','A4','C#5','E5'],['D3','A3','D4','F4']],
  'Gm': [['G2','D4','G4','Bb4'],['C3','C4','Eb4','G4'], ['D3','D4','F#4','A4'],['G2','D4','G4','Bb4']],
  'Cm': [['C3','G3','C4','Eb4'],['F3','F4','Ab4','C5'], ['G3','G4','B4','D5'], ['C3','G3','C4','Eb4']],
  'Fm': [['F2','C4','F4','Ab4'],['Bb2','Bb3','Db4','F4'],['C3','C4','E4','G4'], ['F2','C4','F4','Ab4']],
};
```

Complete the table for all keys present in `KEY_SCALES` in `exercise.html`. For any key not in the table, fall back to C major / A minor as appropriate.

The button label, disabled/loading states, and click handler should follow the same pattern as the Key Reference button in `exercise.html`.

**Build Your Answer card:**

```
┌─────────────────────────────────────────────────────────────┐
│  Notation: [Nashville] [Roman Numerals] [Lead Sheet]        │
│                                                             │
│  Diatonic Palette (7 buttons, one per diatonic triad):      │
│  [  I  ] [  ii  ] [  iii  ] [  IV  ] [  V  ] [  vi  ] [vii°]│
│                                                             │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
│  Modifiers (shown when a chord block is selected):          │
│                                                             │
│  Chromatic: [♭ Lower]  [♯ Raise]                            │
│  Quality:   [maj] [min] [dim] [aug]                         │
│  Sus:       [sus2] [sus4]                                   │
│  Seventh:   [maj7] [min7]  (+[dim7] if block is diminished) │
│             (locked unless any chord in progression uses 7th)│
│  Extensions:[9][♭9][#9][11][#11][13][♭13]                   │
│             (locked unless any chord in progression uses ext)│
│  Bass note: [C][C#][D][D#][E][F][F#][G][G#][A][A#][B]      │
│             (chord tones: normal color; non-chord: muted)   │
│                                                             │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
│                                                             │
│  Building Area:                                             │
│  ┌──────┐ ┌──────┐ ┌──────┐                                │
│  │  I   │ │  IV  │ │  V7  │  ← chord blocks                │
│  └──────┘ └──────┘ └──────┘                                │
│  (If show_chord_count=true, pre-fill with N empty           │
│   placeholder slots. Filled blocks replace placeholders     │
│   when added from the palette.)                             │
│  [Undo Last]  [Clear All]                                   │
└─────────────────────────────────────────────────────────────┘
```

**Submit / Back buttons** (same layout as melodic exercise page)

### Template data injected from Flask:

```html
<script>
  const PROGRESSION_ID  = {{ progression.id }};
  const MIDI_URL        = "{{ url_for('static', filename='midi/' + progression.midi_filename) }}";
  const KEY_SIGNATURE   = "{{ progression.key_signature }}";
  const PROGRESSION_TEMPO = {{ progression.tempo }};

  // Unlock flags — computed server-side (see route 5c) so the user can't inspect the DOM to cheat.
  const UNLOCK_SEVENTH    = {{ unlock_seventh | tojson }};
  const UNLOCK_EXTENSIONS = {{ unlock_extensions | tojson }};
  const UNLOCK_SUS        = {{ unlock_sus | tojson }};

  // Chord count hint (from session preference set on index page)
  const SHOW_CHORD_COUNT  = {{ show_chord_count | tojson }};
  const NUM_CHORDS        = {{ num_chords }};
</script>
```

---

## 8. JavaScript — `static/js/harmonic.js`

This file drives the entire chord-building interface. It does NOT render sheet music.

### 8a. State

```js
let notationMode = 'roman';    // 'roman' | 'nashville' | 'lead'
let blocks       = [];         // array of chord objects (same shape as chord_utils chord dict)
let selectedIdx  = null;       // index of currently selected block, or null

// Populated from template variables
// KEY_SIGNATURE, UNLOCK_SEVENTH, UNLOCK_EXTENSIONS, UNLOCK_SUS
```

### 8b. Diatonic palette

Compute the 7 diatonic triads for `KEY_SIGNATURE` in JavaScript using a lookup table of major and minor keys. For each degree, create a button showing the chord name in the current `notationMode`. Clicking a button calls `addBlock(chordObj)`.

Include a JS lookup table covering all keys in the existing `KEY_SCALES` object in `exercise.html` as a reference for which notes are diatonic.

### 8c. Block rendering

The building area is a `<div id="chord-building-area">`. Each block is a `<div class="chord-block">` showing the chord name formatted by a JS equivalent of `format_chord_name`. Clicking a block sets `selectedIdx` and re-renders the modifier panel.

### 8d. Modifier panel

Rendered below the palette. All modifier buttons update `blocks[selectedIdx]` and re-render the building area and modifier panel.

**Chromatic alteration:** Raise or lower `root_pc` by 1. If raised/lowered away from a diatonic position, set an `alteration` flag on the block for display purposes. Update `root_name` using a helper function that picks the correct enharmonic spelling based on direction (raise → sharp, lower → flat).

**Quality:** Set `quality` on the selected block. Apply the following modifier-reset rules when quality changes — clear **only** modifiers that are invalid for the new quality, keep the rest:

| Modifier | Clear when… |
|---|---|
| `seventh: 'diminished7'` | quality changes away from `'diminished'` |
| `seventh: 'major7'` | quality changes to `'minor'`, `'diminished'`, or `'augmented'` (maj7 is only natural on major chords) |
| `sus` | quality changes to anything other than `null` — i.e., explicitly setting major/minor/dim/aug clears the sus designation (if the user had set sus, then changes quality, sus is cleared) |
| `extensions` | never auto-cleared on quality change; user removes them manually |
| `bass_pc / bass_name` | never auto-cleared; any chord can have any bass note |

Additionally, conditionally show/hide the `dim7` seventh button: it is only visible when `blocks[selectedIdx].quality === 'diminished'`. If the `dim7` button was active and the quality changes away from diminished, clear it (covered by the table above).

**Sus:** Set or clear `sus` on the selected block. When a sus chord is active, the quality buttons (maj/min/dim/aug) are visually disabled (greyed out, `disabled` attribute set) since sus chords don't carry a major/minor triad quality. Clicking a quality button while sus is active first clears the sus, then sets the quality.

**Seventh:** Only rendered if `UNLOCK_SEVENTH === true`. Set or clear `seventh`. Show `dim7` option only if `blocks[selectedIdx].quality === 'diminished'`.

**Extensions:** Only rendered if `UNLOCK_EXTENSIONS === true`. Each extension button is a toggle — clicking adds it to the `extensions` array if absent, removes it if present.

**Bass note buttons:** 12 buttons for C through B. A button is "normal" (Bootstrap `btn-outline-secondary`) if its pitch class is in the chord's tones; "muted" (Bootstrap `btn-outline-light text-muted`) if not (meaning it would create a slash chord with a non-chord-tone bass). Clicking sets `bass_pc` and `bass_name`.

### 8e. Notation mode toggle

Three buttons: Nashville | Roman Numerals | Lead Sheet. Switching mode re-renders all chord block labels and the diatonic palette labels without changing any chord data.

### 8f. Chord name formatting (JS)

Implement `formatChordName(chord, mode, keySignature)` in JavaScript that mirrors the Python `format_chord_name` function. This is used for real-time display. The Python version is used for server-side grading display on the results page.

Key rules (repeat from §3c):
- Cm7 not Cm(♭7)
- Cmaj7 not CM7
- Bdim7 not B°(dim7) or Bb7
- G7 not Gmin7 (dominant seventh = just "7")
- Half-diminished: "m7b5" for lead sheet, "ø7" for Roman/Nashville
- Non-chord bass: append "/X"

### 8g. Submission

```js
document.getElementById('btn-submit').addEventListener('click', async () => {
  const response = await fetch(`/harmonic/submit/${PROGRESSION_ID}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ chords: blocks })
  });
  const data = await response.json();
  if (data.redirect) window.location.href = data.redirect;
});
```

---

## 9. Template — `templates/harmonic_results.html`

Extend `base.html`. Load `Tone.js` and `@tonejs/midi` for the "Play Original" button.

### Layout:

**Breadcrumb:** Harmonic Dictation > Results

**Play Original card:** Play/Stop buttons using the same `player.js` pattern.

**Correct Answer card:** A horizontal row of chord blocks showing the correct chords, labelled using the same notation toggle as the exercise page (Nashville / Roman / Lead Sheet). The notation mode defaults to whatever the user last had selected on the exercise page — pass it as a query param `notation` when redirecting from the submit endpoint, or default to `'roman'`. Pass the pre-formatted chord names for all three modes from the route using `format_chord_name` so the toggle works without a page reload (same JS approach as `harmonic.js`).

**Your Answer card:** A horizontal row of chord blocks showing the user's submitted chords. Each block is colour-coded:
- Root correct + quality correct: green (`bg-success text-white`)
- Root correct, quality wrong: yellow (`bg-warning text-dark`)
- Root wrong: red (`bg-danger text-white`)
- Extra block (user submitted more chords than in correct answer): grey

**Score summary card:**

```
Overall: XX%    Chord Letter: XX%    Chord Quality: XX%
```

**Actions:** Next Progression button (links to `next_url`) | Back to Harmonic Dictation button

---

## 10. CSS additions — `static/css/style.css`

Add styles for:

```css
/* Chord blocks in the building area */
.chord-block {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 64px;
  height: 56px;
  border: 2px solid #6c757d;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  font-size: 1rem;
  user-select: none;
  background: #fff;
  transition: border-color 0.15s, background 0.15s;
  padding: 0 10px;
}
.chord-block.selected {
  border-color: #0d6efd;
  background: #e7f1ff;
}
.chord-block.correct  { background: #198754; color: #fff; border-color: #198754; }
.chord-block.partial  { background: #ffc107; color: #000; border-color: #ffc107; }
.chord-block.wrong    { background: #dc3545; color: #fff; border-color: #dc3545; }

/* Modifier panel */
.modifier-panel { border-top: 1px solid #dee2e6; padding-top: 0.75rem; margin-top: 0.75rem; }
.modifier-row   { display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; margin-bottom: 0.4rem; }
.modifier-label { font-size: 0.8rem; font-weight: 600; color: #6c757d; min-width: 80px; }

/* Non-chord-tone bass buttons */
.bass-btn.non-chord { opacity: 0.45; }

/* Chord building area */
#chord-building-area {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  min-height: 72px;
  align-items: center;
  padding: 0.5rem;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px dashed #ced4da;
}
#chord-building-area .placeholder-text {
  color: #adb5bd;
  font-size: 0.9rem;
}
```

---

## 11. Update `init-db` CLI command

The existing `flask init-db` command calls `db.create_all()`. This automatically picks up new models. No change needed, but **the developer must run `flask init-db` (or `python generate_harmonic_midi.py` which also calls `db.create_all()` inside app context) before running `generate_harmonic_midi.py`**.

Document in a comment in `generate_harmonic_midi.py`:

```python
# Run this script once to create MIDI files and seed the harmonic dictation database.
# Prerequisites: pip install mido midiutil flask flask-sqlalchemy
# Usage: python generate_harmonic_midi.py
```

---

## 12. Key edge cases and constraints to handle

1. **Empty building area on submit:** If the user submits zero chord blocks, return a score of 0 and still save the attempt.
2. **More user chords than correct chords:** Extra blocks count as wrong for grading. Display them as red on the results page.
3. **Fewer user chords than correct chords:** Missing chords count as wrong. Display blank/grey placeholder blocks on the results page.
4. **MIDI files with only one note at a time (non-chordal MIDI):** `infer_chords_from_midi` should return an empty list and log a warning. The seeding script should raise an error if it receives an empty chord list.
5. **Key signatures with flats vs. sharps:** `analyse_chord` must use the key's preferred accidental spelling for `root_name` and `bass_name` (e.g., in Bb major, use "Bb" not "A#").
6. **Minor key input (e.g., "Am"):** The diatonic palette is always based on the **natural minor** scale. For "Am": i (Am), ii° (Bdim), III (C), iv (Dm), v (Em), VI (F), VII (G). The user can manually raise the v to V (minor → major) using the quality modifier, and raise the VII to vii° (major → diminished) using the quality modifier. The `format_chord_name` function must handle both major and minor key signatures.

---

## 13. File checklist

New files to create:
- [ ] `chord_utils.py`
- [ ] `generate_harmonic_midi.py`
- [ ] `templates/harmonic_index.html`
- [ ] `templates/harmonic_exercise.html`
- [ ] `templates/harmonic_results.html`
- [ ] `static/js/harmonic.js`

Files to modify:
- [ ] `models.py` — add `ChordProgression`, `HarmonicAttempt`, `progression_tags`
- [ ] `app.py` — add 5 new routes, update imports
- [ ] `templates/home.html` — activate the Harmonic Dictation card
- [ ] `static/css/style.css` — add chord block and modifier panel styles
- [ ] `requirements.txt` — add `mido`
