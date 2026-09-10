# Bug Tracker

A running list of known bugs and issues to fix. Add new entries at the bottom of the relevant section.

---

## Harmonic Dictation

**BUG-001 — Dissonant/messy chord during results page playback** — ✅ **FIXED 2026-03-19**
Chords sounded dissonant or garbled during playback on the results page, but played correctly during the exercise. Most commonly observed on the I chord following a V chord. Cause was Tone.js Transport scheduling leaving a prior playback session uncleaned. Fixed by switching `window.playChordArray()` in `static/js/player.js` from `Tone.Transport.schedule` to direct `Tone.now() + 0.1` AudioContext scheduling, with `stopAllNotes()` calling `sampler.releaseAll()`.

**BUG-002 — Roman numeral inversion notation uses slash chords instead of figured bass** — ✅ **FIXED 2026-03-19**
Inversions in Roman numeral mode displayed as `I/E` or `I/G` instead of `I6` / `I64` / `I4/2`. Fixed in the Roman branch of `format_chord_name` (`chord_utils.py`) and `formatChordName` (`static/js/chord_block_utils.js`). Nashville slash notation was intentionally left unchanged; lead sheet was already correct.

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

**BUG-003 — `admin_teacher` gets a 403 from their own nav bar** — ✅ **FIXED 2026-08-28**
`templates/base.html` shows an "Admin" link pointing at `/admin/my-school` for users with role `admin_teacher`. That route (`app.py:2395`) redirects them to `admin_courses(school_id=…)` — i.e. `/admin/schools/<id>/courses` — which is gated `@role_required('admin')` at `app.py:1050`. The result is that an `admin_teacher` clicking Admin in the nav always lands on a 403, making the role effectively unusable through the UI.

Fixed by doing both: `admin_my_school` now redirects to `admin_school_detail`, and the whole course/module CMS was opened to `admin_teacher` behind a new `require_school_role()` guard. See `docs/NAMING.md` § School authority.

**Anonymous access to practice pages** *(needs a design decision, not necessarily a fix)*
`/` requires login, but `/melodic`, `/rhythm`, `/harmonic`, `/holistic`, every `/exercise/<id>` page and every `/random` route have no `@login_required`. Anyone with a URL can practise; only POST submit requires an account. The existence of `/sandbox` suggests this is intentional, but it is currently undocumented rather than deliberately designed. Decide whether to keep it as the sandbox story or gate it.

**SQLAlchemy 2.0 deprecation** *(low priority)*
`User.query.get()` in `load_user` (`app.py:46`) raises `LegacyAPIWarning` under SQLAlchemy 2.x. Harmless today; will break on a major upgrade. Replace with `db.session.get(User, int(user_id))`.

---

*Last updated: 2026-08-28*

---

### Figured bass quick reference (kept for reference)

| Inversion | Bass note | Roman numeral suffix | Lead sheet |
|---|---|---|---|
| Root position | Root | (none) | C |
| 1st inversion | 3rd | 6 | C/E |
| 2nd inversion | 5th | 64 | C/G |
| 3rd inversion (7th chords only) | 7th | 4/2 or 2 | C/B |
