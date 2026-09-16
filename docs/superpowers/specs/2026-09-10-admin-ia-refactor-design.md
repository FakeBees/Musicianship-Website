# Admin Information-Architecture Refactor — Design

Date: 2026-09-10
Restore point: tag `pre-admin-refactor` on `main` (commit `57b3e20`)
Work branch: `refactor/admin-ia`

## 1. Problem

The student-facing side of the site is coherent. The admin side is not. An audit of all
97 routes, 24 admin templates and the four test suites found that the logic is sound —
the mess is in information architecture and the template layer.

### 1.1 What is already good (do not "fix" these)

- **Authorization is well designed.** A coarse global `role_required` gate plus a real
  per-school `require_school_role` check, an `outranks_in_school` "strictly below" rule,
  and a perspective system hard-capped at the account's real role. 137 tests pass.
- **No broken links.** Zero broken `url_for` targets, zero broken `render_template`
  targets, zero orphan templates.
- **`screens.py` is a genuine safety net.** `tests/test_screens.py` fails if the registry,
  the app's routes, the template files and `SCREEN_MAP.drawio` disagree. Any route move is
  therefore self-checking.
- **Two filter differences are correct, not drift.** `Container` is a melody-only foreign
  key and `GenProgression` has no tags table. Melody-only `container` and
  gen-progression-only `mode` filters are right. Do not flatten them.

### 1.2 The root cause

School-staff work is scattered across two unrelated prefixes, and `/admin` serves two
different audiences:

| Currently at | Actually is |
|---|---|
| `/admin/melodies`, `/admin/users`, `/admin/schools` … | Platform + content library (site admin) |
| `/admin/schools/<id>/detail`, `/admin/courses/*`, `/admin/modules/*` | School curriculum + roster |
| `/teacher/sections/<id>/set_course`, `/overrides/*`, `/modules/<id>/hide` … | School curriculum, again |

Because of this, the word **"Admin" in the nav goes to two different destinations**: site
admins land on `/admin`; school admins land on `/admin/my-school`, which redirects to a
school detail page. Same label, different mental model.

### 1.3 Confirmed defects

| # | Defect | Evidence |
|---|---|---|
| D1 | Add form and edit modal for a module exercise expose **complementary** field sets. Add renders the exercise picker + clef/min-dur filters but not `difficulty`/`key_signature`; edit renders `difficulty`/`key_signature` but not clef/min-dur. Both handlers accept the same fields. So difficulty and key signature can never be set at creation, and clef/min-dur can never be changed after it. | `templates/admin/module_exercises.html` lines 12–180 vs 293–386; handlers at `app.py:1535` and `app.py:1632` |
| D2 | **15 of 24 admin templates have no back link.** Every edit and upload page is a dead end. `harmonics.html` is the only list page missing one while its four siblings have "← Admin". `schools.html` says "← Admin Home" where the rest say "← Admin". | `templates/admin/*.html` |
| D3 | Admin hub is incoherent: the **Users** card is a dead stat while the Users link hides inside the *Schools* card; the **Sections** card is a dead stat; **Gen Progressions** is filed under "Site Overview" instead of Exercise Library; **Courses and Modules are not linked at all**, so the curriculum tree is reachable only by drilling through Schools. | `templates/admin/index.html` |
| D4 | **Melodies is the only content type with no difficulty filter**, despite showing a Diff column. | `admin_melodies` accepts `q`, `tag`, `container`; its three siblings accept `q`, `tag`, `difficulty` |
| D5 | Visibility column appears on harmonics and holistic only, though all four edit forms expose a visibility field. Delete button reads "Del" on four pages and "Delete" on harmonics. | list templates + `*_edit.html` |
| D6 | `class_teacher` has **permission without a path**: `/admin/schools/<id>/detail` allows the role, but the nav gives it no admin entry. | `app.py:1714`, `templates/base.html:43-50` |
| D7 | Four hardcoded `/admin/...` hrefs bypass `url_for`. | `templates/admin/index.html`, `templates/admin/melodies.html` |
| D8 | `BUGS.md` lists BUG-001/002/003 as open. All three are fixed; BUG-003's fix is in `admin_my_school()` with a docstring explaining it. | `BUGS.md` vs `app.py:2993` |
| D9 | URL segment style is inconsistent: `/admin/module_exercises` (underscore) vs `/admin/gen-progressions` (hyphen). | route table |
| D10 | **Entities listed in lists are not clickable.** Worst case: on "Your Classrooms" the only affordance per row is a red **Leave** button — the classroom name is plain text, the course name is plain text, and `/section/<id>` exists and the viewer is a member. The sole action offered on your own classroom list is the destructive one. | `templates/student/my_sections.html:43`; see §2.6 for the full list |

### 1.4 Defects found while writing the admin guides (2026-09-14)

Writing `docs/guides/` meant checking every admin screen against the running code, which surfaced these.
**Method** says how each was established: *execution* means reproduced through the real routes against
an in-memory database (the dev database was checksummed before and after every run and never changed);
*code* means the behaviour follows deterministically from reading the source.

| # | Defect | Method |
|---|---|---|
| D11 | *(fixed in Phase 1b)* School admins could delete a section but not open it. | execution |
| D12 | **Hide / Hide module do nothing for students.** `teacher_hide_module` and the per-exercise override form both write `action='hide'`, but `curriculum.effective_exercises()` only recognises `remove`, `override` and `add`. No UI path writes `remove` or `override` at all. The teacher sees "hidden"; students still see and complete the work. | execution |
| D13 | The section Edit page shows School-Admin-only controls to Section Teachers: the **Assign Section Teacher** card and the **Delete Section** link. Both lead to 403. | execution |
| D14 | **A Section Teacher saving Section Settings removes the section's course.** The course `<select>` is built from `administered_courses()`, which is empty for a Section Teacher, so the form posts no course and `teacher_edit_section` sets `course_id = None`. Every student loses their modules. Completion records survive, so re-choosing the course restores it. | execution |
| D15 | "+ Add exercise to this section only" requires a numeric exercise ID that no page shows — admin lists show the public ID (`MEL-0012`), a different value. | code |
| D16 | Internal role strings (`class_teacher`, `admin_teacher`) are rendered on the users and school pages, and the school page calls School Admins "administrative teachers" while `ROLE_LABELS` says "School Admin". | code |
| D17 | "← Schools" on `admin/courses.html` links to `admin_schools` (site-admin only), so it 403s for School Admins. (`school_detail.html` gates its equivalent link correctly.) | execution |
| D18 | Visibility offers `public` / `private`, but `_visible_exercise_filter` only admits `public` and `school`. `private` therefore hides content from every student and from every filter-based module exercise; `school` is unreachable from the UI. | code |
| D19 | **Deleting a school with members returns 500.** `db.session.delete(school)` tries to null `school_membership.school_id` (NOT NULL). The transaction rolls back, so nothing is lost. | execution |
| D20 | **Deleting a typical user returns 500** — reproduced for both a section owner and a plain student with a school membership. Nothing is deleted. | execution |
| D21 | Deleting a course permanently deletes every `ModuleCompletion` on it and leaves sections with `course_id = None`. The confirmation reads only *"and all its modules?"* | execution |
| D22 | *(fixed 2026-09-16)* Nav **Sections I Teach** opened a page titled *My Sections*, and nav **My Sections** opened a different page with the same title. A site-wide audit found the same class of problem in several more places. All fixed, and generalised into the **page identity rule** below. | execution |

**Page identity rule** (owner's words: *"the web pages should be clear about what they are"*). Enforced by
five tests in `tests/test_template_contracts.py`:

1. A menu item opens a page with the same name.
2. No two different pages share a main heading (`<h1>`/`<h2>`) or a browser-tab title.
3. Every page has a main heading — a page without one fails the check rather than being skipped. Use
   `<h2 class="h5">` for a heading that should look small.
4. Each Admin dashboard card is named after the page its **Manage →** opens.

Pages renamed to satisfy it: *Sections I Teach*; *<section> — Roster*; *Sandbox*; the Melodic Dictation
library tab; *<school> — Manage School* (and the schools list's **Details** button became **Manage School**);
*Upload Melody from MIDI*; *Melodic Exercise*; the dashboard's *Chord Progressions*, *Holistic Exercises* and
*GenProgressions* cards; a classroom's *<section> — Modules*; courses/modules/exercises tab titles now name
their school/course/module; the three confirm dialogs gained real headings; *Melodic Results* and *Rhythm
Results*.

Deliberately unchanged: the harmonic and holistic results pages have distinct tab titles but no top heading,
and adding one would be a visible layout change on the student side. They aren't in the tests' page set.
| D23 | Module-exercise **Clef** and **Shortest Note Value** filters are read by no handler, and `_apply_exercise_filters` has no branch for them. *(Phase 1 follow-up.)* | code |
| D24 | The module-exercise live match counter ignores Difficulty for melody/rhythm (`LIB_DIMS` omits it) and honours the ignored Clef / Shortest Note Value filters. *(Phase 1 follow-up.)* | execution (jsdom) |
| D25 | Ticking more than one Time Signature posts no time-signature filter at all, while the counter shows the union. | execution (jsdom) |
| D26 | New schools are created with no join code (`School(name=name)`), so nobody can join until someone presses Regenerate. | code |
| D27 | A student joining a section before its school is told *"Ask your teacher for the school join code"*, but Section Teachers are never shown it. | execution |

Also stale: several `condition` notes in `screens.py` predate Phase 1/1b — `SCHOOL_ADMIN_ENTRY` still describes
BUG-003, and `TEACHER_SECTION_DETAIL` / `TEACHER_SECTION_DELETE` predate D11. `tests/test_screens.py` checks
names and access levels, not condition text, so nothing caught the drift.

## 2. Design

### 2.1 Three prefixes, one per job

| Prefix | Job | Who | Design language |
|---|---|---|---|
| `/admin/*` | Run the platform | site admin only | Dense power-tool |
| `/manage/*` | Run **one school** | school staff + site admin | Guided |
| `/teacher`, `/section/*`, `/my-sections`, practice | Teach & learn | everyone | Unchanged |

The access rule falls out of existing code: `/manage/*` always acts on one specific
school and is gated by `require_school_role`, which already grants site admins blanket
authority via `effective_school_role`. **No new authorization concepts are introduced.**

This also clarifies a distinction that is currently muddy: `/manage/sections/<id>`
administers a section, `/section/<id>` participates in one. Today those are
`/teacher/section/<id>` and `/section/<id>`, which read as near-synonyms.

### 2.2 Route map

**Stays on `/admin/*` (site admin only)** — `/admin`, `/admin/users`,
`/admin/users/<id>/delete`, `/admin/schools` (list/create), `/admin/schools/<id>/delete`,
and the whole content library: `/admin/melodies*`, `/admin/rhythms*`,
`/admin/harmonics*`, `/admin/holistic*`, `/admin/gen-progressions*`.

**Moves from `/admin/*` to `/manage/*`:**

| From | To |
|---|---|
| `/admin/my-school` | `/manage` (hub) |
| `/admin/schools/<id>/detail` | `/manage/schools/<id>` |
| `/admin/schools/<id>/add-member` | `/manage/schools/<id>/members/add` |
| `/admin/schools/<id>/remove-member` | `/manage/schools/<id>/members/remove` |
| `/admin/schools/<id>/set-member-role` | `/manage/schools/<id>/members/set-role` |
| `/admin/schools/<id>/set-admin` | `/manage/schools/<id>/members/set-admin` |
| `/admin/schools/<id>/regen-join-code` | `/manage/schools/<id>/join-code/regenerate` |
| `/admin/schools/<id>/courses` | `/manage/schools/<id>/courses` |
| `/admin/courses/<id>/modules` | `/manage/courses/<id>/modules` |
| `/admin/courses/<id>/rename`, `/duplicate`, `/delete` | `/manage/courses/<id>/…` |
| `/admin/courses/<id>/sections` | `/manage/courses/<id>/sections` |
| `/admin/modules/<id>/exercises`, `/delete` | `/manage/modules/<id>/…` |
| `/admin/module_exercises/<id>/edit`, `/delete`, `/duplicate` | `/manage/module-exercises/<id>/…` |

**Moves from `/teacher/*` to `/manage/*`:**

| From | To |
|---|---|
| `/teacher/section/new` | `/manage/sections/new` |
| `/teacher/section/<id>` | `/manage/sections/<id>` |
| `/teacher/section/<id>/edit` | `/manage/sections/<id>/edit` |
| `/teacher/sections/<id>/delete` | `/manage/sections/<id>/delete` |
| `/teacher/sections/<id>/set_course` | `/manage/sections/<id>/set-course` |
| `/teacher/sections/<id>/assign-teacher` | `/manage/sections/<id>/assign-teacher` |
| `/teacher/section/<id>/kick/<uid>` | `/manage/sections/<id>/members/<uid>/remove` |
| `/teacher/sections/<id>/overrides/add` | `/manage/sections/<id>/overrides/add` |
| `/teacher/sections/<id>/overrides/<sme_id>/delete` | `/manage/sections/<id>/overrides/<sme_id>/delete` |
| `/teacher/sections/<id>/modules/<mid>/hide`, `/restore` | `/manage/sections/<id>/modules/<mid>/…` |
| `/teacher/sections/<id>/module_exercises/add` | `/manage/sections/<id>/module-exercises/add` |

**Stays put:** `/teacher` (the "Sections I Teach" dashboard) and every `/section/*`,
`/my-sections`, `/join-school` and practice route.

All new segments use hyphens, fixing D9. View functions for moved routes are renamed
`admin_*` → `manage_*`; screen names `ADMIN_*` → `MANAGE_*`.

No redirects from old paths, consistent with the precedent set by the class → section
rename in `docs/NAMING.md`.

### 2.3 Navigation

Two labels for two destinations, replacing the overloaded "Admin":

| Role | Nav entries |
|---|---|
| student | My Progress · My Classrooms · Home |
| class_teacher | Sections I Teach · My Sections · **Manage School** · Home · My Progress |
| admin_teacher | Sections I Teach · My Sections · **Manage School** · Home · My Progress |
| admin | Sections I Teach · My Sections · **Manage School** · **Site Admin** · Home · My Progress |

"Manage School" appears for anyone holding a school role of `class_teacher` or above,
which closes D6. `/manage` resolves to the single school when the user has one, and shows
a school picker when they have several (site admins always get the picker).

### 2.4 Shared list template

The five content list pages collapse to one template driven by a per-type spec declaring
columns, filters and actions:

- **Shared core filters:** `q`, `difficulty`
- **`tag`** wherever the model has a tags relationship (melody, rhythm, harmonic,
  holistic — *not* gen-progression)
- **Type-specific extras:** `container` (melody only), `mode` (gen-progression only)
- **Shared columns:** ID, Name, Diff, Visibility, Tags, plus type-specific columns

This closes D4 by giving melodies the difficulty filter, and D5 by rendering the
Visibility *column* and one delete affordance on all five pages. A visibility *filter* is
deliberately not added — it is a two-value field and the column plus search covers it.

### 2.5 Two design languages

- **`/admin/*` — dense.** Compact tables, inline edit, bulk tag/visibility actions,
  keyboard navigation, "save and add another" on upload forms. Optimised for authoring
  content in volume, matching the `docs/ROADMAP.md` note about making upload and module
  creation as fast as possible.
- **`/manage/*` — guided.** Breadcrumbs, explanatory empty states, confirmations,
  progressive disclosure. Optimised for school staff who log in occasionally.

A `breadcrumbs` block in `base.html` replaces ad-hoc "← Admin" links, closing D2. The
curriculum tree (School → Course → Module → Exercises) genuinely needs it.

### 2.6 Clickability (cross-cutting)

**Principle: if the viewer has permission to reach an entity, its name in a list is a link
to it.** This applies everywhere — admin lists, teacher lists, student lists.

`templates/home.html` already implements this correctly by wrapping the whole card in an
`<a>`. That is the precedent; propagate it rather than inventing a new pattern.

Rules:

1. **The entity name is the link** — or the whole card, following the `home.html` precedent.
   Not merely a trailing button in a separate actions column.
2. **The destination is the highest-privilege page the viewer can actually reach** for that
   entity: can manage → its manage/edit page; can only participate → its detail page;
   nothing reachable → **plain text, never a dead link**.
3. **A destructive action must never be the only affordance on a row.** This is the D10 bug.
4. Resolution lives in **one** template global, `primary_link(entity)`, returning a URL or
   `None`, so the mapping cannot drift per-template the way the list pages did.

Applies to:

| Template | Entity | Destination |
|---|---|---|
| `student/my_sections.html` | section name | `/section/<id>`; course name → its module list |
| `student/my_sections.html` | "Your schools:" names | school page if staff, else plain |
| `teacher/dashboard.html` | section card title | section detail |
| `admin/schools.html` | school name | `/manage/schools/<id>` |
| `admin/courses.html` | course name | `/manage/courses/<id>/modules` |
| `admin/modules.html` | module name | `/manage/modules/<id>/exercises` |
| `admin/course_sections.html` | section name | `/manage/sections/<id>` |
| `admin/{melodies,rhythms,harmonics,holistic_list,gen_progressions}` | name | its edit page |
| `admin/module_exercises.html` | exercise name | its edit modal |
| `admin/users.html`, `admin/school_detail.html` | user email | **stays plain — no user-detail page exists** |

Creating a user-detail page is explicitly **out of scope**; those two stay plain text so
the refactor introduces no dead links.

## 3. Phases

Each phase is independently shippable and leaves the suite green.

- **Phase 0 — Make the tree safe.** *(done)* Checkpoint commit, `pre-admin-refactor` tag,
  work branch. Remaining: reconcile `BUGS.md` (D8); decide whether to gitignore
  `static/melodic/_preview/`.
- **Phase 1 — Real bugs, no restructuring.** D1 (module-exercise field parity via one
  shared partial), D4 (melodies difficulty filter), D6 (`class_teacher` nav entry), and the
  acute half of D10 — `my_sections.html` and `teacher/dashboard.html`, which need no new
  routes and where a destructive button is currently the only affordance.
- **Phase 2 — Unify the library pages.** The shared list template of §2.4. Closes D5, D7,
  and the content-library rows of D10 (name → edit page).
- **Phase 3 — The split.** Introduce `/manage/*`, move the routes of §2.2, update
  `screens.py` and `SCREEN_MAP.drawio` in the same commit. Closes D9.
- **Phase 4 — Hubs, breadcrumbs, design languages, clickability.** Rebuild the `/admin` hub
  (D3), build the `/manage` hub, add the breadcrumb block everywhere (D2), apply §2.5, and
  land the `primary_link()` global across the remaining lists (rest of D10 — deferred to
  here because its admin destinations are the `/manage/*` routes Phase 3 creates).
- **Phase 5 — Optional: blueprints.** `app.py` is 3538 lines and 97 routes. The blueprints
  map exactly onto the three prefixes, so Phase 3 does the hard thinking and this files it.

Phases 0–2 fix everything broken without touching a single URL. Phases 3–4 are the
restructure. Phase 5 is optional.

## 4. The safety property

**Routes move; guards do not change.** The refactor must not alter a single authorization
outcome. The proof is that `tests/test_school_authority.py` (46 tests) and
`tests/test_perspective.py` (29 tests) keep passing with only endpoint names updated —
never an assertion about who may do what.

Any change to an authorization outcome is out of scope and must be raised separately.

## 5. Testing

- `tests/test_screens.py` enforces registry ↔ routes ↔ templates ↔ diagram agreement, so
  Phase 3 cannot silently half-finish.
- `tests/test_template_contracts.py` guards the template layer through Phases 1, 2 and 4.
- The 75 authorization tests are the §4 safety property.
- New tests: field parity between the module-exercise add and edit forms (D1); presence of
  a breadcrumb on every admin and manage page (D2); the per-type list spec (D4, D5).

Full suite must be green at the end of every phase.

## 6. Rollback

| To do this | Run |
|---|---|
| Return to the pre-refactor state | `git switch main` |
| Discard the refactor entirely | `git branch -D refactor/admin-ia` |
| Hard reset to the restore point | `git reset --hard pre-admin-refactor` |

## 7. Out of scope

- Phase 2 adaptivity (EMA mastery, auto-leveling, SM-2-lite). Untouched by this work.
- The database schema rename (`class` → `section` physical tables). `docs/NAMING.md`
  documents the deliberate Python/SQL divergence; this refactor does not change it.
- The `class_teacher` role *string* stored in `User.role`.
- Resolving the 99-ahead / 2-behind divergence with `origin/main`, and the stale worktree
  at `.claude/worktrees/agent-a4de1215`. Both flagged, neither touched.
