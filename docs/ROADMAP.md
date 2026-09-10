# Musicianship Trainer — Feature Inventory & Roadmap

*Snapshot taken 2026-08-28. Reflects `main` at commit `638fc83` plus uncommitted working-tree changes.*

Companion documents: [`NAMING.md`](NAMING.md) — what Section / Classroom / Course mean, and the
deliberate code-vs-database naming split. [`SCREEN_MAP.drawio`](SCREEN_MAP.drawio) — every screen, the navigation between them, and the
access level required for each. Open it in [diagrams.net](https://app.diagrams.net) or the VS Code / JetBrains
draw.io plugin.

---

## 0. Screen names & debug mode

Every screen has a stable name (`HOME`, `SECTION_MODULE_DETAIL`, `ADMIN_MELODY_GENERATOR`, …) defined once in
[`screens.py`](../screens.py) and shown in red monospace on each box in the screen map. The name is the
unambiguous way to refer to a screen when redesigning it — "redraw SECTION_MODULE_DETAIL" points at exactly one
route and one template.

**Debug mode** — press **`Ctrl+Shift+D`** on any page. A popup window opens showing the current screen's name,
URL, endpoint, template file, required access level, and your own permission state (role, school memberships,
section membership for the section in context, and whether you'd be allowed through). A small badge appears
bottom-left so you can tell debug mode is on. Press the combo again to turn it off; the setting persists across
page loads and tabs.

The popup follows the main tab automatically as you navigate — it listens for `localStorage` changes rather
than being reopened, so no popup-blocker fights.

> **Why not `fn+D`:** the `fn` key is invisible to JavaScript. `KeyboardEvent` exposes `ctrlKey`, `shiftKey`,
> `altKey` and `metaKey` but has no `fnKey`, in any browser — macOS handles `fn` below the browser layer, so
> `fn+D` arrives as a bare `d`. To change the combo, edit `MATCHES_TOGGLE` at the top of
> [`static/js/debug.js`](../static/js/debug.js); alternatives are listed in the comment above it.

**Keeping it honest:** `tests/test_screens.py` fails if a route exists without a name, if a name is duplicated,
if `screens.py` names a route or template that no longer exists, or if a name drawn on the .drawio has no entry
in `screens.py`. Rename a box in the diagram and the test suite tells you to rename it in `screens.py` too.

**Before production:** `/debug/panel` and `/debug/state` are currently open to anyone. They only ever report
the requester's own state, so nothing leaks between users, but they should be gated behind a config flag before
any real deployment.

---

## 1. Where the project stands

**Test suite: 60 passed** (`.venv/bin/python -m pytest -q`), covering the melody generator, holistic grading,
role guards, and school schema.

The build order from the original design spec was Phase 0 (bugs) → Phase 1 (accounts) → Phase 2 (adaptivity) →
Phase 3 (admin CMS + generator). **Phases 0, 1 and 3 are done. Phase 2 was skipped entirely** and is the single
largest gap between the spec and the code.

---

## 2. Built and working

### 2.1 Dictation modes

| Mode | Library | Random | Drill | Grading | Results |
|---|---|---|---|---|---|
| Melodic | ✅ `/melodic` | ✅ | ✅ VexFlow editor | pitch + duration | ✅ |
| Rhythmic | ✅ `/rhythm` | ✅ | ✅ percussion staff | duration only | ✅ |
| Harmonic | ✅ `/harmonic` | ✅ | ✅ chord-block builder | letter + quality | ✅ |
| Holistic | ✅ `/holistic` | ❌ none | ✅ WAV + N staves | per-line | ✅ |

- Harmonic notation modes: Roman numeral (figured-bass inversions `I6` / `I64` / `I4/2`), Nashville (slash),
  Lead Sheet. Sus modifier row appears only when the progression contains sus chords.
- Holistic was recently genericized: a `HolisticLine` table now supports **any number** of melody / rhythm /
  harmonic lines per exercise, with per-line-id scoring. Replaced the old fixed melody + optional-bass layout.
- Playback via Tone.js with direct `Tone.now()` scheduling (not Transport) to avoid the timing glitch that
  caused BUG-001.
- Filtering: difficulty, tags, time signature, minimum duration, clef, category.
- Visibility model on all four content types: `public` / `school` (scoped by `school_id`), enforced by
  `_visible_exercise_filter()`.

### 2.2 Accounts, schools, sections

- Email/password auth with hashed passwords (Flask-Login). Roles: `student`, `class_teacher`, `admin_teacher`,
  `admin`.
- `School` → `SchoolMembership` (its own per-school role) → `Course` → `Module` → `ModuleExercise`.
- `Section` joins students by code, links to a `Course`, has an owning `teacher_id` and an optional
  `assigned_teacher_id` (the `class_teacher`).
- `SectionModuleExercise` lets a teacher override the course curriculum per section: add exercises, hide modules,
  restore them, change completion criteria.
- `ModuleCompletion` tracks per-student, per-section progress with best score, attempt count, passing count.
- Student surfaces: `/my-sections`, `/section/<id>` mode select, module list, module detail with exercise blocks,
  `/me` progress page with attempt history and per-module completion.
- Teacher surfaces: `/teacher` dashboard, section detail with roster and per-mode averages, section editing,
  student removal, section deletion.

### 2.3 Admin CMS

Full list / edit / delete / upload for **Melodies, Rhythms, Harmonics, Holistic** plus **GenProgressions**,
**Schools / Courses / Modules / ModuleExercises**, and **Users**.

- MIDI upload → parse via `midi_to_notes.py` → metadata form → saved with a `public_id` (`MEL-0001`,
  `HRM-0004`, …).
- Holistic upload additionally takes a WAV plus per-line MIDIs, with a drag-reorder Lines builder (SortableJS).
- Module exercises support **filter presets** (`params_json`) and **count-based completion criteria**
  (`completion_criterion_json`).

### 2.4 Melody generator

Rule-based, not statistical: realize harmony from a `GenProgression` → build a rhythm skeleton from cells →
place chord tones on strong beats toward contour waypoints → apply enabled ornamentation techniques (passing,
neighbour, appoggiatura, suspension, anticipation, escape) → auto-tag and suggest difficulty → emit note JSON
plus MIDI. Admin reviews on a VexFlow stave, listens, confirms difficulty, then approves or rejects.

---

## 3. In progress (uncommitted working tree)

| File | State |
|---|---|
| `templates/admin/gen_progression_edit.html` | **+287 lines** — a visual chord-block editor for GenProgressions (palette buttons, click-to-select blocks, beat counts). Substantial and unfinished. |
| `templates/admin/melody_generator.html` | +107/−~40 — generator UI rework, presumably paired with the above. |
| `templates/admin/gen_progressions.html` | Minor list-page changes. |
| `templates/admin/index.html` | `url_for` fix for the Gen Progressions link (was a hardcoded `/admin/gen_progressions` that didn't match the real `/admin/gen-progressions` route). |
| `templates/home.html` | The four mode-card description paragraphs deleted. Looks like a deliberate simplification, but no replacement copy was added. |
| `instance/musicianship.db` | Binary DB churn — **this file should not be tracked at all** (see §5). |

**Decision needed:** finish the chord-block editor, or stash it and start the next feature clean.

---

## 4. Not built

### 4.1 Phase 2 — Adaptivity (the big one)

Nothing exists. No references to mastery, EMA, spaced repetition, or scheduling anywhere in the codebase. The
spec calls for three pieces:

- **Mastery signal** — per user, per topic/tag, per mode. Exponential moving average of `overall_score` over
  recent attempts. Compute on the fly first; add a cache table only if it proves slow.
- **Auto-leveling** — within an active filter set, step the next exercise's `difficulty` up at ≥85% over the
  last *N*, down at ≤60%, hold otherwise. Bounded to difficulties that actually exist for those filters, and
  falling back to the existing full-library fallback in `random_melody()`.
- **Spaced repetition** — SM-2-lite keyed on `(user_id, exercise_type, exercise_id)` with `ease`,
  `interval_days`, `next_due`. A Review mode surfaces due items.

Hard scope guard from the spec: EMA + difficulty stepping + SM-2-lite only. No IRT, no Bayesian knowledge
tracing.

Both the difficulty-stepping function and the SM-2 interval update are pure functions and should be
test-driven.

*dev note: I don't know when this kind of adaptivity was ever discussed. I think for now it'll just be up to the school to measure difficulty.

### 4.2 Rhythm generator

Design-only in the spec (§8.4). Reuses steps 1–2 of the melody engine (harmony + rhythm cells) without pitch,
emitting pitchless `{duration, dotted}` JSON through the same approve/reject loop. Never implemented.

### 4.3 Content volume

- 6 seeded harmonic progressions.
- 3 seeded holistic exercises.

Both were flagged as thin months ago and neither has grown. The melody generator solves this for melodies only.

### 4.4 Holistic gaps

- No `/holistic/random` route — the only mode without one. The library page is the sole entry point.
- No generator; every holistic exercise is hand-authored WAV + MIDI.
*dev note: holistic has to be handmade, and random selection doesn't make sense for it either.

### 4.5 Absolute pitch training

Listed as complete in the old status memory (piano sampler, single-note ID) and `MIDI_AND_ABSOLUTE_PITCH_PLAN.md`
exists, but there is **no route for it** in `app.py` and no template. Either it was never wired up, or it was
removed. Needs a decision: rebuild it, or delete the plan doc.

---

## 5. Bugs and defects

### BUG-003 — `admin_teacher` gets a 403 from their own nav bar *(new, confirmed)*

`templates/base.html` shows an "Admin" link to `/admin/my-school` for `admin_teacher`. That route
(`app.py:2395`) redirects them to `admin_courses(school_id=…)`, i.e. `/admin/schools/<id>/courses` — which is
gated `@role_required('admin')` at `app.py:1050`. An `admin_teacher` clicking Admin lands on a 403.

Fix options: widen `admin_courses` to `('admin_teacher', 'admin')` with a school-membership check (matching the
pattern already used in `admin_school_detail`), or point `admin_my_school` at `admin_school_detail` instead.

### BUG-001 / BUG-002 — stale entries in `BUGS.md`

Both are recorded as open in `BUGS.md` but were fixed on 2026-03-19 (Tone.js direct scheduling; figured-bass
Roman numerals in `chord_utils.py` and `chord_block_utils.js`). `BUGS.md` says *"Last updated: 2026-03-19"* and
still lists them as live. **Mark them resolved so the tracker is trustworthy again.**

### Anonymous access to practice pages *(needs a decision, not necessarily a fix)*

`/`, the home page, requires login. But `/melodic`, `/rhythm`, `/harmonic`, `/holistic`, all
`/exercise/<id>` pages and all `/random` routes have **no** `@login_required`. Anyone with a URL can practise;
only submitting requires an account. `/sandbox` implies this is intentional, but it's currently undocumented
and unguarded rather than deliberately designed. Decide: keep it as the sandbox story, or gate it.

### SQLAlchemy legacy warnings

`User.query.get()` in `load_user` (`app.py:46`) is a 2.0-deprecated pattern. Harmless today, will break on a
SQLAlchemy major upgrade.

---

## 6. Production readiness

None of this is done, and all of it was explicitly deferred in the design spec (§9). Listed here so the debt is
visible, not because it's urgent for a dev/thesis build.

- **`instance/musicianship.db` is committed to git.** It contains real user rows and password hashes. It should
  be in `.gitignore` and removed from tracking (history rewrite is a separate, larger decision).
- No CSRF protection on any form.
- No password reset, no email verification.
- SQLite, no Alembic — schema changes are one-off `migrate_*.py` scripts (there are now eight of them).
- No rate limiting on login.
- `render.yaml` exists but there's no documented deploy/backup story.

---

## 7. Suggested next steps

1. **Resolve the working tree.** Finish or stash the GenProgression chord-block editor, and decide about the
   `home.html` mode-card copy. Everything else is blocked behind a dirty tree.
2. **Fix BUG-003** and reconcile `BUGS.md`. Small, and BUG-003 makes the `admin_teacher` role unusable through
   the UI.
3. **Build Phase 2 adaptivity.** It's the largest unbuilt piece of the original design, it's the most
   pedagogically interesting, and the two core functions are pure and easily test-driven.
4. **Grow content** — more harmonic progressions and holistic exercises, or build the rhythm generator to
   automate part of it.
5. **Decide about absolute pitch training** — rebuild or remove the plan doc.
6. **Stop tracking the database file** before anything gets deployed or shared.

*dev thought: next step should be to make manually uploading exercises and creating student modules and managing school systems as easy as possible 