# Musicianship Trainer — Implementation Plan for Claude Code

## Status: 3 of 14 tasks already done (marked ✅)

---

## A. Deployment — SQLite Database in Git

### ✅ A1. `.gitignore` — DONE
Changed `instance/` to `instance/*` + `!instance/musicianship.db` so the db gets committed.
Also added `migrate.py` to the gitignored dev-tools section.

### ✅ A2. `app.py` — DONE
Replaced the `DATABASE_URL` / Postgres URL-patching block with:
```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///musicianship.db'
```

### ✅ A3. `render.yaml` — DONE
Removed the `databases:` block and `DATABASE_URL` env var.
Simplified `startCommand` to just `gunicorn app:app`.

### A4. Delete `main.py`
Safe to delete — it's a PyCharm "hello world" template with no app logic.
```
git rm main.py
```

### A5. Untrack already-committed files that are now gitignored
Some dev scripts may be tracked in git despite being in `.gitignore` (if they were committed before gitignore was updated). Run:
```
git rm --cached migrate.py 2>/dev/null || true
git rm --cached main.py 2>/dev/null || true
```
Then commit everything:
```
git add -A
git commit -m "Switch to bundled SQLite db; simplify Render deployment"
```

---

## B. Fix: Old Exercises Can't Be Deleted

**Root cause:** `delete_exercise.py` looks up exercises by `source_key`, but exercises seeded before that column was added have `source_key = NULL`.

**Fix:** Create and run `backfill_source_keys.py` (then delete it / add to gitignore):

```python
"""backfill_source_keys.py — run once locally, then delete."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from app import app
from models import db, Melody, Rhythm, ChordProgression, HolisticExercise
import re

def slug(name):
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')

with app.app_context():
    changed = 0

    # Melody: derive source_key from midi_filename
    # e.g. "melodic/c_major_ascending/c_major_ascending.mid" → "c_major_ascending"
    for m in Melody.query.filter_by(source_key=None).all():
        parts = m.midi_filename.replace('\\', '/').split('/')
        if len(parts) >= 2:
            m.source_key = parts[-2]   # second-to-last segment = folder name
            changed += 1
            print(f"  Melody  {m.id}: → {m.source_key}")

    # ChordProgression: same logic
    for p in ChordProgression.query.filter_by(source_key=None).all():
        parts = p.midi_filename.replace('\\', '/').split('/')
        if len(parts) >= 2:
            p.source_key = parts[-2]
            changed += 1
            print(f"  Harm    {p.id}: → {p.source_key}")

    # Rhythm: no midi_filename; derive from name
    for r in Rhythm.query.filter_by(source_key=None).all():
        r.source_key = slug(r.name)
        changed += 1
        print(f"  Rhythm  {r.id}: → {r.source_key}")

    # HolisticExercise: derive from folder field
    # e.g. "holistic/waltz_c_major/" → "waltz_c_major"
    for h in HolisticExercise.query.filter_by(source_key=None).all():
        folder = h.folder.strip('/')
        h.source_key = folder.split('/')[-1]
        changed += 1
        print(f"  Holistic {h.id}: → {h.source_key}")

    db.session.commit()
    print(f"\nBackfilled {changed} records.")
```

Run it, verify output, commit the updated `instance/musicianship.db`.

---

## C. Bug Fix: Tied Notes Sound Twice

**File:** `static/js/player.js`  
**Function:** `window.playNoteArray`

Currently both `tieStart` and `tieEnd` notes trigger `triggerAttackRelease`, so tied notes play twice. 

**Replace the entire `window.playNoteArray` function with:**

```javascript
window.playNoteArray = async function (notes, bpm, onDone) {
  if (typeof Tone === 'undefined') return;
  await Tone.start();

  getSampler();
  await Tone.loaded();

  const s = getSampler();
  Tone.Transport.cancel();
  const secPerBeat = 60 / (bpm || 100);
  let t = Tone.Transport.seconds;

  notes.forEach((n, idx) => {
    const baseBeats = DUR_BEATS[n.duration] || 1;
    const beats     = n.dotted ? baseBeats * 1.5 : baseBeats;
    const isRest    = n.duration.endsWith('r');

    // tieEnd: the sound was already covered by the tieStart note.
    // Advance the clock silently and skip scheduling.
    if (n.tieEnd) {
      t += beats * secPerBeat;
      return;
    }

    if (!isRest) {
      // For a tieStart note, extend the sound to cover the tied continuation.
      let soundBeats = beats;
      if (n.tieStart && idx + 1 < notes.length && notes[idx + 1].tieEnd) {
        const nxt = notes[idx + 1];
        const nb  = DUR_BEATS[nxt.duration] || 1;
        soundBeats += nxt.dotted ? nb * 1.5 : nb;
      }
      const pitch = vexKeyToTonePitch(n.key);
      if (pitch) {
        Tone.Transport.schedule((time) => {
          s.triggerAttackRelease(pitch, soundBeats * secPerBeat * 0.9, time);
        }, t);
      }
    }
    t += beats * secPerBeat;
  });

  if (onDone) {
    Tone.Transport.schedule(() => { onDone(); }, t + 0.3);
  }
  Tone.Transport.start();
};
```

---

## D. Bug Fix: Harmonic Results Chord Playback Dissonance

**File:** `templates/harmonic_results.html`  
**Root cause:** In `voiceProgression`, bass and upper voices are range-clamped with `Math.max`/`Math.min`, which can push a note to the wrong pitch class (e.g. C4=60 clamped to B3=59, sounding a major 7th dissonance). 

**Replace the entire `voiceProgression` function with:**

```javascript
function voiceProgression(chords) {
  if (!chords || !chords.length) return [];
  const result = [];

  function voiceFirst(chord) {
    const tones = getChordTonePcs(chord);
    // Bass in octave 3 (MIDI 36–59), pitch-class preserved
    let bass = 36 + chord.bass_pc;
    while (bass % 12 !== chord.bass_pc % 12) bass++;
    while (bass > 59) bass -= 12;
    while (bass < 36) bass += 12;
    // Three upper voices near octave 4–5 (MIDI 52–84)
    const upper = [0, 1, 2].map(v => {
      let midi = tones[v % tones.length] + 60;
      while (midi < 52) midi += 12;
      while (midi > 84) midi -= 12;
      return midi;
    });
    upper.sort((a, b) => a - b);
    return [bass, ...upper];
  }

  const first = voiceFirst(chords[0]);
  result.push(first.map(midiToToneName));
  let prev = first;

  for (let i = 1; i < chords.length; i++) {
    const chord = chords[i];
    const tones = getChordTonePcs(chord);

    // Bass: find nearest in-range MIDI note with the correct pitch class
    let bass = nearestMidiForPc(prev[0], chord.bass_pc);
    while (bass > 59) bass -= 12;
    while (bass < 36) bass += 12;

    // Upper voices: parsimonious voice leading, pitch-class-safe range restriction
    const upper = prev.slice(1).map(prevMidi => {
      let best = null, bestDist = Infinity;
      tones.forEach(pc => {
        const cand = nearestMidiForPc(prevMidi, pc);
        const d = Math.abs(cand - prevMidi);
        if (d < bestDist) { bestDist = d; best = cand; }
      });
      while (best > 84) best -= 12;
      while (best < 52) best += 12;
      return best;
    });

    const voicing = [bass, ...upper];
    result.push(voicing.map(midiToToneName));
    prev = voicing;
  }
  return result;
}
```

---

## E. Feature: Reference Toggles — `player.js` Changes

**File:** `static/js/player.js`

Two changes needed:

### E1. Expose `window.playMidi` and remove auto-attach of `btn-play`

At the bottom of the IIFE (currently `if (btnPlay) btnPlay.addEventListener('click', play);`):

**Remove:**
```javascript
if (btnPlay) btnPlay.addEventListener('click', play);
```

**Replace with:**
```javascript
// Expose play() publicly so exercise templates can chain it after references.
// Templates are responsible for attaching their own btn-play listener.
window.playMidi = play;
```

Keep the stop listener unchanged:
```javascript
if (btnStop) btnStop.addEventListener('click', stop);
```

### E2. Add `window.playCountIn` function

Add this new function inside the IIFE (after `window.playChordArray`, before the closing `})();`):

```javascript
/**
 * Play a metronome count-in: one measure of sine-click ticks.
 * Compound meters (6/8, 9/8, 12/8): beat = dotted quarter.
 * Simple meters: beat = quarter note.
 * @param {number}        bpm      tempo in BPM
 * @param {number}        top      time signature numerator
 * @param {number}        bot      time signature denominator
 * @param {function|null} onDone   callback when finished
 */
window.playCountIn = async function (bpm, top, bot, onDone) {
  if (typeof Tone === 'undefined') return;
  await Tone.start();

  const synth = new Tone.Synth({
    oscillator: { type: 'sine' },
    envelope: { attack: 0.001, decay: 0.04, sustain: 0, release: 0.02 },
  }).toDestination();

  const secPerBeat  = 60 / (bpm || 100);
  const isCompound  = (bot === 8);
  const numBeats    = isCompound ? top / 3 : top;
  const beatSec     = isCompound ? secPerBeat * 1.5 : secPerBeat;

  Tone.Transport.cancel();
  let t = Tone.Transport.seconds;

  for (let i = 0; i < numBeats; i++) {
    const beatTime = t + i * beatSec;
    Tone.Transport.schedule(time => {
      synth.triggerAttackRelease('A5', '32n', time);
    }, beatTime);
  }

  if (onDone) {
    Tone.Transport.schedule(() => { onDone(); }, t + numBeats * beatSec + 0.1);
  }
  Tone.Transport.start();
};
```

---

## F. Feature: `rhythm_notation.js` — Make Count-In Toggleable

**File:** `static/js/rhythm_notation.js`  
**Function:** `window.playRhythmArray`

Add a fourth `options` parameter and skip the count-in block when `options.skipCountIn` is true.

**Change the function signature from:**
```javascript
window.playRhythmArray = async function (notes, bpm, onDone) {
```
**To:**
```javascript
window.playRhythmArray = async function (notes, bpm, onDone, options) {
```

**Then wrap the count-in block** (the `for (let i = 0; i < countBeats; i++)` loop and its surrounding setup) in:
```javascript
if (!options || !options.skipCountIn) {
  // ... existing count-in code ...
}
```

The count-in setup variables (`isCompound`, `countBeats`, `countBeatSec`) only need to be declared if the count-in will run, or can be hoisted outside the `if` block — either way is fine.

---

## G. Feature: Melodic Exercise Reference Checkboxes

**File:** `templates/exercise.html`

### G1. Add checkboxes to the Listen card

In the card body `div.card-body`, after the existing "Listen as many times" text div, add:

```html
<div class="d-flex flex-wrap gap-3 align-items-center ms-1 mt-2">
  <div class="form-check form-check-inline mb-0">
    <input class="form-check-input" type="checkbox" id="cb-beat-ref" checked>
    <label class="form-check-label small" for="cb-beat-ref">Beat Reference</label>
  </div>
  <div class="form-check form-check-inline mb-0">
    <input class="form-check-input" type="checkbox" id="cb-scale-ref">
    <label class="form-check-label small" for="cb-scale-ref">Scale Reference</label>
  </div>
</div>
```

### G2. Replace the play button and add chaining script

The `btn-play` listener is now handled by the template (player.js no longer auto-attaches it after the E1 change above).

Add this script block **after** the `player.js` and `notation.js` script tags, replacing or adding to the existing key-reference script block:

```javascript
document.addEventListener('DOMContentLoaded', () => {
  // ── Key Reference (standalone button, unchanged) ─────────────────────────
  const btnKeyRef = document.getElementById('btn-key-ref');
  if (btnKeyRef) {
    btnKeyRef.addEventListener('click', async () => {
      const scale = KEY_SCALES[KEY_SIGNATURE] || KEY_SCALES['C'];
      const scaleNotes = scale.map(k => ({ key: k, duration: 'q' }));
      const triadNotes = [0, 2, 4, 7].map(i => ({ key: scale[i], duration: 'q' }));
      const refNotes   = [...scaleNotes, { key: 'b/4', duration: 'qr' }, ...triadNotes];
      btnKeyRef.disabled = true;
      btnKeyRef.innerHTML = '<i class="bi bi-volume-up me-1"></i>Playing…';
      await window.playNoteArray(refNotes, 144, () => {
        btnKeyRef.disabled = false;
        btnKeyRef.innerHTML = '<i class="bi bi-music-note-list me-1"></i>Key Reference';
      });
    });
  }

  // ── Play button — chains optional references then plays the MIDI ──────────
  const btnPlay = document.getElementById('btn-play');
  if (btnPlay) {
    btnPlay.addEventListener('click', async () => {
      const beatChecked  = document.getElementById('cb-beat-ref')?.checked;
      const scaleChecked = document.getElementById('cb-scale-ref')?.checked;

      // Build a sequential chain: [beat] → [scale] → MIDI
      const steps = [];
      if (beatChecked)  steps.push('beat');
      if (scaleChecked) steps.push('scale');
      steps.push('midi');

      // Disable play button for duration of chain
      btnPlay.disabled = true;

      let i = 0;
      function runNext() {
        if (i >= steps.length) { btnPlay.disabled = false; return; }
        const step = steps[i++];
        if (step === 'beat') {
          window.playCountIn(MELODY_TEMPO || 100, TIME_SIG_TOP, TIME_SIG_BOTTOM, runNext);
        } else if (step === 'scale') {
          const scale = KEY_SCALES[KEY_SIGNATURE] || KEY_SCALES['C'];
          const scaleNotes = scale.map(k => ({ key: k, duration: 'q' }));
          const triadNotes = [0, 2, 4, 7].map(i => ({ key: scale[i], duration: 'q' }));
          const refNotes   = [...scaleNotes, { key: 'b/4', duration: 'qr' }, ...triadNotes];
          window.playNoteArray(refNotes, 144, runNext);
        } else {
          // Re-enable before handing off to window.playMidi so its own UI logic works
          btnPlay.disabled = false;
          window.playMidi();
        }
      }
      runNext();
    });
  }
});
```

### G3. Add `MELODY_TEMPO` template variable

In the `<script>` block that defines `MELODY_ID`, `MIDI_URL`, etc., add:
```javascript
const MELODY_TEMPO = {{ melody.tempo }};
```

---

## H. Feature: Rhythm Exercise Beat Reference Checkbox

**File:** `templates/rhythm_exercise.html`

### H1. Add checkbox to the Listen card

In the card body, after the stop button and before the text div, add:
```html
<div class="form-check form-check-inline mb-0">
  <input class="form-check-input" type="checkbox" id="cb-beat-ref" checked>
  <label class="form-check-label small" for="cb-beat-ref">Beat Reference</label>
</div>
```

### H2. Update the `playRhythmArray` call

In the existing play button listener, change:
```javascript
await window.playRhythmArray(RHYTHM_NOTES, RHYTHM_TEMPO, resetUI);
```
to:
```javascript
const skipCountIn = !document.getElementById('cb-beat-ref')?.checked;
await window.playRhythmArray(RHYTHM_NOTES, RHYTHM_TEMPO, resetUI, { skipCountIn });
```

---

## I. Feature: Harmonic Exercise Key Reference Checkbox

**File:** `templates/harmonic_exercise.html`

### I1. Add checkbox to the Listen card

In the card body `d-flex` div, after the stop button and before the `btn-key-ref` button, add:
```html
<div class="form-check form-check-inline mb-0">
  <input class="form-check-input" type="checkbox" id="cb-key-ref">
  <label class="form-check-label small" for="cb-key-ref">Key Reference</label>
</div>
```

### I2. Add `btn-play` listener (player.js no longer auto-attaches it)

In the template's `<script>` block (after harmonic.js and player.js are loaded), add:

```javascript
document.addEventListener('DOMContentLoaded', () => {
  const btnPlay = document.getElementById('btn-play');
  if (btnPlay) {
    btnPlay.addEventListener('click', async () => {
      const keyRefChecked = document.getElementById('cb-key-ref')?.checked;
      if (keyRefChecked) {
        btnPlay.disabled = true;
        const chords = window.ChordBlockUtils.HARM_KEY_REFERENCE[KEY_SIGNATURE]
          || (KEY_SIGNATURE.endsWith('m')
              ? window.ChordBlockUtils.HARM_KEY_REFERENCE['Am']
              : window.ChordBlockUtils.HARM_KEY_REFERENCE['C']);
        await window.playChordArray(chords, 72, () => {
          btnPlay.disabled = false;
          window.playMidi();
        });
      } else {
        window.playMidi();
      }
    });
  }
});
```

Note: `HARM_KEY_REFERENCE` is already imported from `ChordBlockUtils` in harmonic.js; for the template script it's accessed via `window.ChordBlockUtils.HARM_KEY_REFERENCE`.

---

## J. Feature: Holistic Exercise Reference Checkboxes

**File:** `templates/holistic_exercise.html`

### J1. Add three checkboxes to the Listen card

In the card body, after the existing buttons row (after the text div), add:
```html
<div class="d-flex flex-wrap gap-3 align-items-center ms-1 mt-2">
  <div class="form-check form-check-inline mb-0">
    <input class="form-check-input" type="checkbox" id="cb-scale-ref">
    <label class="form-check-label small" for="cb-scale-ref">Scale Reference</label>
  </div>
  <div class="form-check form-check-inline mb-0">
    <input class="form-check-input" type="checkbox" id="cb-harmony-ref">
    <label class="form-check-label small" for="cb-harmony-ref">Harmony Reference</label>
  </div>
  <div class="form-check form-check-inline mb-0">
    <input class="form-check-input" type="checkbox" id="cb-beat-ref" checked>
    <label class="form-check-label small" for="cb-beat-ref">Beat Reference</label>
  </div>
</div>
```

### J2. Modify the WAV play button handler in holistic.js (or template inline script)

The holistic exercise play button (`btn-wav-play`) plays the WAV recording. Modify the handler to chain references first. 

Find the section in `holistic.js` (or in `holistic_exercise.html`'s inline script) that attaches the `btn-wav-play` click listener. Replace the direct `audio.play()` call with a chained sequence.

The holistic exercise template already defines `KEY_SIGNATURE`, `EXERCISE_TEMPO` (if not, add `const EXERCISE_TEMPO = {{ exercise.tempo }};` to the template vars), `TIME_SIG_TOP`, `TIME_SIG_BOTTOM`.

**Key scale data** for holistic references — the `KEY_SCALES` object already exists in `exercise.html`; copy it into the holistic template's script block (or into holistic.js), since holistic also needs it.

**Replace the play button handler** (wherever it lives in holistic.js or the template) with logic like:

```javascript
btnWavPlay.addEventListener('click', async () => {
  if (wavPlaying) return;

  const scaleChecked   = document.getElementById('cb-scale-ref')?.checked;
  const harmonyChecked = document.getElementById('cb-harmony-ref')?.checked;
  const beatChecked    = document.getElementById('cb-beat-ref')?.checked;

  // Disable button while refs play
  btnWavPlay.disabled = true;
  btnWavPlay.innerHTML = '<i class="bi bi-volume-up me-1"></i>Playing…';

  const steps = [];
  if (scaleChecked)   steps.push('scale');
  if (harmonyChecked) steps.push('harmony');
  if (beatChecked)    steps.push('beat');
  steps.push('wav');

  let i = 0;
  function runNext() {
    if (i >= steps.length) return;
    const step = steps[i++];

    if (step === 'scale') {
      const scaleData = HOLISTIC_KEY_SCALES[KEY_SIGNATURE] || HOLISTIC_KEY_SCALES['C'];
      const scaleNotes = scaleData.map(k => ({ key: k, duration: 'q' }));
      const triadNotes = [0, 2, 4, 7].map(j => ({ key: scaleData[j], duration: 'q' }));
      const refNotes   = [...scaleNotes, { key: 'b/4', duration: 'qr' }, ...triadNotes];
      window.playNoteArray(refNotes, 144, runNext);

    } else if (step === 'harmony') {
      const chords = window.ChordBlockUtils.HARM_KEY_REFERENCE[KEY_SIGNATURE]
        || (KEY_SIGNATURE.endsWith('m')
            ? window.ChordBlockUtils.HARM_KEY_REFERENCE['Am']
            : window.ChordBlockUtils.HARM_KEY_REFERENCE['C']);
      window.playChordArray(chords, 72, runNext);

    } else if (step === 'beat') {
      window.playCountIn(EXERCISE_TEMPO, TIME_SIG_TOP, TIME_SIG_BOTTOM, runNext);

    } else if (step === 'wav') {
      // Restore button state and play the WAV recording
      btnWavPlay.disabled = false;
      btnWavPlay.innerHTML = '<i class="bi bi-play-fill"></i> Play Recording';
      // ... existing WAV playback logic here (wavPlayCount++, audio.play(), etc.) ...
    }
  }
  runNext();
});
```

Add `HOLISTIC_KEY_SCALES` to the holistic template's script vars (same data as `KEY_SCALES` in exercise.html) and add `const EXERCISE_TEMPO = {{ exercise.tempo }};`.

---

## Summary Table

| # | File | Change | Status |
|---|------|--------|--------|
| A1 | `.gitignore` | Allow instance/musicianship.db; gitignore migrate.py | ✅ Done |
| A2 | `app.py` | Remove Postgres URL logic; hardcode SQLite | ✅ Done |
| A3 | `render.yaml` | Remove Postgres; simplify startCommand | ✅ Done |
| A4 | `main.py` | Delete file | ⬜ Todo |
| A5 | git | `git rm --cached` stale tracked files; commit db | ⬜ Todo |
| B | db | Run backfill_source_keys.py; commit db | ⬜ Todo |
| C | `static/js/player.js` | Fix tied notes in playNoteArray | ⬜ Todo |
| D | `templates/harmonic_results.html` | Fix voiceProgression clamping | ⬜ Todo |
| E1 | `static/js/player.js` | Expose window.playMidi; remove auto-attach | ⬜ Todo |
| E2 | `static/js/player.js` | Add window.playCountIn | ⬜ Todo |
| F | `static/js/rhythm_notation.js` | Add skipCountIn option to playRhythmArray | ⬜ Todo |
| G | `templates/exercise.html` | Beat + Scale Reference checkboxes + chain handler | ⬜ Todo |
| H | `templates/rhythm_exercise.html` | Beat Reference checkbox | ⬜ Todo |
| I | `templates/harmonic_exercise.html` | Key Reference checkbox + btn-play handler | ⬜ Todo |
| J | `templates/holistic_exercise.html` | Scale + Harmony + Beat Reference checkboxes + chain | ⬜ Todo |
