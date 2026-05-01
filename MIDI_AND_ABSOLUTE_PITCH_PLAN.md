# MIDI Keyboard Input + Absolute Pitch Training Upgrades — Implementation Plan

**Audience:** Claude Code, working on this repo.
**Scope:** Two coordinated feature additions — (1) Web MIDI keyboard input across the dictation exercises, and (2) expanded options in the Absolute Pitch Training page (octave range, octave-blind grading, multiple instrument timbres).

This plan is surgical: every change has a target file and, where applicable, a line range. Do not refactor beyond what's listed. Match the existing code style of the file you're editing (the codebase uses plain ES5/ES6 + jQuery-free vanilla JS, Tone.js v14, and VexFlow for notation).

---

## 1. High-level summary

### 1A. MIDI keyboard input
Add Web MIDI keyboard input as an alternative input method on three of the four dictation pages:

| Section                   | MIDI behavior                                                                                                                                                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Melodic dictation         | Each MIDI note-on places a note at the next sequential beat, using the currently selected duration. The played pitch overrides any selected accidental modifier (sharp/flat/natural). Cursor auto-advances. |
| Absolute pitch training   | MIDI note-on acts identically to clicking the on-screen keyboard. Pressing the MIDI key also plays the note through the current sampler (audible feedback).                    |
| Rhythmic dictation        | Every MIDI note-on places the currently selected duration at the next available rhythm slot. The pitch played is irrelevant — any key is a "place note" event.                 |
| Harmonic dictation        | MIDI input is ignored. Do not include the MIDI script on this page.                                                                                                            |

MIDI connection UX: **auto-detect on page load**. Show a small status indicator (`MIDI: <device name>` or `MIDI: not connected`) in `templates/base.html` so it appears on every page. No manual connect button required.

### 1B. Absolute pitch training upgrades
On `templates/absolute_pitch.html`, add:

1. **Octave-range slider** with 7 discrete stops: `C4–C5`, `C4–C6`, `C3–C6`, `C3–C7`, `C2–C7`, `C1–C7`, `A0–C8` (full keyboard). Target notes are sampled from the selected range.
2. **"Grade octave" checkbox** (default: checked). When unchecked, the on-screen keyboard collapses to a single octave (C4–B4) and any matching pitch class — clicked or played via MIDI — counts as correct, regardless of the actual sounded octave.
3. **Instrument selector** (dropdown). Options:
   - Salamander Grand Piano (current default)
   - Synthesizer (Tone.PolySynth)
   - Electric Piano
   - Organ
   - Violin
   - Cello
   - Flute
   - Guitar (acoustic)
   - Marimba / Xylophone

Persist the user's slider, checkbox, and instrument choices in `localStorage` so they survive page reloads.

---

## 2. New files

### 2.1 `static/js/midi_input.js` (new)
A single small module — no framework. Responsibilities:

- **Device management**
  - On script load, call `navigator.requestMIDIAccess({ sysex: false })`.
  - Cache the chosen input device. If multiple inputs are present, pick the first one and listen for `statechange` to swap if it disconnects/reconnects.
  - Expose `MidiInput.getStatus()` → `{ connected: boolean, deviceName: string }`.
- **Status indicator hook**
  - Expose `MidiInput.attachStatusIndicator(element)` — element receives text content updates (`MIDI: <name>` / `MIDI: not connected`) and a CSS class (`midi-connected` / `midi-disconnected`).
- **Pub/sub for note-on**
  - Expose `MidiInput.onNoteOn(handler)` where `handler` receives `{ midi: number, velocity: number }`.
  - Treat note-on with velocity 0 as note-off (MIDI spec quirk) — do not fire the handler.
  - Ignore note-off, control change, pitch bend, sustain pedal, and all other messages.
- **Graceful degradation**
  - If `navigator.requestMIDIAccess` is undefined (older browsers, Safari without flag), expose a no-op `MidiInput` whose `getStatus()` returns `{ connected: false, deviceName: 'unsupported' }`. Do not throw.
- **Unlock note**
  - This module does **not** call `Tone.start()`. The first user gesture on each page (existing Play button etc.) handles audio unlock; MIDI events arriving before that gesture should still place notes silently — Tone.js will simply drop the audio and that's fine.

### 2.2 `static/js/midi_to_vex.js` (new, tiny — ~40 lines)
Pure helper. One exported function:

```
midiToVexKey(midiNumber, keySignature) → "c/4" | "c#/5" | "eb/4" | ...
```

- For natural notes, return `"<letter>/<octave>"`.
- For black keys, choose sharp vs. flat spelling based on the current `KEY_SIGNATURE` global (already exposed by `templates/exercise.html` line 136). Use this rule:
  - Flat-side keys (`F`, `Bb`, `Eb`, `Ab`, `Db`, `Gb`, `Dm`, `Gm`, `Cm`, `Fm`) → flat spelling (`bb`, `eb`, etc.)
  - Sharp-side keys (`G`, `D`, `A`, `E`, `B`, `F#`, `Em`, `Bm`) → sharp spelling
  - `C` and `Am` → sharp spelling (default)
- Return the VexFlow key string in the form `"<letter><accidental>/<octave>"` (lowercase letter, accidental is `b` or `#`, e.g. `"f#/4"`, `"eb/3"`).

Unit-testable in isolation; no DOM dependencies.

### 2.3 `static/js/instruments.js` (new)
A registry of Tone.js Sampler / Synth factory functions keyed by instrument name. Sample sources use the open `nbrosowsky/tonejs-instruments` GitHub-hosted samples, which mirror the current Salamander-from-CDN setup.

Exports:
```
window.Instruments = {
  list:    [{ id, label }, ...],   // for the dropdown
  create:  (id) => Tone.Sampler | Tone.PolySynth,
};
```

Instrument definitions (all `.toDestination()`):

| `id`              | Label                       | Implementation |
| ----------------- | --------------------------- | -------------- |
| `salamander`      | Salamander Grand Piano      | Existing Sampler config — keep verbatim, baseUrl `https://tonejs.github.io/audio/salamander/` |
| `synth`           | Synthesizer                 | `new Tone.PolySynth(Tone.Synth, { oscillator: { type: 'triangle' }, envelope: { attack: 0.01, release: 0.8 } })` |
| `electric-piano`  | Electric Piano              | Sampler from `https://nbrosowsky.github.io/tonejs-instruments/samples/piano-electric/` (use the project's URL map) |
| `organ`           | Organ                       | Sampler from `samples/organ/` |
| `violin`          | Violin                      | Sampler from `samples/violin/` |
| `cello`           | Cello                       | Sampler from `samples/cello/` |
| `flute`           | Flute                       | Sampler from `samples/flute/` |
| `guitar`          | Guitar (acoustic)           | Sampler from `samples/guitar-acoustic/` |
| `marimba`         | Marimba                     | Sampler from `samples/xylophone/` (project labels mallet samples under `xylophone`) |

For each Sampler, copy the URL map from the upstream `tonejs-instruments` README — Claude Code should fetch `https://github.com/nbrosowsky/tonejs-instruments` to get the exact sample filename list per instrument; do not invent filenames. If a fetch is not possible at implementation time, hard-code only the filenames present in the upstream repo at commit `master`.

Each `Instruments.create(id)` returns an object with the same trigger surface (`triggerAttackRelease(note, duration)`), so callers don't need to branch by instrument type.

Loading state: `create()` returns the instance immediately; the caller listens for `Tone.loaded()` (or the Sampler's `onload`) before enabling the Play button. Keep the existing `samplesLoaded` flag pattern.

---

## 3. Modifications by file

### 3.1 `templates/base.html`
- Add a small `<span id="midi-status" class="midi-disconnected">MIDI: not connected</span>` to the existing navbar / header. Style with a tiny CSS chip (green dot when connected, gray when not).
- Include `<script src="{{ url_for('static', filename='js/midi_input.js') }}"></script>` once, in `base.html`, **before** the page-specific `{% block scripts %}`.
- After load, call `MidiInput.attachStatusIndicator(document.getElementById('midi-status'))`.

### 3.2 `templates/exercise.html` (melodic dictation)
- After the existing `<script src=".../notation.js"></script>` (line 141), add:
  ```html
  <script src="{{ url_for('static', filename='js/midi_to_vex.js') }}"></script>
  <script>
    MidiInput.onNoteOn(({ midi }) => {
      if (typeof window.placeMidiNote === 'function') {
        window.placeMidiNote(midi);
      }
    });
  </script>
  ```
- No UI changes on this page. Existing duration buttons, dot, and accidental controls are untouched. The accidental modifier is simply ignored when a MIDI note arrives.

### 3.3 `static/js/notation.js`
**Goal:** expose `window.placeMidiNote(midiNumber)` that performs the same effect as the existing click-to-place flow at lines 744–782, but driven by MIDI pitch instead of Y-coordinate.

- Around line 815 (just before `// Public API (results page)`), add a new exported function:
  ```js
  window.placeMidiNote = function (midiNumber) {
    const key = midiToVexKey(midiNumber, KEY_SIGNATURE);
    if (!key) return;

    // Replicate the body of the mousedown placement, minus Y-coordinate logic
    // and minus accidental application (MIDI pitch wins).
    const beats  = noteBeats({ duration: selectedDur, dotted: isDotted });
    const bTotal = (typeof BEATS_TOTAL !== 'undefined') ? BEATS_TOTAL : Infinity;
    if (currentBeats + beats > bTotal + 0.001) { flashError(); return; }

    if (!fitsInCurrentMeasure(beats)) {
      const bpm        = getBeatsPerMeasure();
      const incomplete = measureInfo.find(m => !m.isFull);
      if (!incomplete) { flashError(); return; }
      const remaining  = bpm - incomplete.usedBeats;
      const firstSpec  = beatsToNoteSpec(remaining);
      const secondSpec = beatsToNoteSpec(beats - remaining);
      if (!firstSpec || !secondSpec) { flashError(); return; }
      userNotes.push({ key, duration: firstSpec.duration,  dotted: firstSpec.dotted,  tieStart: true });
      userNotes.push({ key, duration: secondSpec.duration, dotted: secondSpec.dotted, tieEnd:   true });
      currentBeats += beats;
      // Do NOT auto-reset accidental: it was never applied for MIDI input.
      refresh();
      return;
    }

    userNotes.push({ key, duration: selectedDur, dotted: isDotted });
    currentBeats += beats;
    refresh();
  };
  ```
- Note: this function must live in the closure that already owns `selectedDur`, `isDotted`, `userNotes`, `currentBeats`, `measureInfo`, `flashError`, `fitsInCurrentMeasure`, `getBeatsPerMeasure`, `beatsToNoteSpec`, `noteBeats`, and `refresh`. Place it inside the same IIFE as those.
- **No audible playback** — per spec, melodic dictation MIDI input is silent (so MIDI key presses can't spoil the answer).

### 3.4 `templates/rhythm_exercise.html`
- After `<script src=".../rhythm_notation.js"></script>`, add:
  ```html
  <script>
    MidiInput.onNoteOn(() => {
      if (typeof window.placeMidiRhythmNote === 'function') {
        window.placeMidiRhythmNote();
      }
    });
  </script>
  ```
- The MIDI pitch is ignored — every note-on just calls the placer.

### 3.5 `static/js/rhythm_notation.js`
- Around line 530 (just before `// Refresh`), add:
  ```js
  window.placeMidiRhythmNote = function () {
    const beats  = noteBeats({ duration: selectedDur, dotted: isDotted });
    const bTotal = (typeof BEATS_TOTAL !== 'undefined') ? BEATS_TOTAL : Infinity;
    if (currentBeats + beats > bTotal + 0.001) { flashError(); return; }

    if (!fitsInCurrentMeasure(beats)) {
      const bpm        = getBeatsPerMeasure();
      const incomplete = measureInfo.find(m => !m.isFull);
      if (!incomplete) { flashError(); return; }
      const remaining  = bpm - incomplete.usedBeats;
      const firstSpec  = beatsToNoteSpec(remaining);
      const secondSpec = beatsToNoteSpec(beats - remaining);
      if (!firstSpec || !secondSpec) { flashError(); return; }
      userNotes.push({ duration: firstSpec.duration,  dotted: firstSpec.dotted,  tieStart: true });
      userNotes.push({ duration: secondSpec.duration, dotted: secondSpec.dotted, tieEnd:   true });
      currentBeats += beats;
      refresh();
      return;
    }

    userNotes.push({ duration: selectedDur, dotted: isDotted });
    currentBeats += beats;
    refresh();
  };
  ```
- Same closure-placement rule as 3.3.
- No audible playback.

### 3.6 `templates/absolute_pitch.html`
This page gets the most UI changes.

#### 3.6.1 New UI elements
Insert above the existing `#play-btn` (around line 230):

```html
<!-- Settings panel -->
<div class="ap-settings">
  <label class="ap-setting">
    <span>Range:</span>
    <input id="range-slider" type="range" min="0" max="6" step="1" value="0">
    <span id="range-label">C4 – C5</span>
  </label>

  <label class="ap-setting">
    <input id="grade-octave" type="checkbox" checked>
    Grade exact octave
  </label>

  <label class="ap-setting">
    <span>Sound:</span>
    <select id="instrument-select"></select>
  </label>
</div>
```

The `#instrument-select` options are populated from `Instruments.list` at runtime.

Update the `<p class="pitch-sub">` text to reflect the current range dynamically (replace the hard-coded "2 Octaves — C4 to B5" line at 228).

#### 3.6.2 Range table
At the top of the existing `<script>` block (line 252+), define:
```js
const OCTAVE_RANGES = [
  { label: 'C4 – C5',         low: 'C4', high: 'C5' },
  { label: 'C4 – C6',         low: 'C4', high: 'C6' },
  { label: 'C3 – C6',         low: 'C3', high: 'C6' },
  { label: 'C3 – C7',         low: 'C3', high: 'C7' },
  { label: 'C2 – C7',         low: 'C2', high: 'C7' },
  { label: 'C1 – C7',         low: 'C1', high: 'C7' },
  { label: 'A0 – C8 (full)',  low: 'A0', high: 'C8' },
];
```

Refactor the hardcoded `WHITE_KEYS` / `BLACK_KEYS` arrays (lines 253–267) into builder functions `buildWhiteKeys(low, high)` and `buildBlackKeys(low, high)` that produce the same shape but cover the requested range.

#### 3.6.3 Grade-octave behavior
- Add a top-level `gradeOctave` flag, initialized from `localStorage` (default `true`).
- When `gradeOctave === true`: keyboard renders the full selected range (current behavior, but range-aware). Correct answer = exact note match.
- When `gradeOctave === false`: keyboard always renders one octave (C4–B4). Correct answer = matching pitch-class only. The audible target still plays in its actual sampled octave from the chosen range.
  - Implementation: in `onKeyClick(note, el)` (line 388–415), compare `pitchClass(note) === pitchClass(targetNote)` instead of `note === targetNote`. `pitchClass` strips the trailing octave digit.
  - The keyboard-rebuild logic must call `buildWhiteKeys('C4','B4')` / `buildBlackKeys('C4','B4')` whenever `gradeOctave` is unchecked, regardless of the range slider.

#### 3.6.4 Instrument selector
- Replace the hard-coded `sampler` declaration (lines 286–304) with:
  ```js
  let sampler;
  function loadInstrument(id) {
    if (sampler && sampler.dispose) sampler.dispose();
    samplesLoaded = false;
    playBtn.disabled = true;
    statusDisplay.textContent = `Loading ${id}…`;
    sampler = Instruments.create(id);
    Tone.loaded().then(() => {
      samplesLoaded = true;
      playBtn.disabled = false;
      playBtn.textContent = 'Play Note';
      statusDisplay.textContent = 'Press "Play Note" to begin';
    });
  }
  ```
- Wire `#instrument-select.onchange` → save to localStorage + `loadInstrument(...)`.

#### 3.6.5 MIDI input
At the bottom of the script block, add:
```js
MidiInput.onNoteOn(({ midi }) => {
  const noteName = midiToNoteName(midi);                  // e.g. 67 → 'G4'
  const targetEl = document.querySelector(`[data-note="${noteName}"]`)
                || document.querySelector(`[data-note="${pitchClassEl(midi)}"]`); // fallback when octave-blind
  if (targetEl) onKeyClick(noteName, targetEl);
  else onKeyClick(noteName, document.createElement('div')); // still register answer if no UI key
});
```

`midiToNoteName(midi)` is a small helper (use sharp spelling, e.g. `Cs4`, to match the `data-note` format in `WHITE_KEYS`/`BLACK_KEYS`). `pitchClassEl(midi)` returns the same name normalized to the C4 octave for the octave-blind keyboard.

The `onKeyClick` audio playback already calls `playNote`, which goes through the sampler — this satisfies the "audible feedback in absolute pitch only" requirement.

#### 3.6.6 Persistence
- Settings keys: `ap.range` (0–6), `ap.gradeOctave` (boolean), `ap.instrument` (id string).
- Read on init; write on each change.

### 3.7 `templates/harmonic_exercise.html`
**No changes.** Do not include `midi_input.js` references here. The base template's `midi_input.js` script will load and the status indicator will still display, but no `onNoteOn` handler is registered, so MIDI presses are silently ignored. This is the intended behavior.

### 3.8 CSS
Add to the existing global stylesheet (or a new `static/css/midi.css` and include in base):
```css
#midi-status { font-size: 0.85rem; padding: 2px 8px; border-radius: 999px; }
#midi-status.midi-connected    { background: #d4edda; color: #155724; }
#midi-status.midi-disconnected { background: #e2e3e5; color: #6c757d; }

.ap-settings { display: flex; gap: 1.25rem; flex-wrap: wrap; align-items: center; margin: 0 0 1rem 0; }
.ap-setting  { display: flex; gap: 0.5rem; align-items: center; }
```

---

## 4. Edge cases & gotchas

1. **Audio unlock.** Web Audio requires a user gesture before sound plays. Existing buttons already handle this on each page; MIDI input that arrives before the user has clicked anything should still place notes (silently) on the dictation pages, and on absolute pitch will simply be inaudible until the user clicks Play once.
2. **Multiple MIDI devices.** Pick the first input. Don't crash if zero inputs are available.
3. **Hot-plug.** Listen for `statechange` on the `MIDIAccess` object; update the status indicator and re-bind to the new device.
4. **MIDI velocity 0.** Treat as note-off; don't fire `onNoteOn`.
5. **Sustain pedal / CC / pitch bend.** Ignore.
6. **Browser support.** Chrome, Edge, Opera support Web MIDI natively. Firefox supports it on desktop. Safari requires an extension. The `midi_input.js` no-op fallback handles this — page must still function without MIDI.
7. **Sampler swap mid-round (absolute pitch).** If the user changes instruments while a target note is being held, dispose cleanly. The next "Play Note" press should use the new instrument; mid-round swaps should not crash.
8. **Octave-blind and range-slider interaction.** When `gradeOctave` is unchecked, the slider still controls the audible target range — only the on-screen keyboard collapses to one octave. Make this explicit in a small helper text under the controls.
9. **Note spelling on melodic MIDI input.** Spelling derives from `KEY_SIGNATURE` (per `midiToVexKey`). Do not touch the user's accidental modifier state — it's left alone for subsequent click input.
10. **Auto-advance off the end.** When `currentBeats + beats > BEATS_TOTAL`, call `flashError()` and don't push (matches existing click behavior).

---

## 5. Testing checklist

After implementation, manually verify:

### MIDI keyboard (with a real device or a virtual MIDI keyboard like [VMPK](https://vmpk.sourceforge.io/))
- [ ] Status indicator shows `MIDI: <name>` on every page when device connected.
- [ ] Status flips to `MIDI: not connected` on unplug; flips back on replug.
- [ ] **Melodic dictation:** pressing a MIDI key places a note at the current cursor with the selected duration. Pitch matches MIDI input. Cursor advances. Sharp/flat selection state is unchanged after MIDI input. End-of-piece presses are blocked with `flashError()`.
- [ ] **Rhythmic dictation:** pressing any MIDI key places the selected duration. Pitch is ignored.
- [ ] **Absolute pitch training:** pressing a MIDI key acts identically to clicking the matching on-screen key. Audible playback fires through the current sampler. Correct/incorrect game state updates match clicks.
- [ ] **Harmonic dictation:** MIDI keys do nothing.

### Absolute pitch upgrades
- [ ] Range slider: each of the 7 stops snaps and updates the keyboard width + the sub-heading. Target notes drawn from the selected range only.
- [ ] Grade-octave checked + range C2–C7: pressing C4 when target is C5 = wrong.
- [ ] Grade-octave unchecked + range C2–C7: target is E5, pressing on-screen E (C4–B4 keyboard) = correct. Same target via MIDI E2 = also correct.
- [ ] Each instrument in the dropdown plays correctly. Switching instruments mid-session works. Loading state shows during sample fetch.
- [ ] Settings persist across page reload.

### Regression
- [ ] Existing click-to-place still works in melodic & rhythmic dictation.
- [ ] Existing accidental modifiers + click input still work in melodic.
- [ ] Salamander piano remains the default instrument on first visit.

---

## 6. Out of scope (do not implement)

- MIDI output / playback to external device.
- MIDI in harmonic dictation.
- Velocity-sensitive note placement.
- Custom MIDI device picker UI (auto-pick first device only).
- Transposition / clef-aware MIDI mapping beyond what `midiToVexKey` covers.
- Per-user preference sync to the database (localStorage only for now).

---

## 7. Suggested commit sequence

1. `static/js/midi_input.js` + base.html status indicator (smallest visible change).
2. `static/js/midi_to_vex.js` + `placeMidiNote` in notation.js + exercise.html hookup.
3. `placeMidiRhythmNote` in rhythm_notation.js + rhythm_exercise.html hookup.
4. `static/js/instruments.js` + absolute_pitch.html instrument selector.
5. Absolute-pitch range slider + grade-octave checkbox + persistence.
6. CSS polish + final manual test pass.

Each step should be runnable in isolation; the page should never be broken between commits.
