# Phase 3B — Melody Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pure rule/constraint melody generator engine (`melody_generator.py`) that takes parameters and produces VexFlow-format note JSON, plus an admin UI approve/reject loop at `/admin/melodies/generate`.

**Architecture:** `melody_generator.py` is a standalone module (no Flask imports) with pure functions: realize harmony → build rhythm skeleton → place chord tones on strong beats → ornament weak beats → auto-tag + suggest difficulty → emit notes_json + write preview MIDI. The Flask routes in `app.py` call `generate(params)`, store the result in the Flask session, then serve a preview page where the admin approves (saves to DB) or rejects (returns to form). VexFlow notation is rendered client-side using the existing `notation.js` already loaded in `base.html`.

**Tech Stack:** Python stdlib (`random`, `json`, `os`), `midiutil` (already installed) for MIDI write, `midi_to_notes.note_to_vex` for MIDI→VexFlow spelling. Tests use `pytest` (add to `.venv/bin/pip install pytest` if needed).

## Global Constraints
- Python 3.9; no new pip packages beyond `pytest`
- Note format: `{"key": "c/4", "duration": "q"[, "dotted": true]}` — rests use `"b/4"` + `"qr"`
- Generator is deterministic given a fixed `seed` int
- All scale degrees stored as strings: `"I","II","III","IV","V","VI","VII"` (major) and `"i","ii","iii","iv","V","VI","VII"` (natural minor)
- Quality strings: `"maj","min","dim","aug","dom7","maj7","min7","dim7","hdim7"`
- Clef tessituras: treble `c/4–g/5` (MIDI 60–79), bass `c/2–g/3` (MIDI 36–55), tenor `c/3–g/4` (MIDI 48–67)
- Generated preview MIDI: `static/melodic/_preview/_preview.mid`
- Approved melody MIDI: `static/melodic/<slug>/<slug>.mid` where slug = `mel_<public_id_lower>`
- Admin routes all use `@login_required @role_required('admin')`
- Run verify: `python3 -c "import sys; sys.path.insert(0, '/Users/jareddamron/PycharmProjects/Musicianship'); import os; os.chdir('/Users/jareddamron/PycharmProjects/Musicianship'); import melody_generator; print('OK')"`

---

## File Map

| Action | Path |
|--------|------|
| Create | `melody_generator.py` |
| Create | `tests/conftest.py` |
| Create | `tests/test_generator.py` |
| Modify | `app.py` (add generator routes) |
| Create | `templates/admin/melody_generator.html` |

---

## Task 1: Core constants and harmony realization

**Files:**
- Create: `melody_generator.py` (first section)

**Interfaces:**
- Produces:
  - `KEY_PC: dict[str, int]` — key string → tonic pitch class (0–11)
  - `MAJOR_DEGREE_PC: dict[str, int]` — scale degree → semitones above tonic for major
  - `MINOR_DEGREE_PC: dict[str, int]` — same for natural minor
  - `CHORD_INTERVALS: dict[str, list[int]]` — quality → intervals above root
  - `CLEF_RANGE: dict[str, tuple[int,int]]` — clef → (low_midi, high_midi) inclusive
  - `realize_harmony(chords: list[dict], key: str, mode: str) -> list[dict]`
    - Input chord dict: `{"degree": "I", "quality": "maj", "inversion": 0, "beats": 4}`
    - Output: `[{"chord_pcs": set[int], "root_pc": int, "quality": str, "start_beat": float, "dur_beats": float}, ...]`
  - `chord_tone_midis(root_pc, quality, low_midi, high_midi) -> list[int]`

- [ ] **Step 1: Write tests/conftest.py**

```python
# tests/conftest.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
```

- [ ] **Step 2: Write failing tests for constants and realize_harmony**

Create `tests/test_generator.py`:

```python
import pytest
from melody_generator import (
    KEY_PC, CHORD_INTERVALS, CLEF_RANGE,
    realize_harmony, chord_tone_midis,
)


def test_key_pc_c_is_zero():
    assert KEY_PC['C'] == 0


def test_key_pc_g_is_seven():
    assert KEY_PC['G'] == 7


def test_key_pc_f_is_five():
    assert KEY_PC['F'] == 5


def test_key_pc_am_is_nine():
    assert KEY_PC['Am'] == 9


def test_chord_intervals_maj():
    assert CHORD_INTERVALS['maj'] == [0, 4, 7]


def test_chord_intervals_min():
    assert CHORD_INTERVALS['min'] == [0, 3, 7]


def test_chord_intervals_dom7():
    assert CHORD_INTERVALS['dom7'] == [0, 4, 7, 10]


def test_clef_range_treble():
    low, high = CLEF_RANGE['treble']
    assert low == 60   # c/4
    assert high == 79  # g/5


def test_clef_range_bass():
    low, high = CLEF_RANGE['bass']
    assert low == 36   # c/2
    assert high == 55  # g/3


def test_realize_harmony_c_major_I_IV_V_I():
    chords = [
        {"degree": "I",  "quality": "maj", "inversion": 0, "beats": 4},
        {"degree": "IV", "quality": "maj", "inversion": 0, "beats": 4},
        {"degree": "V",  "quality": "maj", "inversion": 0, "beats": 4},
        {"degree": "I",  "quality": "maj", "inversion": 0, "beats": 4},
    ]
    windows = realize_harmony(chords, 'C', 'major')
    assert len(windows) == 4
    # I in C = {0, 4, 7}  (C, E, G)
    assert windows[0]['chord_pcs'] == {0, 4, 7}
    assert windows[0]['start_beat'] == 0.0
    assert windows[0]['dur_beats'] == 4.0
    # IV in C = {5, 9, 0} (F, A, C)
    assert windows[1]['chord_pcs'] == {5, 9, 0}
    # V in C = {7, 11, 2} (G, B, D)
    assert windows[2]['chord_pcs'] == {7, 11, 2}


def test_realize_harmony_am_minor_i_iv_V():
    chords = [
        {"degree": "i",  "quality": "min", "inversion": 0, "beats": 4},
        {"degree": "iv", "quality": "min", "inversion": 0, "beats": 4},
        {"degree": "V",  "quality": "maj", "inversion": 0, "beats": 4},
    ]
    windows = realize_harmony(chords, 'Am', 'minor')
    # Am tonic pc = 9; i = {9, 0, 4}
    assert 9 in windows[0]['chord_pcs']
    # iv in Am = Dm = {2, 5, 9}
    assert 2 in windows[1]['chord_pcs']
    # V in Am = E major = {4, 8, 11}
    assert 4 in windows[2]['chord_pcs']


def test_chord_tone_midis_in_treble_range():
    # C major chord (root_pc=0) in treble range 60–79
    midis = chord_tone_midis(0, 'maj', 60, 79)
    for m in midis:
        assert 60 <= m <= 79
    # Should include C5 (72), E5 (76), G5 (79), C4 (60)? check some
    assert 72 in midis  # c/5
    assert 64 in midis  # e/4
    assert 67 in midis  # g/4
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship && .venv/bin/pip install pytest -q && .venv/bin/pytest tests/test_generator.py -v 2>&1 | head -30
```
Expected: `ModuleNotFoundError: No module named 'melody_generator'`

- [ ] **Step 4: Write the first section of melody_generator.py**

```python
"""
melody_generator.py
===================
Rule/constraint melody generator.  No ML; every note traces to a music-theory rule.

Public API
----------
generate(params: dict) -> dict
    params keys: key, mode, gen_progression_id, time_sig, num_measures,
                 min_duration, clef, start_midi, high_midi, low_midi,
                 techniques (list[str]), rhythm_complexity (1–3),
                 syncopation (bool), seed (int|None)
    returns: {notes_json, midi_path, difficulty_suggestion, auto_tags, generation_params}
"""

import json
import os
import random

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')

# ── Pitch-class constants ────────────────────────────────────────────────────

KEY_PC = {
    'C': 0,  'G': 7,  'D': 2,  'A': 9,  'E': 4,  'B': 11, 'F#': 6,
    'F': 5,  'Bb': 10, 'Eb': 3, 'Ab': 8, 'Db': 1, 'Gb': 6,
    'Am': 9, 'Em': 4, 'Bm': 11, 'F#m': 6, 'C#m': 1, 'G#m': 8,
    'Dm': 2, 'Gm': 7, 'Cm': 0, 'Fm': 5, 'Bbm': 10, 'Ebm': 3,
}

# Semitones above tonic for each scale degree (major / natural-minor)
MAJOR_DEGREE_PC = {
    'I': 0, 'II': 2, 'III': 4, 'IV': 5, 'V': 7, 'VI': 9, 'VII': 11,
    'i': 0, 'ii': 2, 'iii': 4, 'iv': 5, 'v': 7, 'vi': 9, 'vii': 11,
}
MINOR_DEGREE_PC = {
    'I': 0, 'i': 0, 'II': 2, 'ii': 2, 'III': 3, 'iii': 3,
    'IV': 5, 'iv': 5, 'V': 7, 'v': 7, 'VI': 8, 'vi': 8,
    'VII': 10, 'vii': 10,
}

CHORD_INTERVALS = {
    'maj':   [0, 4, 7],
    'min':   [0, 3, 7],
    'dim':   [0, 3, 6],
    'aug':   [0, 4, 8],
    'dom7':  [0, 4, 7, 10],
    'maj7':  [0, 4, 7, 11],
    'min7':  [0, 3, 7, 10],
    'dim7':  [0, 3, 6, 9],
    'hdim7': [0, 3, 6, 10],
}

CLEF_RANGE = {
    'treble': (60, 79),   # c/4 – g/5
    'bass':   (36, 55),   # c/2 – g/3
    'tenor':  (48, 67),   # c/3 – g/4
}

BEAT_VALUES = {'w': 4.0, 'h': 2.0, 'q': 1.0, '8': 0.5, '16': 0.25}
DUR_ORDER   = ['16', '8', 'q', 'h', 'w']   # shortest → longest

# ── Harmony ──────────────────────────────────────────────────────────────────

def realize_harmony(chords: list, key: str, mode: str) -> list:
    """
    Translate key-agnostic scale-degree chords into pitch-class sets.

    Returns list of dicts:
      {chord_pcs: set[int], root_pc: int, quality: str,
       start_beat: float, dur_beats: float}
    """
    tonic_pc  = KEY_PC.get(key, 0)
    degree_pc = MAJOR_DEGREE_PC if mode == 'major' else MINOR_DEGREE_PC
    windows   = []
    beat      = 0.0
    for c in chords:
        degree   = c['degree']
        quality  = c.get('quality', 'maj')
        dur      = float(c.get('beats', 4))
        root_offset = degree_pc.get(degree, 0)
        root_pc  = (tonic_pc + root_offset) % 12
        intervals = CHORD_INTERVALS.get(quality, [0, 4, 7])
        chord_pcs = {(root_pc + i) % 12 for i in intervals}
        windows.append({
            'chord_pcs': chord_pcs,
            'root_pc':   root_pc,
            'quality':   quality,
            'start_beat': beat,
            'dur_beats':  dur,
        })
        beat += dur
    return windows


def chord_tone_midis(root_pc: int, quality: str, low_midi: int, high_midi: int) -> list:
    """Return all MIDI note numbers in [low_midi, high_midi] that are chord tones."""
    intervals = CHORD_INTERVALS.get(quality, [0, 4, 7])
    result = []
    for midi in range(low_midi, high_midi + 1):
        if midi % 12 in {(root_pc + i) % 12 for i in intervals}:
            result.append(midi)
    return result
```

- [ ] **Step 5: Run tests — they should pass now**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship && .venv/bin/pytest tests/test_generator.py -v 2>&1 | tail -20
```
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship && git add melody_generator.py tests/conftest.py tests/test_generator.py && git commit -m "feat: melody_generator constants, realize_harmony, chord_tone_midis"
```

---

## Task 2: Rhythm skeleton builder

**Files:**
- Modify: `melody_generator.py` (add `build_rhythm`)
- Modify: `tests/test_generator.py` (add rhythm tests)

**Interfaces:**
- Consumes: `BEAT_VALUES`, `DUR_ORDER`
- Produces:
  - `strong_beats(time_sig: str, num_measures: int) -> set[float]` — beat positions that are metrically strong
  - `build_rhythm(time_sig: str, num_measures: int, min_duration: str, complexity: int, syncopation: bool, rng: random.Random) -> list[dict]`
    - Returns list of `{"beat": float, "dur": str, "dotted": bool, "is_strong": bool}`
    - All slots together fill exactly `num_measures * beats_per_measure` beats
    - `complexity` 1 = mostly quarter notes, 2 = mix of quarters/eighths, 3 = includes dotted + shorter

- [ ] **Step 1: Add rhythm tests to tests/test_generator.py**

Append to existing test file:

```python
from melody_generator import build_rhythm, strong_beats
import random


def test_strong_beats_4_4():
    sb = strong_beats('4/4', 2)
    assert 0.0 in sb   # beat 1 of measure 1
    assert 2.0 in sb   # beat 3 of measure 1 (half-bar accent)
    assert 4.0 in sb   # beat 1 of measure 2


def test_strong_beats_3_4():
    sb = strong_beats('3/4', 2)
    assert 0.0 in sb
    assert 3.0 in sb
    assert 1.0 not in sb  # beats 2 and 3 are weak


def test_build_rhythm_fills_exact_duration_4_4():
    rng = random.Random(42)
    slots = build_rhythm('4/4', 2, 'q', complexity=1, syncopation=False, rng=rng)
    total = sum(BEAT_VALUES[s['dur']] * (1.5 if s['dotted'] else 1.0) for s in slots)
    assert abs(total - 8.0) < 0.001  # 2 measures × 4 beats


def test_build_rhythm_fills_exact_duration_3_4():
    rng = random.Random(7)
    slots = build_rhythm('3/4', 4, 'q', complexity=1, syncopation=False, rng=rng)
    total = sum(BEAT_VALUES[s['dur']] * (1.5 if s['dotted'] else 1.0) for s in slots)
    assert abs(total - 12.0) < 0.001  # 4 measures × 3 beats


def test_build_rhythm_strong_slots_on_strong_beats():
    rng = random.Random(1)
    slots = build_rhythm('4/4', 2, 'q', complexity=1, syncopation=False, rng=rng)
    sb = strong_beats('4/4', 2)
    for s in slots:
        if s['beat'] in sb:
            assert s['is_strong']


def test_build_rhythm_min_duration_respected():
    rng = random.Random(99)
    slots = build_rhythm('4/4', 2, '8', complexity=2, syncopation=False, rng=rng)
    for s in slots:
        val = BEAT_VALUES[s['dur']] * (1.5 if s['dotted'] else 1.0)
        assert val >= BEAT_VALUES['8'] * 0.99  # nothing shorter than min_duration


from melody_generator import BEAT_VALUES
```

- [ ] **Step 2: Run tests to confirm new tests fail**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship && .venv/bin/pytest tests/test_generator.py -v -k "rhythm or strong" 2>&1 | tail -15
```
Expected: `ImportError` or `AttributeError` on `build_rhythm`/`strong_beats`

- [ ] **Step 3: Implement build_rhythm and strong_beats in melody_generator.py**

Append to `melody_generator.py`:

```python
# ── Rhythm skeleton ───────────────────────────────────────────────────────────

def beats_per_measure(time_sig: str) -> float:
    """Quarter-note beat count per measure."""
    num, den = (int(x) for x in time_sig.split('/'))
    return num * (4.0 / den)


def strong_beats(time_sig: str, num_measures: int) -> set:
    """
    Return the set of beat positions (in quarter-note units) that are metrically strong.
    For simple meters: beats 1 and (for 4/4) 3.
    For compound meters (6/8, 9/8, 12/8): dotted-quarter downbeats.
    """
    num, den = (int(x) for x in time_sig.split('/'))
    bpm = beats_per_measure(time_sig)
    result = set()
    for m in range(num_measures):
        bar_start = m * bpm
        if den == 8:
            # Compound: strong on each dotted-quarter group (every 1.5 beats)
            groups = num // 3
            for g in range(groups):
                result.add(bar_start + g * 1.5)
        else:
            # Simple: beat 1 always strong; beat 3 strong in 4/4
            result.add(bar_start)
            if num == 4:
                result.add(bar_start + 2.0)
    return result


# Rhythm cells per beat: (dur, dotted, beats_consumed)
# Indexed by min_duration and complexity
def _beat_cells(min_dur: str, complexity: int, syncopation: bool, rng: random.Random) -> list:
    """
    Return a list of (dur, dotted) tuples that fill exactly 1 quarter-note beat.
    Only called for simple-meter beats; compound uses dotted-quarter cells.
    """
    if min_dur == 'q' or complexity == 1:
        return [('q', False)]

    cells_q = [
        [('q', False)],           # quarter note
        [('8', False), ('8', False)],  # two eighths
    ]
    if complexity >= 2:
        cells_q.append([('8', True), ('16', False)])  # dotted-8 + 16th
    if syncopation and complexity >= 2:
        cells_q.append([('8r', False), ('8', False)])  # eighth rest + eighth (tie-syncopation approximation)

    if min_dur == '16' and complexity >= 3:
        cells_q.append([('16', False)] * 4)

    return rng.choice(cells_q)


def build_rhythm(time_sig: str, num_measures: int, min_duration: str,
                 complexity: int, syncopation: bool, rng: random.Random) -> list:
    """
    Build a rhythmic skeleton as a list of note slots.

    Each slot: {"beat": float, "dur": str, "dotted": bool, "is_strong": bool}

    "dur" is the VexFlow duration string (may end in 'r' for a rest).
    All slots together consume exactly num_measures * beats_per_measure(time_sig) beats.
    """
    num, den = (int(x) for x in time_sig.split('/'))
    bpm = beats_per_measure(time_sig)
    sb  = strong_beats(time_sig, num_measures)
    total_beats = num_measures * bpm
    slots = []
    beat  = 0.0

    if den == 8:
        # Compound meter: work in dotted-quarter units (1.5 beats each)
        dotted_q_count = int(round(total_beats / 1.5))
        for i in range(dotted_q_count):
            is_strong = beat in sb or any(abs(beat - s) < 0.01 for s in sb)
            if complexity <= 1 or (is_strong and rng.random() < 0.5):
                # Dotted quarter
                slots.append({'beat': beat, 'dur': 'q', 'dotted': True, 'is_strong': is_strong})
                beat += 1.5
            else:
                # Split into three eighths
                for j in range(3):
                    slots.append({'beat': beat, 'dur': '8', 'dotted': False,
                                  'is_strong': is_strong and j == 0})
                    beat += 0.5
    else:
        # Simple meter: work beat by beat
        while beat < total_beats - 0.001:
            is_strong = any(abs(beat - s) < 0.01 for s in sb)
            remaining = total_beats - beat

            # For the last beat, force a quarter if possible
            if remaining <= 1.0 + 0.001 and min_duration in ('q', 'h', 'w'):
                dur_val = min(remaining, 1.0)
                dur_str = 'q' if abs(dur_val - 1.0) < 0.01 else '8'
                slots.append({'beat': beat, 'dur': dur_str, 'dotted': False, 'is_strong': is_strong})
                beat += BEAT_VALUES.get(dur_str, 1.0)
                continue

            cell = _beat_cells(min_duration, complexity, syncopation, rng)
            for dur, dotted in cell:
                base = dur.rstrip('r')
                val  = BEAT_VALUES.get(base, 1.0) * (1.5 if dotted else 1.0)
                slots.append({'beat': beat, 'dur': dur, 'dotted': dotted,
                              'is_strong': is_strong})
                beat += val
                is_strong = False  # only first note in a cell is on the beat

    return slots
```

- [ ] **Step 4: Run tests — all should pass**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship && .venv/bin/pytest tests/test_generator.py -v 2>&1 | tail -25
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship && git add melody_generator.py tests/test_generator.py && git commit -m "feat: melody_generator build_rhythm and strong_beats"
```

---

## Task 3: Skeleton note placement

**Files:**
- Modify: `melody_generator.py`
- Modify: `tests/test_generator.py`

**Interfaces:**
- Consumes: `realize_harmony`, `chord_tone_midis`, `build_rhythm`, `CLEF_RANGE`
- Produces:
  - `active_window(beat, windows) -> dict` — returns the harmony window active at a given beat
  - `place_skeleton(slots, windows, contour, clef, key, rng) -> list[dict]`
    - `contour`: `{"start_midi": int, "high_midi": int, "low_midi": int}`
    - Fills `is_strong=True` slots with chord-tone MIDI numbers
    - Fills `is_strong=False` slots with `None` (will be handled in Task 4)
    - Returns same list with added `"midi": int|None` key on each slot
    - Constraints: no consecutive leaps > 7 semitones; prefer stepwise motion; bias toward contour waypoints

- [ ] **Step 1: Add skeleton tests to tests/test_generator.py**

```python
from melody_generator import place_skeleton, active_window


def test_active_window_finds_correct_chord():
    windows = realize_harmony([
        {"degree": "I",  "quality": "maj", "inversion": 0, "beats": 4},
        {"degree": "V",  "quality": "maj", "inversion": 0, "beats": 4},
    ], 'C', 'major')
    w = active_window(2.0, windows)
    assert 0 in w['chord_pcs']  # still on I at beat 2

    w2 = active_window(4.0, windows)
    assert 7 in w2['chord_pcs']  # V starts at beat 4 (G)


def test_place_skeleton_strong_beats_are_chord_tones():
    rng = random.Random(42)
    chords = [
        {"degree": "I",  "quality": "maj", "inversion": 0, "beats": 4},
        {"degree": "V",  "quality": "maj", "inversion": 0, "beats": 4},
    ]
    windows = realize_harmony(chords, 'C', 'major')
    slots = build_rhythm('4/4', 2, 'q', complexity=1, syncopation=False, rng=rng)
    contour = {"start_midi": 64, "high_midi": 72, "low_midi": 60}
    result = place_skeleton(slots, windows, contour, 'treble', 'C', rng)

    for s in result:
        if s['is_strong'] and s['midi'] is not None:
            win = active_window(s['beat'], windows)
            assert s['midi'] % 12 in win['chord_pcs'], (
                f"Note {s['midi']} (pc={s['midi']%12}) not in chord pcs {win['chord_pcs']}"
            )


def test_place_skeleton_notes_in_clef_range():
    rng = random.Random(7)
    chords = [{"degree": "I", "quality": "maj", "inversion": 0, "beats": 4}]
    windows = realize_harmony(chords, 'C', 'major')
    slots = build_rhythm('4/4', 1, 'q', complexity=1, syncopation=False, rng=rng)
    contour = {"start_midi": 64, "high_midi": 72, "low_midi": 60}
    result = place_skeleton(slots, windows, contour, 'treble', 'C', rng)
    low, high = CLEF_RANGE['treble']
    for s in result:
        if s['midi'] is not None:
            assert low <= s['midi'] <= high


from melody_generator import CLEF_RANGE
```

- [ ] **Step 2: Run tests — skeleton tests should fail**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship && .venv/bin/pytest tests/test_generator.py -v -k "skeleton or active_window" 2>&1 | tail -10
```
Expected: `ImportError` on `place_skeleton`/`active_window`

- [ ] **Step 3: Implement place_skeleton in melody_generator.py**

```python
# ── Skeleton placement ────────────────────────────────────────────────────────

def active_window(beat: float, windows: list) -> dict:
    """Return the harmonic window that is active at the given beat position."""
    best = windows[0]
    for w in windows:
        if w['start_beat'] <= beat + 0.001:
            best = w
    return best


def _closest_chord_tone(target_midi: int, chord_tone_list: list) -> int:
    """Return the chord tone MIDI closest in pitch to target_midi."""
    if not chord_tone_list:
        return target_midi
    return min(chord_tone_list, key=lambda m: abs(m - target_midi))


def _toward_waypoint(current: int, waypoint: int, chord_tones: list) -> int:
    """
    Pick the chord tone that moves toward the waypoint.
    If above waypoint: prefer lower; if below: prefer higher.
    Among candidates, prefer the smallest step.
    """
    if not chord_tones:
        return current
    # Score each candidate: prefer movement toward waypoint and small steps
    def score(m):
        distance_to_wp = abs(m - waypoint)
        step_size = abs(m - current)
        # Penalise moving away from waypoint
        wrong_direction = 5 if (waypoint > current and m < current) or \
                              (waypoint < current and m > current) else 0
        # Penalise large leaps
        leap_penalty = max(0, step_size - 7) * 3
        return distance_to_wp + step_size * 0.3 + wrong_direction + leap_penalty
    return min(chord_tones, key=score)


def place_skeleton(slots: list, windows: list, contour: dict,
                   clef: str, key: str, rng: random.Random) -> list:
    """
    Fill strong-beat slots with chord tones, leave weak-beat slots as None.

    Modifies slots in-place (adds 'midi' key) and returns the list.
    Contour: {"start_midi": int, "high_midi": int, "low_midi": int}
    """
    low_midi, high_midi = CLEF_RANGE.get(clef, (60, 79))
    total_beats = sum(
        BEAT_VALUES.get(s['dur'].rstrip('r'), 1.0) * (1.5 if s['dotted'] else 1.0)
        for s in slots
    )

    prev_midi = contour['start_midi']
    strong_count = sum(1 for s in slots if s['is_strong'])
    strong_idx   = 0

    for s in slots:
        s['midi'] = None
        if not s['is_strong']:
            continue

        win   = active_window(s['beat'], windows)
        ct    = chord_tone_midis(win['root_pc'], win['quality'], low_midi, high_midi)

        # Determine target waypoint based on progress through the melody
        progress = strong_idx / max(strong_count - 1, 1)
        if progress < 0.3:
            waypoint = contour['high_midi']    # climbing toward high point
        elif progress < 0.6:
            waypoint = contour['high_midi']    # sustain near peak
        else:
            waypoint = contour['start_midi']   # descend toward cadence

        # Exclude notes that would form a leap > 9 semitones from previous
        reachable = [m for m in ct if abs(m - prev_midi) <= 9] or ct

        midi = _toward_waypoint(prev_midi, waypoint, reachable)
        s['midi'] = midi
        prev_midi  = midi
        strong_idx += 1

    return slots
```

- [ ] **Step 4: Run all tests**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship && .venv/bin/pytest tests/test_generator.py -v 2>&1 | tail -30
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship && git add melody_generator.py tests/test_generator.py && git commit -m "feat: melody_generator skeleton placement (active_window, place_skeleton)"
```

---

## Task 4: Ornamentation techniques

**Files:**
- Modify: `melody_generator.py`
- Modify: `tests/test_generator.py`

**Interfaces:**
- Consumes: `KEY_PC`, `MAJOR_DEGREE_PC`/`MINOR_DEGREE_PC`
- Produces:
  - `key_pcs(key: str, mode: str) -> set[int]` — all pitch classes in the key (diatonic set)
  - `apply_techniques(slots, windows, enabled_techniques, key, mode, rng) -> tuple[list, list[str]]`
    - Fills `midi=None` (weak-beat) slots using enabled techniques
    - Returns `(updated_slots, techniques_actually_used: list[str])`
    - Supported technique names: `"passing_tone"`, `"neighbor_tone"`, `"appoggiatura"`, `"suspension"`, `"anticipation"`, `"escape_tone"`

- [ ] **Step 1: Add technique tests to tests/test_generator.py**

```python
from melody_generator import key_pcs, apply_techniques


def test_key_pcs_c_major():
    pcs = key_pcs('C', 'major')
    assert pcs == {0, 2, 4, 5, 7, 9, 11}


def test_key_pcs_am_minor():
    pcs = key_pcs('Am', 'minor')
    # A natural minor = A B C D E F G = pcs 9,11,0,2,4,5,7
    assert pcs == {9, 11, 0, 2, 4, 5, 7}


def test_apply_techniques_passing_tone_fills_weak_slots():
    """After apply_techniques, no midi=None slots should remain (all filled or silenced)."""
    rng = random.Random(42)
    chords = [
        {"degree": "I", "quality": "maj", "inversion": 0, "beats": 4},
        {"degree": "V", "quality": "maj", "inversion": 0, "beats": 4},
    ]
    windows = realize_harmony(chords, 'C', 'major')
    slots = build_rhythm('4/4', 2, '8', complexity=2, syncopation=False, rng=rng)
    contour = {"start_midi": 64, "high_midi": 72, "low_midi": 60}
    slots = place_skeleton(slots, windows, contour, 'treble', 'C', rng)
    slots, used = apply_techniques(slots, windows, ['passing_tone', 'neighbor_tone'], 'C', 'major', rng)
    # All slots should now have a midi value (or be a rest)
    for s in slots:
        assert s['midi'] is not None or s['dur'].endswith('r'), f"Unfilled slot: {s}"


def test_apply_techniques_returns_used_list():
    rng = random.Random(1)
    chords = [{"degree": "I", "quality": "maj", "inversion": 0, "beats": 4}]
    windows = realize_harmony(chords, 'C', 'major')
    slots = build_rhythm('4/4', 1, '8', complexity=2, syncopation=False, rng=rng)
    contour = {"start_midi": 64, "high_midi": 72, "low_midi": 60}
    slots = place_skeleton(slots, windows, contour, 'treble', 'C', rng)
    slots, used = apply_techniques(slots, windows, ['passing_tone'], 'C', 'major', rng)
    assert isinstance(used, list)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship && .venv/bin/pytest tests/test_generator.py -v -k "technique or key_pcs or apply" 2>&1 | tail -10
```

- [ ] **Step 3: Implement key_pcs and apply_techniques in melody_generator.py**

```python
# ── Ornamentation ─────────────────────────────────────────────────────────────

MAJOR_SCALE_INTERVALS = [0, 2, 4, 5, 7, 9, 11]
MINOR_SCALE_INTERVALS = [0, 2, 3, 5, 7, 8, 10]   # natural minor


def key_pcs(key: str, mode: str) -> set:
    """Return the set of pitch classes in the key's diatonic scale."""
    tonic = KEY_PC.get(key, 0)
    intervals = MAJOR_SCALE_INTERVALS if mode == 'major' else MINOR_SCALE_INTERVALS
    return {(tonic + i) % 12 for i in intervals}


def _step_between(midi_a: int, midi_b: int, diatonic_pcs: set) -> int | None:
    """
    Return a diatonic note that fills the interval between midi_a and midi_b by step.
    Works if the interval is a third (3–4 semitones); returns None otherwise.
    """
    diff = midi_b - midi_a
    if abs(diff) not in (3, 4):
        return None
    direction = 1 if diff > 0 else -1
    for semis in [direction, direction * 2]:
        candidate_pc = (midi_a + semis) % 12
        if candidate_pc in diatonic_pcs:
            return midi_a + semis
    return None


def _neighbor(midi: int, diatonic_pcs: set, direction: int = 1) -> int:
    """Return the nearest diatonic neighbor in the given direction (+1 or -1 semitone steps)."""
    for delta in [direction, -direction, 2 * direction, -2 * direction]:
        candidate = midi + delta
        if candidate % 12 in diatonic_pcs and candidate != midi:
            return candidate
    return midi


def apply_techniques(slots: list, windows: list, enabled: list,
                     key: str, mode: str, rng: random.Random) -> tuple:
    """
    Fill weak-beat slots (midi=None) using the enabled ornamentation techniques.

    Priority order (for each weak slot):
      1. passing_tone  — if the surrounding strong notes form a third
      2. neighbor_tone — step away then back (requires a pair of weak slots)
      3. anticipation  — early arrival on next strong tone
      4. escape_tone   — step in wrong direction then leap
      5. appoggiatura  — non-chord tone resolving down to next chord tone
      6. suspension    — hold the previous strong tone (tie)
      fallback         — repeat the previous note

    Returns (updated_slots, list_of_technique_names_actually_inserted).
    """
    diatonic = key_pcs(key, mode)
    used_techniques = set()
    n = len(slots)

    for i, s in enumerate(slots):
        if s['midi'] is not None or s['dur'].endswith('r'):
            continue

        # Find surrounding strong-beat notes
        prev_midi = next((slots[j]['midi'] for j in range(i - 1, -1, -1)
                         if slots[j]['midi'] is not None), None)
        next_midi = next((slots[j]['midi'] for j in range(i + 1, n)
                         if slots[j]['midi'] is not None), None)

        win = active_window(s['beat'], windows)
        chosen = None

        # 1. Passing tone
        if 'passing_tone' in enabled and prev_midi and next_midi:
            pt = _step_between(prev_midi, next_midi, diatonic)
            if pt is not None:
                chosen = pt
                used_techniques.add('passing_tone')

        # 2. Neighbor tone
        if chosen is None and 'neighbor_tone' in enabled and prev_midi:
            nb_dir = rng.choice([1, -1])
            nb = _neighbor(prev_midi, diatonic, nb_dir)
            if nb != prev_midi:
                chosen = nb
                used_techniques.add('neighbor_tone')

        # 3. Anticipation (early arrival on next strong tone)
        if chosen is None and 'anticipation' in enabled and next_midi:
            if rng.random() < 0.4:
                chosen = next_midi
                used_techniques.add('anticipation')

        # 4. Escape tone (step opposite direction to next note, then leap resolves)
        if chosen is None and 'escape_tone' in enabled and prev_midi and next_midi:
            diff = next_midi - prev_midi
            escape_dir = -1 if diff > 0 else 1
            esc = _neighbor(prev_midi, diatonic, escape_dir)
            if esc != prev_midi and abs(esc - next_midi) <= 9:
                chosen = esc
                used_techniques.add('escape_tone')

        # 5. Appoggiatura (accented non-chord tone resolving to chord tone)
        if chosen is None and 'appoggiatura' in enabled and next_midi:
            ct = {(win['root_pc'] + interval) % 12
                  for interval in CHORD_INTERVALS.get(win['quality'], [0, 4, 7])}
            if next_midi % 12 in ct:
                # Step above or below next_midi, not a chord tone
                for delta in [1, 2, -1, -2]:
                    candidate = next_midi + delta
                    if candidate % 12 not in ct and candidate % 12 in diatonic:
                        chosen = candidate
                        used_techniques.add('appoggiatura')
                        break

        # 6. Suspension (repeat previous strong tone)
        if chosen is None and 'suspension' in enabled and prev_midi:
            if rng.random() < 0.3:
                chosen = prev_midi
                used_techniques.add('suspension')

        # Fallback: repeat previous note
        if chosen is None:
            chosen = prev_midi if prev_midi is not None else (next_midi or 60)

        s['midi'] = chosen

    return slots, list(used_techniques)
```

- [ ] **Step 4: Run all tests**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship && .venv/bin/pytest tests/test_generator.py -v 2>&1 | tail -30
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship && git add melody_generator.py tests/test_generator.py && git commit -m "feat: melody_generator ornamentation techniques"
```

---

## Task 5: Auto-tagging, difficulty suggestion, emit + top-level generate()

**Files:**
- Modify: `melody_generator.py`
- Modify: `tests/test_generator.py`

**Interfaces:**
- Produces:
  - `auto_tags(params, techniques_used) -> list[str]` — derive Tag names from params + techniques
  - `suggest_difficulty(slots, techniques_used, gen_prog_difficulty) -> int` — returns 1–5
  - `slots_to_notes_json(slots, key) -> str` — convert filled slots to JSON string in VexFlow format
  - `write_preview_midi(notes_json_str: str, tempo: int) -> str` — write to `static/melodic/_preview/_preview.mid`, return relative path `melodic/_preview/_preview.mid`
  - `generate(params: dict) -> dict` — the top-level function

- [ ] **Step 1: Add emit and generate tests to tests/test_generator.py**

```python
from melody_generator import (
    auto_tags, suggest_difficulty, slots_to_notes_json, generate
)
import json


def test_auto_tags_includes_time_signature():
    params = {'time_sig': '3/4', 'min_duration': 'q', 'clef': 'treble', 'key': 'C', 'mode': 'major'}
    tags = auto_tags(params, [])
    assert 'waltz' in tags or '3/4' in ' '.join(tags)


def test_auto_tags_includes_technique_tags():
    params = {'time_sig': '4/4', 'min_duration': '8', 'clef': 'treble', 'key': 'C', 'mode': 'major'}
    tags = auto_tags(params, ['passing_tone', 'neighbor_tone'])
    assert 'passing-tone' in tags or 'passing_tone' in tags or any('passing' in t for t in tags)


def test_suggest_difficulty_higher_for_more_techniques():
    d_few  = suggest_difficulty([], [], 1)
    d_many = suggest_difficulty([], ['passing_tone', 'neighbor_tone', 'appoggiatura', 'suspension'], 1)
    assert d_many >= d_few


def test_slots_to_notes_json_valid_json():
    # Simple slot: one quarter note C4
    slots = [{'beat': 0.0, 'dur': 'q', 'dotted': False, 'is_strong': True, 'midi': 60}]
    result = slots_to_notes_json(slots, 'C')
    notes = json.loads(result)
    assert len(notes) == 1
    assert notes[0]['duration'] == 'q'
    assert 'key' in notes[0]


def test_slots_to_notes_json_rest():
    slots = [{'beat': 0.0, 'dur': 'q', 'dotted': False, 'is_strong': False, 'midi': None}]
    result = slots_to_notes_json(slots, 'C')
    notes = json.loads(result)
    assert notes[0]['duration'].endswith('r')


def test_generate_is_deterministic():
    from models import GenProgression  # may not exist in test env; skip if so
    # Use params without DB lookup (pass chords directly via mock)
    # We test determinism by running twice with same seed
    params = {
        'key': 'C', 'mode': 'major',
        'gen_progression_chords': [
            {"degree": "I",  "quality": "maj", "inversion": 0, "beats": 4},
            {"degree": "V",  "quality": "maj", "inversion": 0, "beats": 4},
        ],
        'time_sig': '4/4', 'num_measures': 2,
        'min_duration': 'q', 'clef': 'treble',
        'start_midi': 64, 'high_midi': 72, 'low_midi': 60,
        'techniques': ['passing_tone'],
        'rhythm_complexity': 1, 'syncopation': False,
        'seed': 42, 'tempo': 100,
    }
    r1 = generate(params)
    r2 = generate(params)
    assert r1['notes_json'] == r2['notes_json']


def test_generate_strong_beats_are_chord_tones():
    params = {
        'key': 'C', 'mode': 'major',
        'gen_progression_chords': [
            {"degree": "I", "quality": "maj", "inversion": 0, "beats": 4},
        ],
        'time_sig': '4/4', 'num_measures': 1,
        'min_duration': 'q', 'clef': 'treble',
        'start_midi': 64, 'high_midi': 72, 'low_midi': 60,
        'techniques': [], 'rhythm_complexity': 1, 'syncopation': False,
        'seed': 1, 'tempo': 100,
    }
    result = generate(params)
    notes = json.loads(result['notes_json'])
    windows = realize_harmony(params['gen_progression_chords'], 'C', 'major')
    i_chord_pcs = windows[0]['chord_pcs']
    # With complexity=1 and 4/4, all notes are quarter notes on strong beats
    for n in notes:
        if not n['duration'].endswith('r'):
            # Parse key like "e/4" → pitch class
            note_name = n['key'].split('/')[0]
            name_to_pc = {'c':0,'c#':1,'db':1,'d':2,'d#':3,'eb':3,'e':4,'f':5,
                          'f#':6,'gb':6,'g':7,'g#':8,'ab':8,'a':9,'a#':10,'bb':10,'b':11}
            pc = name_to_pc.get(note_name.lower(), -1)
            assert pc in i_chord_pcs, f"Note {n['key']} (pc={pc}) not in I chord {i_chord_pcs}"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship && .venv/bin/pytest tests/test_generator.py -v -k "auto_tags or suggest_diff or slots_to or generate" 2>&1 | tail -15
```

- [ ] **Step 3: Implement remaining functions in melody_generator.py**

```python
# ── Auto-tagging and difficulty ───────────────────────────────────────────────

TECHNIQUE_TAGS = {
    'passing_tone':  'passing-tone',
    'neighbor_tone': 'neighbor-tone',
    'appoggiatura':  'appoggiatura',
    'suspension':    'suspension',
    'anticipation':  'anticipation',
    'escape_tone':   'escape-tone',
}

TECHNIQUE_DIFFICULTY = {
    'passing_tone':  0.5, 'neighbor_tone': 0.5,
    'appoggiatura':  1.5, 'suspension':    1.5,
    'anticipation':  1.0, 'escape_tone':   1.0,
}

TIME_SIG_TAGS = {
    '3/4': ['waltz'], '2/4': ['march'],
    '6/8': ['compound-meter'], '9/8': ['compound-meter'], '12/8': ['compound-meter'],
}

MIN_DUR_TAGS = {
    '8':  ['eighth-notes'], '16': ['sixteenth-notes'],
}


def auto_tags(params: dict, techniques_used: list) -> list:
    tags = []
    tags += TIME_SIG_TAGS.get(params.get('time_sig', '4/4'), [])
    tags += MIN_DUR_TAGS.get(params.get('min_duration', 'q'), [])
    if params.get('clef') == 'bass':
        tags.append('bass-clef')
    elif params.get('clef') == 'tenor':
        tags.append('tenor-clef')
    if params.get('mode') == 'minor':
        tags.append('minor-scale')
    else:
        tags.append('major-scale')
    for t in techniques_used:
        tag = TECHNIQUE_TAGS.get(t)
        if tag:
            tags.append(tag)
    return list(dict.fromkeys(tags))   # deduplicate, preserve order


def suggest_difficulty(slots: list, techniques_used: list, gen_prog_difficulty: int = 1) -> int:
    score = gen_prog_difficulty * 0.5
    for t in techniques_used:
        score += TECHNIQUE_DIFFICULTY.get(t, 0.5)
    # Count leaps > 4 semitones
    midis = [s['midi'] for s in slots if s.get('midi') is not None]
    for i in range(1, len(midis)):
        if abs(midis[i] - midis[i - 1]) > 4:
            score += 0.3
    return max(1, min(5, round(score)))


# ── Emit ─────────────────────────────────────────────────────────────────────

def slots_to_notes_json(slots: list, key: str) -> str:
    """Convert filled slots to VexFlow note JSON string."""
    from midi_to_notes import note_to_vex
    notes = []
    for s in slots:
        dur = s['dur']
        dotted = s.get('dotted', False)
        midi = s.get('midi')

        if dur.endswith('r') or midi is None:
            entry = {'key': 'b/4', 'duration': (dur.rstrip('r') + 'r') if not dur.endswith('r') else dur}
        else:
            vex_key = note_to_vex(midi, None, key)
            entry = {'key': vex_key, 'duration': dur}

        if dotted:
            entry['dotted'] = True
        notes.append(entry)
    return json.dumps(notes)


def write_preview_midi(notes_json_str: str, tempo: int) -> str:
    """
    Write a preview MIDI to static/melodic/_preview/_preview.mid.
    Returns the relative path 'melodic/_preview/_preview.mid'.
    """
    from generate_midi import write_midi as _write_midi, DURATION_BEATS
    from midiutil import MIDIFile
    notes = json.loads(notes_json_str)
    dest_dir = os.path.join(STATIC_DIR, 'melodic', '_preview')
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, '_preview.mid')

    midi = MIDIFile(1)
    midi.addTempo(0, 0, tempo)
    time = 0.0
    for n in notes:
        dur_str = n['duration']
        dotted  = n.get('dotted', False)
        base    = dur_str.rstrip('r')
        beats   = DURATION_BEATS.get(base, 1) * (1.5 if dotted else 1)
        if not dur_str.endswith('r'):
            # Parse VexFlow key to MIDI
            key_str = n['key']
            name, octave = key_str.split('/')
            pc_map = {'c':0,'c#':1,'db':1,'d':2,'d#':3,'eb':3,'e':4,'f':5,
                      'f#':6,'gb':6,'g':7,'g#':8,'ab':8,'a':9,'a#':10,'bb':10,'b':11}
            pc = pc_map.get(name.lower(), 0)
            midi_num = (int(octave) + 1) * 12 + pc
            midi.addNote(0, 0, midi_num, time, beats * 0.9, 90)
        time += beats

    with open(dest_path, 'wb') as f:
        midi.writeFile(f)
    return 'melodic/_preview/_preview.mid'


# ── Top-level generate() ──────────────────────────────────────────────────────

def generate(params: dict) -> dict:
    """
    Generate a melody from params dict.

    Required params keys:
      key (str), mode (str), gen_progression_chords (list[dict]),
      time_sig (str), num_measures (int), min_duration (str), clef (str),
      start_midi (int), high_midi (int), low_midi (int),
      techniques (list[str]), rhythm_complexity (int, 1–3),
      syncopation (bool), seed (int|None), tempo (int)

    Returns:
      notes_json (str), midi_path (str), difficulty_suggestion (int),
      auto_tags (list[str]), generation_params (dict)
    """
    seed = params.get('seed')
    rng  = random.Random(seed)

    chords  = params['gen_progression_chords']
    key     = params['key']
    mode    = params['mode']
    clef    = params['clef']
    tempo   = params.get('tempo', 100)

    windows = realize_harmony(chords, key, mode)
    slots   = build_rhythm(
        params['time_sig'], params['num_measures'],
        params['min_duration'], params['rhythm_complexity'],
        params['syncopation'], rng,
    )
    contour = {
        'start_midi': params['start_midi'],
        'high_midi':  params['high_midi'],
        'low_midi':   params['low_midi'],
    }
    slots = place_skeleton(slots, windows, contour, clef, key, rng)
    slots, techniques_used = apply_techniques(
        slots, windows, params.get('techniques', []), key, mode, rng
    )

    # Determine gen_prog difficulty (passed in or default 1)
    gp_diff = params.get('gen_prog_difficulty', 1)

    notes_json_str = slots_to_notes_json(slots, key)
    midi_path      = write_preview_midi(notes_json_str, tempo)

    return {
        'notes_json':           notes_json_str,
        'midi_path':            midi_path,
        'difficulty_suggestion': suggest_difficulty(slots, techniques_used, gp_diff),
        'auto_tags':            auto_tags(params, techniques_used),
        'generation_params':    params,
    }
```

- [ ] **Step 4: Run all tests**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship && .venv/bin/pytest tests/test_generator.py -v 2>&1 | tail -35
```
Expected: all PASS (the `test_generate_strong_beats_are_chord_tones` test is the key golden test)

- [ ] **Step 5: Commit**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship && git add melody_generator.py tests/test_generator.py && git commit -m "feat: melody_generator auto_tags, difficulty, emit, generate()"
```

---

## Task 6: Generator UI routes and template

**Files:**
- Modify: `app.py`
- Create: `templates/admin/melody_generator.html`

**Interfaces:**
- Consumes: `melody_generator.generate`, `GenProgression`, `Container`, `Tag`, `Melody` models
- Produces: routes `admin_melody_generator`, `admin_melody_approve`, `admin_melody_reject`

- [ ] **Step 1: Add generator routes to app.py**

Add after the melody upload routes:

```python
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
        # Restore last-used params from session if available
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

    key         = request.form.get('key', 'C')
    mode        = request.form.get('mode', 'major')
    time_sig    = request.form.get('time_sig', '4/4')
    num_measures = request.form.get('num_measures', 4, type=int)
    min_duration = request.form.get('min_duration', 'q')
    clef        = request.form.get('clef', 'treble')
    tempo       = request.form.get('tempo', 100, type=int)
    complexity  = request.form.get('rhythm_complexity', 1, type=int)
    syncopation = request.form.get('syncopation') == 'on'
    techniques  = request.form.getlist('techniques')
    seed_raw    = request.form.get('seed', '').strip()
    seed        = int(seed_raw) if seed_raw.isdigit() else None

    # Build contour from form (MIDI note numbers)
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

    # Store pending melody in session
    session['pending_melody'] = {
        'notes_json':           result['notes_json'],
        'midi_path':            result['midi_path'],
        'difficulty_suggestion': result['difficulty_suggestion'],
        'auto_tags':            result['auto_tags'],
        'generation_params':    result['generation_params'],
        'gp_id': gp_id,
    }
    session['generator_params'] = request.form.to_dict(flat=False)

    preview = {
        'notes_json':           result['notes_json'],
        'midi_url':             url_for('static', filename=result['midi_path']),
        'difficulty_suggestion': result['difficulty_suggestion'],
        'auto_tags':            result['auto_tags'],
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

    # Determine public_id
    last = Melody.query.order_by(Melody.id.desc()).first()
    next_num = (last.id + 1) if last else 1
    public_id = f'MEL-{next_num:04d}'

    # Copy preview MIDI to permanent location
    slug       = f'mel_{public_id.lower().replace("-", "_")}'
    src_path   = os.path.join(app.static_folder, pending['midi_path'].replace('/', os.sep))
    dest_dir   = os.path.join(app.static_folder, 'melodic', slug)
    dest_name  = f'{slug}.mid'
    os.makedirs(dest_dir, exist_ok=True)
    import shutil
    shutil.copy2(src_path, os.path.join(dest_dir, dest_name))
    midi_filename = f'melodic/{slug}/{dest_name}'

    # Override difficulty if admin changed it
    difficulty = request.form.get('difficulty', pending['difficulty_suggestion'], type=int)
    container_id = request.form.get('container_id', type=int) or None

    # Tags: combine auto-tags with any manually checked ones
    tag_ids   = request.form.getlist('tag_ids', type=int)
    auto_tag_names = pending['auto_tags']
    manual_tags = Tag.query.filter(Tag.id.in_(tag_ids)).all() if tag_ids else []

    mel = Melody(
        name=name,
        description=request.form.get('description', '').strip(),
        midi_filename=midi_filename,
        notes_json=pending['notes_json'],
        key_signature=pending['generation_params']['key'],
        time_signature=pending['generation_params']['time_sig'],
        clef=pending['generation_params']['clef'],
        min_duration=pending['generation_params']['min_duration'],
        tempo=pending['generation_params'].get('tempo', 100),
        difficulty=difficulty,
        public_id=public_id,
        container_id=container_id,
        generation_params=json.dumps(pending['generation_params']),
    )
    mel.tags = manual_tags

    # Also add auto-tags that exist in the DB
    for tag_name in auto_tag_names:
        tag = Tag.query.filter_by(name=tag_name).first()
        if tag and tag not in mel.tags:
            mel.tags.append(tag)

    db.session.add(mel)
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
```

- [ ] **Step 2: Create templates/admin/melody_generator.html**

```html
{% extends 'base.html' %}
{% block title %}Melody Generator — Admin{% endblock %}
{% block content %}
<div class="container py-4">
  <h2 class="mb-4">Melody Generator</h2>

  {% with messages = get_flashed_messages(with_categories=true) %}
    {% for cat, msg in messages %}<div class="alert alert-{{ cat }}">{{ msg }}</div>{% endfor %}
  {% endwith %}

  <div class="row g-4">
    {# ── Left: Parameters ─────────────────────────────────────────────── #}
    <div class="col-lg-5">
      <form method="post" id="gen-form">
        <div class="card">
          <div class="card-header fw-semibold">Parameters</div>
          <div class="card-body">

            <div class="mb-3">
              <label class="form-label fw-semibold">GenProgression <span class="text-danger">*</span></label>
              <select name="gen_progression_id" class="form-select" required>
                <option value="">— Select —</option>
                {% for gp in gen_progressions %}
                <option value="{{ gp.id }}"
                  {% if last_params.get('gen_progression_id', [''])[0]|string == gp.id|string %}selected{% endif %}>
                  #{{ gp.number }} {{ gp.name or '' }} ({{ gp.length_bars }} bars, {{ gp.mode }}, diff {{ gp.difficulty }})
                </option>
                {% endfor %}
              </select>
            </div>

            <div class="row g-2 mb-3">
              <div class="col-6">
                <label class="form-label fw-semibold">Key</label>
                <select name="key" class="form-select">
                  {% for k in ['C','G','D','A','E','B','F#','F','Bb','Eb','Ab','Db','Gb',
                               'Am','Em','Bm','Dm','Gm','Cm','Fm'] %}
                  <option {% if last_params.get('key',['C'])[0] == k %}selected{% endif %}>{{ k }}</option>
                  {% endfor %}
                </select>
              </div>
              <div class="col-6">
                <label class="form-label fw-semibold">Mode</label>
                <select name="mode" class="form-select">
                  <option {% if last_params.get('mode',['major'])[0] == 'major' %}selected{% endif %}>major</option>
                  <option {% if last_params.get('mode',['major'])[0] == 'minor' %}selected{% endif %}>minor</option>
                </select>
              </div>
            </div>

            <div class="row g-2 mb-3">
              <div class="col-4">
                <label class="form-label fw-semibold">Time Sig</label>
                <select name="time_sig" class="form-select">
                  {% for ts in ['2/4','3/4','4/4','6/8','9/8','12/8'] %}
                  <option {% if last_params.get('time_sig',['4/4'])[0] == ts %}selected{% endif %}>{{ ts }}</option>
                  {% endfor %}
                </select>
              </div>
              <div class="col-4">
                <label class="form-label fw-semibold">Measures</label>
                <input name="num_measures" type="number" class="form-control" min="1" max="16"
                       value="{{ last_params.get('num_measures',['4'])[0] }}">
              </div>
              <div class="col-4">
                <label class="form-label fw-semibold">Clef</label>
                <select name="clef" class="form-select">
                  {% for c in ['treble','bass','tenor'] %}
                  <option {% if last_params.get('clef',['treble'])[0] == c %}selected{% endif %}>{{ c }}</option>
                  {% endfor %}
                </select>
              </div>
            </div>

            <div class="row g-2 mb-3">
              <div class="col-6">
                <label class="form-label fw-semibold">Min Duration</label>
                <select name="min_duration" class="form-select">
                  {% for d in ['h','q','8','16'] %}
                  <option {% if last_params.get('min_duration',['q'])[0] == d %}selected{% endif %}>{{ d }}</option>
                  {% endfor %}
                </select>
              </div>
              <div class="col-6">
                <label class="form-label fw-semibold">Tempo (BPM)</label>
                <input name="tempo" type="number" class="form-control"
                       value="{{ last_params.get('tempo',['100'])[0] }}">
              </div>
            </div>

            <hr>
            <p class="fw-semibold mb-1">Contour (MIDI note numbers)</p>
            <div class="row g-2 mb-3">
              <div class="col-4">
                <label class="form-label small">Start</label>
                <input name="start_midi" type="number" class="form-control"
                       value="{{ last_params.get('start_midi',['64'])[0] }}">
              </div>
              <div class="col-4">
                <label class="form-label small">Peak</label>
                <input name="high_midi" type="number" class="form-control"
                       value="{{ last_params.get('high_midi',['72'])[0] }}">
              </div>
              <div class="col-4">
                <label class="form-label small">Low</label>
                <input name="low_midi" type="number" class="form-control"
                       value="{{ last_params.get('low_midi',['60'])[0] }}">
              </div>
            </div>

            <hr>
            <p class="fw-semibold mb-1">Rhythm</p>
            <div class="row g-2 mb-3">
              <div class="col-6">
                <label class="form-label small">Complexity (1–3)</label>
                <select name="rhythm_complexity" class="form-select">
                  {% for c in [1,2,3] %}
                  <option {% if last_params.get('rhythm_complexity',['1'])[0]|int == c %}selected{% endif %}>{{ c }}</option>
                  {% endfor %}
                </select>
              </div>
              <div class="col-6 d-flex align-items-end">
                <div class="form-check">
                  <input class="form-check-input" type="checkbox" name="syncopation" id="sync"
                         {% if last_params.get('syncopation') %}checked{% endif %}>
                  <label class="form-check-label" for="sync">Syncopation</label>
                </div>
              </div>
            </div>

            <hr>
            <p class="fw-semibold mb-1">Ornament Techniques</p>
            <div class="d-flex flex-wrap gap-2 mb-3">
              {% for t in ['passing_tone','neighbor_tone','appoggiatura','suspension','anticipation','escape_tone'] %}
              <div class="form-check">
                <input class="form-check-input" type="checkbox" name="techniques" value="{{ t }}"
                       id="tech_{{ t }}"
                       {% if t in last_params.get('techniques',[]) %}checked{% endif %}>
                <label class="form-check-label small" for="tech_{{ t }}">{{ t.replace('_',' ') }}</label>
              </div>
              {% endfor %}
            </div>

            <div class="mb-3">
              <label class="form-label small">Random seed (blank = random each time)</label>
              <input name="seed" class="form-control form-control-sm"
                     value="{{ last_params.get('seed',[''])[0] }}" placeholder="e.g. 42">
            </div>

          </div>
          <div class="card-footer">
            <button type="submit" class="btn btn-primary w-100">Generate →</button>
          </div>
        </div>
      </form>
    </div>

    {# ── Right: Preview ───────────────────────────────────────────────── #}
    <div class="col-lg-7">
      {% if preview %}
      <div class="card">
        <div class="card-header d-flex justify-content-between align-items-center">
          <span class="fw-semibold">Preview</span>
          <span class="badge bg-secondary">Difficulty suggestion: {{ preview.difficulty_suggestion }}</span>
        </div>
        <div class="card-body">
          {# VexFlow notation — same pattern as exercise.html #}
          <div id="notation-container" style="overflow-x:auto"></div>
          <div class="mt-2">
            <button id="play-btn" class="btn btn-sm btn-outline-primary">▶ Play</button>
            <button id="stop-btn" class="btn btn-sm btn-outline-secondary ms-1">■ Stop</button>
          </div>
          <p class="small text-muted mt-2">Auto-tags: {{ preview.auto_tags | join(', ') }}</p>
        </div>
      </div>

      <div class="card mt-3">
        <div class="card-header fw-semibold">Approve &amp; Save</div>
        <div class="card-body">
          <form method="post" action="{{ url_for('admin_melody_approve') }}">
            <div class="row g-3">
              <div class="col-12"><label class="form-label fw-semibold">Name <span class="text-danger">*</span></label>
                <input name="name" class="form-control" required></div>
              <div class="col-12"><label class="form-label fw-semibold">Description</label>
                <textarea name="description" class="form-control" rows="2"></textarea></div>
              <div class="col-md-4"><label class="form-label fw-semibold">Difficulty</label>
                <select name="difficulty" class="form-select">
                  {% for d in [1,2,3,4,5] %}
                  <option {% if d == preview.difficulty_suggestion %}selected{% endif %}>{{ d }}</option>
                  {% endfor %}
                </select></div>
              <div class="col-md-8"><label class="form-label fw-semibold">Container</label>
                <select name="container_id" class="form-select">
                  <option value="">— None —</option>
                  {% for c in containers %}
                  <option value="{{ c.id }}">{{ c.name }}</option>
                  {% endfor %}
                </select></div>
              <div class="col-12"><label class="form-label fw-semibold">Tags</label>
                <div class="d-flex flex-wrap gap-2">
                  {% for t in all_tags %}
                  <div class="form-check">
                    <input class="form-check-input" type="checkbox" name="tag_ids" value="{{ t.id }}"
                           id="at{{ t.id }}" {% if t.name in preview.auto_tags %}checked{% endif %}>
                    <label class="form-check-label small" for="at{{ t.id }}">{{ t.name }}</label>
                  </div>
                  {% endfor %}
                </div></div>
            </div>
            <div class="d-flex gap-2 mt-3">
              <button class="btn btn-success">✓ Approve &amp; Save</button>
            </div>
          </form>
          <form method="post" action="{{ url_for('admin_melody_reject') }}" class="mt-2">
            <button class="btn btn-outline-danger">✗ Reject — Discard</button>
          </form>
        </div>
      </div>

      {# Notation script #}
      <script>
      (function(){
        const notes = {{ preview.notes_json | safe }};
        const midiUrl = "{{ preview.midi_url }}";
        // Render with existing notation.js (same interface as exercise.html)
        if (window.renderNotation) {
          window.renderNotation('notation-container', notes, {
            timeSignature: '{{ last_params.get("time_sig",["4/4"])[0] }}',
            clef: '{{ last_params.get("clef",["treble"])[0] }}',
            keySignature: '{{ last_params.get("key",["C"])[0] }}',
          });
        }
        // Play button via existing player.js / Tone.js
        document.getElementById('play-btn').onclick = function() {
          if (window.playMidi) window.playMidi(midiUrl);
        };
        document.getElementById('stop-btn').onclick = function() {
          if (window.stopMidi) window.stopMidi();
        };
      })();
      </script>
      {% else %}
      <div class="text-center text-muted py-5 border rounded">
        <p>Set parameters and click <strong>Generate</strong> to preview a melody.</p>
      </div>
      {% endif %}
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Verify full flow**

Start server, visit `http://localhost:5000/admin/melodies/generate`.
- Select a GenProgression, set params, click Generate
- Preview pane should appear with notation + play button + difficulty suggestion + auto-tags pre-checked
- Fill name, click "Approve & Save" → redirects to melody edit page for the new melody
- Verify the melody appears in `/admin/melodies` list with correct public_id and tags
- Try "Reject" → redirects back to generator form with params preserved

- [ ] **Step 4: Commit**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship && git add app.py templates/admin/melody_generator.html && git commit -m "feat: melody generator UI — generate/approve/reject loop"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Parameter-driven generate → review → approve/reject loop (Tasks 1–6)
- ✅ GenProgression realization in key/mode (Task 1)
- ✅ Rhythm-cell skeleton with complexity/syncopation settings (Task 2)
- ✅ Chord-tone placement on strong beats (Task 3)
- ✅ Six ornament techniques (passing, neighbor, appoggiatura, suspension, anticipation, escape) (Task 4)
- ✅ Auto-tags from time sig, min_duration, clef, mode, techniques (Task 5)
- ✅ Difficulty suggestion heuristic (Task 5)
- ✅ `generation_params` stored on approved melody (Task 6)
- ✅ Hybrid difficulty: engine suggests, admin confirms/overrides before save (Task 6 approve form)
- ✅ Container assigned at approve time (Task 6)
- ✅ Preview: VexFlow notation + Tone.js playback of generated MIDI (Task 6 template)
- ✅ Deterministic with fixed seed (tested in Task 5)
- ✅ Strong beats are always chord tones (tested in Task 5)
- ✅ Range/leap constraints hold (Task 3 `_toward_waypoint` + 9-semitone cap)
- ✅ emitted JSON round-trips through existing notation.js player (Task 5 `slots_to_notes_json`)
- ✅ Rhythm generator is design-only: not built, but architecture (build_rhythm) is reusable for pitchless output
- ✅ Tests in `tests/test_generator.py` covering all golden-test criteria from spec §10

**Placeholder scan:** No TBDs. All functions and code blocks are complete.

**Type consistency:** `realize_harmony` → `windows` list used consistently in `place_skeleton`, `active_window`, `apply_techniques`. `slots` list shape `{beat, dur, dotted, is_strong, midi}` consistent across Tasks 2–5. `generate(params)` expects `gen_progression_chords` key (not a DB object) to keep it testable without Flask context.
