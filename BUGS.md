# Bug Tracker

A running list of known bugs and issues to fix. Add new entries at the bottom of the relevant section.

---

## Harmonic Dictation

**BUG-001 — Dissonant/messy final chord on results page playback**
The last chord in a progression (observed on I–IV–V–I) sounds dissonant or garbled during playback on the results page, but plays correctly during the exercise. Only occurs post-grading. Likely a Tone.js scheduling or Transport state issue — a previous playback session may not be fully cleaned up before the results page initiates playback, causing notes from a prior play to bleed into or clash with the new playback. Investigate whether `Tone.Transport.cancel()` and synth `releaseAll()` are called before starting results-page playback.

**BUG-002 — Roman numeral inversion notation uses slash chords instead of figured bass**
Inversions in Roman numeral mode are displayed as `I/E` or `I/G` instead of the correct `I6` (first inversion, third in bass) and `I64` (second inversion, fifth in bass). Inversion notation differs by mode:
- **Lead sheet:** slash chord with note name — `C/E`, `C/G` ✓ (already correct)
- **Nashville:** slash chord with scale degree number — `1/3`, `1/5` (intentional, keep as-is)
- **Roman numeral:** figured bass numbers only — `I6`, `I64`, `I4/2` (currently wrong, shows slash notation like Nashville — fix this)

Fix only the Roman numeral branch in `format_chord_name` in `chord_utils.py` and `formatChordName` in `chord_block_utils.js` (or `harmonic.js` before refactor). Nashville slash notation is correct and should not be changed.

---

## Holistic Dictation

*(none yet)*

---

## Melodic Dictation

*(none yet)*

---

## Rhythmic Dictation

*(none yet)*

---

## General / Shared

*(none yet)*

---

*Last updated: 2026-03-18*

---

### Figured bass quick reference (for BUG-002 fix)

| Inversion | Bass note | Roman numeral suffix | Lead sheet |
|---|---|---|---|
| Root position | Root | (none) | C |
| 1st inversion | 3rd | 6 | C/E |
| 2nd inversion | 5th | 64 | C/G |
| 3rd inversion (7th chords only) | 7th | 4/2 or 2 | C/B |
