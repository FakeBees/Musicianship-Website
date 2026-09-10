# Musicianship Trainer — Admin CMS, Accounts, Adaptivity & Melody Generation

**Status:** Design approved (2026-06-25). Awaiting spec review → implementation planning.
**Author:** Jared Damron (with Claude)
**Scope of this spec:** Architecture for four phases of work on the existing Flask Musicianship Trainer. Each phase will get its own implementation plan; Phases 0 and 1 are planned first.

---

## 1. Context & goals

The Musicianship Trainer is an existing Flask app (VexFlow notation entry, Tone.js playback, MIDI input, SQLite bundled in git, deployed on Render). It has four dictation modes — **melodic, rhythmic, harmonic, holistic** — with enharmonic-aware grading and Roman/Nashville/lead-sheet chord entry. It currently has **no user accounts** and **no admin UI**; content is seeded via local Python scripts (`generate_midi.py`, `generate_rhythms.py`, `generate_harmonic_midi.py`, `generate_holistic_exercises.py`).

This work serves two tracks that happen to align:
- **Honors thesis** (graded on *functionality design* + *exercise corpus*; programming and graphic design are out of thesis scope but are how we realize the design).
- **Future business** (B2B licensing to schools; the institutional layer is the make-or-break).

### Goals
1. Fix two known credibility bugs.
2. Add accounts + a teacher/class layer so progress can be tracked (foundation for everything else).
3. Add simple adaptivity (auto-leveling + spaced repetition).
4. Build an admin CMS to create/edit/delete all four exercise types, with **parameter-driven melody generation** (approve/reject loop) as one feature inside it.

### Non-goals (deferred)
- Assignments / gradebook / LMS integration (teacher layer is **read-only progress view** for now).
- Rhythm auto-generation (design extensibly, build later).
- Payments/licensing.
- Production hardening (see §9 — explicitly deferred but documented).

---

## 2. Current state (what already exists — do not rebuild)

- **Models** (`models.py`): `Tag`, `Melody`, `UserAttempt`, `Rhythm`, `RhythmAttempt`, `ChordProgression`, `HarmonicAttempt`, `HolisticExercise`, `HolisticAttempt`, plus association tables `melody_tags`, `rhythm_tags`, `progression_tags`, `holistic_tags`.
- **Note format** (used everywhere): JSON array of `{"key": "c/4", "duration": "q"[, "dotted": true]}`. Rests use `"b/4"` + duration suffixed `r` (e.g. `"qr"`). Durations: `w h q 8 16`. This is the canonical interchange format — the generator must emit exactly this.
- **MIDI pipeline**: `midi_to_notes.py` (`extract_notes`, `build_json_list`, `note_to_vex`, `snap_duration`) parses MIDI → note JSON. `generate_midi.py` has `write_midi(filename, notes, tempo)`, `notes_to_json(raw_notes)`, a `MELODIES` list, and `seed()`.
- **Difficulty**: `Melody.difficulty` (1–5) already exists, as do `time_signature`, `key_signature`, `clef`, `min_duration`, `tempo`.
- **Tags**: the same `Tag` rows the user filters on before an exercise. Tags include `contains:` prefixed names (used by harmonic/holistic indexes).
- **Grading** (`app.py`, `chord_utils.py`): position-based, enharmonic-aware for pitch; chord grading separates letter vs quality; supports inversions/sevenths/extensions/sus and Roman/Nashville/lead-sheet display.
- **Deploy**: `app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///musicianship.db'`; DB committed at `instance/musicianship.db`; `gunicorn app:app` on Render.

---

## 3. Dev-vs-production posture (READ THIS)

**For now (development, site not publicly open):** keep the existing low-friction workflow.
- SQLite stays bundled in git (`instance/musicianship.db`).
- Schema changes may be applied with **one-off local migration scripts** (the project's existing pattern — see `CLAUDE_CODE_PLAN.md` §B `backfill_source_keys.py`), then the updated `.db` is committed.
- MIDI/audio assets stay committed under `static/`.
- Admin content can be created/edited directly; direct DB manipulation is acceptable.

**Security floors that are NOT deferrable even in dev:**
- Passwords must be **hashed** (Werkzeug `generate_password_hash`) from day one — never store plaintext, even in a dev DB that's committed to git.
- Set a real `SECRET_KEY` via env var for any deployment that has real user logins (the current `'dev-secret-key-change-in-production'` fallback is fine only for purely local use).
- The admin section must be **role-gated** the moment accounts exist.

**Production transition checklist (do NOT do now; document & revisit before public launch):**
- [ ] Move from bundled SQLite → **managed Postgres** (`psycopg2-binary` is already a dependency; restore a `DATABASE_URL` config path).
- [ ] Adopt **Flask-Migrate / Alembic** for versioned schema migrations; stop committing the DB; stop using one-off migration scripts.
- [ ] Move committed MIDI/audio → **object storage** (S3 / Cloudflare R2) + CDN; store URLs in DB instead of `static/` paths.
- [ ] Real secrets management (env-injected `SECRET_KEY`, DB creds), `SESSION_COOKIE_SECURE`, HTTPS-only.
- [ ] Auth hardening: email verification, password reset, rate-limiting/lockout on login, CSRF protection on all forms.
- [ ] Backups + migration of any real student data already collected.
- [ ] Consider moving melody-generation compute off the request thread (background job) if batches get large.
- [ ] Re-evaluate committing PII (any real student emails) — must not live in a public git repo.

Every model and route below is designed so this transition is a config/storage swap, not a rewrite (e.g., asset references go through helper properties; no business logic assumes SQLite).

---

## 4. Data model changes

> Migration approach (dev): add tables/columns, then write a one-off `migrate_<feature>.py` script (mirroring `backfill_source_keys.py`) to backfill and commit the updated `.db`. New nullable columns keep existing rows valid.

### 4.1 Accounts & classes (Phase 1)
```python
class User(db.Model):
    id            = Integer, pk
    email         = String(255), unique, not null
    password_hash = String(255), not null         # Werkzeug hash
    display_name  = String(100)
    role          = String(20), default 'student'  # 'admin' | 'teacher' | 'student'
    created_at    = DateTime, server_default now
    # Flask-Login: is_authenticated/is_active/get_id via UserMixin

class Class(db.Model):
    id          = Integer, pk
    name        = String(120), not null
    join_code   = String(12), unique, not null     # students join with this
    teacher_id  = FK -> user.id, not null
    created_at  = DateTime
    # teacher = relationship; members via class_members

class_members = Table(             # many-to-many student <-> class
    class_id  FK -> class.id,
    user_id   FK -> user.id,
)
```
- Roles: `admin` = Jared (full `/admin` access). `teacher` = owns classes, read-only progress view. `student` = takes exercises, has personal history.
- Students join a class via `join_code` (no assignments yet).

### 4.2 Link attempts to users (Phase 1)
Add nullable `user_id = FK -> user.id` to **all** attempt tables: `UserAttempt`, `RhythmAttempt`, `HarmonicAttempt`, `HolisticAttempt`. Nullable preserves existing anonymous rows and lets logged-out practice still work. Populate when a logged-in user submits.

### 4.3 Public IDs (Phase 3, applied to all four exercise types)
Add `public_id = String(16), unique, indexed` to `Melody`, `ChordProgression`, `Rhythm`, `HolisticExercise`.
- Format: `MEL-####`, `HRM-####`, `RHY-####`, `HOL-####` (zero-padded sequence, assigned at creation; backfill existing rows).
- Shown on each exercise page; searchable in admin. Independent of the integer PK.

### 4.4 Containers (Phase 3 — melodies now, reusable later)
```python
class Container(db.Model):
    id          = Integer, pk
    name        = String(120), not null
    description = String(300)
    created_at  = DateTime

# Melody gains:
container_id = FK -> container.id, nullable   # exactly one container per melody (or none)
```
- **One container per melody**, reassignable (your choice). Tags still cross-cut and are independent of containers.
- Admin can view "all containers" or filter to one, and within either, filter by tags.
- A default container (e.g. "Unsorted") may hold melodies with `container_id = NULL`.

### 4.5 Generation parameters (Phase 3)
Add `generation_params = Text (JSON), nullable` to `Melody` — the full parameter set that produced it (key, length, chosen `GenProgression`, enabled techniques, contour waypoints, rhythm settings, seed). Enables regenerate/iterate and is a thesis artifact (traceability of how each exercise was made).

### 4.6 Generation chord-progression library (Phase 3) — NEW, separate from `ChordProgression`
This is **distinct** from the student-facing `ChordProgression` exercises. It is the harmonic skeleton source for generation, stored **by number, key-agnostic**.
```python
class GenProgression(db.Model):
    id          = Integer, pk
    number      = Integer, unique          # referenced "by number" (e.g. progression #7)
    name        = String(120)              # optional human label
    length_bars = Integer                  # 2 | 4 | 8 | 16
    mode        = String(10), default 'major'   # 'major' | 'minor'
    # Key-agnostic chord list as scale-degree / Roman tokens with durations (in beats):
    #   [{"degree": "I",  "quality": "maj", "inversion": 0, "beats": 4},
    #    {"degree": "vi", "quality": "min", "inversion": 0, "beats": 4}, ...]
    chords_json = Text, not null
    difficulty  = Integer, default 1       # informs generated-melody difficulty suggestion
    tags        = many-to-many -> Tag (optional, e.g. 'contains:secondary_dominant')
```
- Stored in scale degrees so one progression realizes in any key. The generator transposes to the chosen key at generation time.
- Seed a starter set across all four lengths and both modes; expandable by the admin (basic CRUD in admin, lower priority than melody CRUD).

---

## 5. Phase 0 — Bug fixes

Reference: `BUGS.md`. Draft fixes already exist in `CLAUDE_CODE_PLAN.md` §C/§D — verify against current code before applying (filenames may have changed post-refactor; chord-block logic moved toward `chord_block_utils.js`).

- **BUG-001 — V→I dissonance on results-page playback.** Tone.js Transport/synth state from a prior playback bleeds into the next. Ensure `Tone.Transport.cancel()` + synth `releaseAll()` before results-page playback starts. Fix in the harmonic results playback path (`templates/harmonic_results.html` `voiceProgression` / playback init). The `voiceProgression` clamping fix in `CLAUDE_CODE_PLAN.md` §D (pitch-class-safe range restriction instead of `Math.max/min`) is part of this.
- **BUG-002 — Roman-numeral inversions show slash chords instead of figured bass.** Fix only the Roman branch of `format_chord_name` (`chord_utils.py`) and `formatChordName` (`chord_block_utils.js` / `harmonic.js`): root=none, 1st inv=`6`, 2nd inv=`64`, 7th-chord 3rd inv=`4/2`. Leave lead-sheet (`C/E`) and Nashville (`1/3`) untouched. Figured-bass reference table is in `BUGS.md`.

**Verification:** play I–IV–V–I on the results page (no dissonance on the final I after V); confirm a 1st-inversion tonic renders `I6` in Roman mode, `C/E` in lead, `1/3` in Nashville.

---

## 6. Phase 1 — Accounts + teacher/class layer

### Components
- **Auth** (Flask-Login + Werkzeug hashing): register, login, logout. Email/password only (no OAuth/SSO yet). Roles assigned at creation; admin role set manually for Jared.
- **Session model**: logged-in users get attempts linked to `user_id`; logged-out practice still works (anonymous attempts, as today).
- **Student progress page** (`/me` or `/progress`): history of attempts with scores over time, grouped by mode and topic/tag. Reuses existing `*Attempt` rows now keyed by `user_id`.
- **Teacher layer**:
  - Create/manage `Class` (name → generated `join_code`).
  - Students join via code.
  - **Read-only progress view**: per class, a roster with each student's recent activity and average accuracy by mode/topic. No assignments, no editing student data.
- **Route protection**: decorators `@login_required`, `@role_required('teacher')`, `@role_required('admin')`.

### Migration
One-off `migrate_accounts.py`: create `user`, `class`, `class_members`; add nullable `user_id` to the four attempt tables; create the admin user; commit `.db`.

### Notes
- Keep all existing routes working for anonymous users (backward compatible).
- Passwords hashed from the start (see §3 security floors).

---

## 7. Phase 2 — Adaptivity (simple)

Depends on Phase 1 (per-user attempts) and a per-exercise difficulty signal (exists: `difficulty` 1–5).

### 7.1 Mastery model
Maintain a lightweight per-user, per-topic mastery signal derived from attempt history:
- `Mastery(user_id, tag_or_topic, mode)` → rolling accuracy (e.g., exponential moving average of overall_score) + a coarse mastery level. Store as a small table or compute on the fly from recent attempts (start with on-the-fly; add a cache table only if needed).

### 7.2 Auto-leveling
When the user practices within a set of filters, pick the next exercise's **difficulty** by stepping up/down from their recent performance in that filter set:
- ≥ threshold (e.g. 85%) over last *N* → step difficulty up.
- ≤ threshold (e.g. 60%) → step down.
- else hold. Bounded to available difficulties for the active filters. Falls back gracefully when no exercise matches (reuse existing fallback-to-full-library behavior in `random_melody`).

### 7.3 Spaced repetition
SM-2-lite scheduler keyed to `(user_id, exercise)`:
- On each attempt, update an interval/ease based on score (correct → longer interval; missed → reset to short).
- Store `next_due` per `(user, exercise)`.
- A "Review" mode surfaces **due** previously-missed exercises before/with new material.
- Keep it simple: a single small table `ReviewSchedule(user_id, exercise_type, exercise_id, ease, interval_days, next_due)`.

### 7.4 Scope guard
"Simple" is a hard requirement — no IRT/Bayesian knowledge tracing. EMA accuracy + difficulty stepping + SM-2-lite only.

---

## 8. Phase 3 — Admin CMS + melody generator

### 8.1 Admin shell (`/admin`, admin-only)
Four sections: **Melodies, Harmonies, Rhythms, Holistic.** Each section provides:
- **List**: searchable by `public_id`, filterable by tag (and, for melodies, by container or "all containers"). Shows key metadata.
- **Edit**: metadata, tags, (melody) container, and the note/chord data where practical.
- **Delete**: with confirmation; reuse/extend existing `delete_exercise.py` logic.
- **Manual create from MIDI**: upload MIDI → parse via `midi_to_notes.py` → preview (notation + playback) → set metadata/tags → save. Emits canonical note JSON + stores MIDI under `static/`.
  - **Holistic** additionally: upload **audio (WAV)** + multiple MIDIs (`melody.mid`, `harmony.mid`, `melody_N.mid`, `rhythm_N.mid`) per the existing folder convention in `HOLISTIC_DICTATION_PLAN.md`.

### 8.2 Melody generator (feature inside the Melodies section)
The parameter-driven **generate → review → approve/reject → next** loop.

**UI loop:**
1. Admin sets parameters (persist between melodies; editable anytime).
2. Click Generate → engine produces one melody.
3. Admin sees it on the VexFlow sheet, can **listen** (existing player), sees the **engine-suggested difficulty** and **auto-derived tags**.
4. **Hybrid difficulty**: engine suggests 1–5; admin confirms or changes **every time** before save.
5. **Approve** → saved to DB (canonical note JSON + generated MIDI), assigned `public_id`, placed in the selected **container**, tags applied, `generation_params` stored. **Reject** → discarded.
6. Advance to next; parameters persist.

**Parameters (initial set; will iterate):**
- Key; mode (major/minor).
- Length (in measures) → maps to a `GenProgression` of matching bar length.
- `GenProgression` selection: pick a specific number, or "let engine choose by key+difficulty+length."
- Time signature; shortest note value (`min_duration`); clef.
- Contour waypoints: start note, high point, low point, optional interior points (auto-placed by default; pinnable).
- Enabled theory techniques (toggles): passing tone, neighbor tone, appoggiatura, suspension, anticipation, escape tone, … (extensible registry).
- Rhythm settings: rhythm-cell complexity, syncopation on/off, dotted figures on/off, anacrusis on/off.
- Optional random seed (for reproducibility / regenerate).

### 8.3 Generation engine — algorithm (skeleton + diminution, constraint-based)
> Pure rule/constraint approach (NOT Markov, NOT ML): every note traces to a music-theory rule, guaranteeing requested techniques actually appear and producing trustworthy auto-tags. This is also the thesis-defensible choice.

**Step 1 — Realize harmony.** Take the chosen `GenProgression` (key-agnostic scale degrees) and realize it in the selected key → an ordered list of chords with beat durations (the harmonic rhythm).

**Step 2 — Rhythm first.** Build a rhythmic surface from a library of idiomatic **rhythm cells** (per beat, per meter), weighted by the complexity/syncopation/dotted settings and bounded by `min_duration`. Determine which rhythmic positions are **strong beats** (chord-tone anchors) vs weak (eligible for ornament tones).

**Step 3 — Structural skeleton.** Place a **chord tone on each strong beat**, choosing the chord tone that best advances toward the next **contour waypoint**. Connect skeleton tones with a **stepwise bias**; direction is biased toward the next waypoint (ascend toward the high point, descend toward the cadence). Apply the **gap-fill principle**: after a leap, prefer reversing direction and stepping back to fill the gap. Hard constraints: stay in range/tessitura; avoid tritone leaps and oversized leaps; cadence lands on an appropriate chord tone (typically tonic).

**Step 4 — Diminution / ornamentation.** For each **enabled** technique, a rule-module inserts the corresponding non-chord tone(s) at eligible weak positions per textbook definition:
- passing tone (fills a third by step, same direction),
- neighbor tone (step away and back),
- appoggiatura (accented, leap in, step down to resolution),
- suspension (held-over, resolve down by step),
- anticipation, escape tone, etc.
Each insertion is recorded → drives auto-tagging.

**Step 5 — Tag + difficulty.**
- **Auto-tags**: time signature, `min_duration`, clef, and every technique actually inserted (+ key/topic tags) — these are the same `Tag` rows the user filters on.
- **Difficulty suggestion**: heuristic from technique count/complexity, leap sizes/frequency, chromaticism, rhythmic complexity, and `GenProgression.difficulty` → 1–5. Admin confirms/overrides.

**Step 6 — Emit.** Produce canonical `{key, duration, dotted}` JSON; write MIDI via existing `write_midi`; on approve, persist `Melody` (+ `public_id`, `container_id`, `generation_params`, tags).

**Extensibility:** technique modules live in a registry so new techniques (and later, a rhythm generator reusing Steps 1–2) can be added without touching the core loop.

### 8.4 Rhythm generator (DESIGN-ONLY, build later)
Reuse Steps 1–2 (rhythm-cell library) without pitch. Same approve/reject loop, emitting pitchless `{duration, dotted}` JSON. Spec it now structurally so the admin shell and loop are shared; implement in a later phase.

---

## 9. Security & production transition

See §3. Summary of what Phase 1 must do correctly even in dev (hash passwords, gate admin/teacher routes, real `SECRET_KEY` when deployed with logins) and what is explicitly deferred to the production transition checklist (Postgres, Alembic migrations, object storage, email verification, password reset, CSRF, rate-limiting, backups, removing PII/DB from git).

---

## 10. Testing

- **Phase 0**: manual verification scenarios in §5; add a small unit test for `format_chord_name` Roman inversions.
- **Phase 1**: auth flows (register/login/logout, role gating), anonymous practice still works, attempts link to users; class join via code; teacher sees only their classes.
- **Phase 2**: unit tests for the difficulty-stepping function and SM-2-lite interval updates (pure functions, easy to test).
- **Phase 3**: golden tests for the generator — given fixed params + seed, output is deterministic and (a) every strong beat is a chord tone, (b) each enabled technique appears at least once and is correctly tagged, (c) range/leap constraints hold, (d) emitted JSON round-trips through the existing player/grader.

---

## 11. Build order & open items

**Order:** Phase 0 → Phase 1 → Phase 2 → Phase 3. Generate the implementation plan **phase by phase** (Phase 0 + 1 first).

**Defaults chosen (override if needed):** email/password auth; class-code join; `public_id` on all four types; melody length in measures.

**Deferred (noted, not built now):** assignments/gradebook, rhythm auto-generation, payments, full production hardening.

**Open items to confirm during planning:**
- Exact starter set of `GenProgression` entries (numbers, lengths, modes) — Jared to supply or approve a generated starter set.
- Initial technique registry contents and their difficulty weights.
- Whether teacher progress view needs CSV export now or later.
