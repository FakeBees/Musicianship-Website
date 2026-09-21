# Bug Round + Section Content Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the open admin bugs, let Section Teachers build their own section's curriculum with the full course-exercise tools, and make school / user / course deletion work — cascading, behind three confirmation pages.

**Architecture:** Section-owned content lives in the existing `module` and `module_exercise` tables, tagged with a new nullable `section_id` (physical column `class_id`, already migrated — commit `0c22646`). That lets section exercises reuse the course form, launcher and completion tracking unchanged. Deletions go through one set of cascade helpers.

**Tech Stack:** Flask, Flask-SQLAlchemy, Flask-Login, Jinja2, Bootstrap 5, pytest.

**Spec:** `docs/superpowers/specs/2026-09-10-admin-ia-refactor-design.md` §1.4 (D12–D27).

## Decisions made by the project owner (2026-09-21)

- **Section Teachers can add section-specific modules and exercises.**
- **Adding an exercise to a section works exactly like adding one to a course** — the same full form: type, name, order, completion rule, filters, holistic picker.
- **Deleting a school, a user, or a course cascades** — it deletes their sections and progress with them.
- **Those three deletes go through three separate confirmation pages:** *are you sure?* → *here's everything it will delete — are you sure?* → *are you really sure?*
- **Section Teachers see the school join code.**
- D18 (what "private" visibility means) is **not decided** — out of scope for this round.

## Global Constraints

- **Never write to `instance/musicianship.db`.** The suite runs in-memory via `tests/conftest.py`; `.venv/bin/python -m pytest -q` is safe. Never run the app against the real database. The schema migration is already done.
- `timeout` is not available on this machine.
- Baseline: **167 passing** at `0c22646`. Every task ends strictly higher.
- **TDD, with RED proven.** Write the tests first, run them, and confirm they fail *for the reason in their name* before implementing. In this project a first-draft assertion has repeatedly passed against unfixed code.
- `tests/test_school_authority.py` and `tests/test_perspective.py`: **existing assertions stay unmodified and passing.** You may append new tests to them. **One exception, Task 5 only:** `test_adding_an_exercise_affects_only_this_section` checks the *mechanism* this round deliberately replaces (it asserts no `ModuleExercise` row is written). Task 5 rewrites that one test to assert the same *invariant* — other sections and the course are untouched — under the new design. No other existing assertion in either file may change.
- No test helper named `login()` exists. Use `client_as(uid)` (`tests/test_template_contracts.py`) or `client_for(user)` (`tests/test_school_authority.py`). **One client per user per test** — these files leak `current_user` across clients within one app context.
- **Page identity rule** (enforced by tests): a menu item opens a page with the same name; no two different pages share a main `<h1>`/`<h2>` or a tab title; every page has an `<h1>`/`<h2>` (`<h2 class="h5">` to look small). New pages must follow it, and must be added to the uniqueness tests' page set.
- **Clickability rule:** an entity's name in a list links to it when the viewer can reach it; never a dead link.
- **`screens.py` and `docs/SCREEN_MAP.drawio` must agree** (`tests/test_screens.py`). A new *page* (anything rendering a template) needs a `screens.py` entry **and** a box on the map: copy an existing page box's `mxCell` in the `.drawio`, give it a unique `id` and a clear spot, and put the new name in the same `face='monospace'>NAME<` label format. A new POST-only *action* needs only a `screens.py` entry. Removing a route means removing its entry.
- Templates use `url_for`, never hardcoded paths. Staff copy uses `{{ section_term }}` / `{{ section_terms_title }}`, never hardcoded "Section"/"Classroom". Role names shown to people use `ROLE_LABELS` / `role_labels`, never raw `class_teacher`.
- Commit at the end of each task; last line `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

---

### Task 1: Small fixes — D14, D13, D17, D26, D16, D27, BUGS.md, stale screen notes

**D14 — a Section Teacher saving Section Settings wipes the course.** In `teacher_edit_section`, only a caller for whom `can_manage_section(section)` is true may change the course; for anyone else the POST keeps `section.course_id` exactly as it was, whatever the form sent. In `teacher/edit_section.html`, a non-manager sees the current course as read-only text (with *"Ask your School Admin to change it"*) instead of the `<select>`. Test: a Section Teacher renames a section → name changes, course unchanged. Also test that a manager can still change and clear the course.

**D13 — School-Admin-only controls shown to Section Teachers.** On `teacher/edit_section.html`, render the **Assign Section Teacher** card and the **Delete Section** link only when `can_manage`. Test: a Section Teacher's Edit page contains neither; a School Admin's contains both.

**D17 — "← Schools" on the courses page is Forbidden for School Admins.** In `admin/courses.html`, make the back link go to the school's own page (`admin_school_detail`), labelled with the school's name. Test: every `←` link on the courses page returns 200 for a School Admin.

**D26 — new schools have no join code.** `admin_schools` POST creates the school with a join code from `_random_school_code()`, retrying until it's unused (`School.join_code` is unique). Test: a newly created school has a non-empty join code.

**D16 — internal role names shown to people.** Everywhere a role is displayed, show its `ROLE_LABELS` label: *"Your role here"*, the Members table's role column, the role `<select>` option **text** (values stay raw), the *"You can grant roles below your own (…)"* help text, the users page's role column, and flash messages from add-member, set-member-role, set-school-admin and assign-teacher. Rename the school page's **Administrative teachers** card to **School Admins**, its button to **Make School Admin**, and its help/flash text to match. Test: the school page and users page never contain `class_teacher` or `admin_teacher` as visible text (they may appear in `value=""` attributes).

**D27 — Section Teachers see the school join code.** On `admin/school_detail.html`, show the join code to Section Teachers too; **Regenerate** stays School-Admin-and-above. Also show the school join code on a section's roster page (`teacher/section_detail.html`) next to the section join code, when the section belongs to a school, labelled so it's clear students use the school code first. Tests: a Section Teacher sees the school code on both pages and has no Regenerate button.

**BUGS.md.** Mark BUG-001, BUG-002 and BUG-003 fixed, each with a one-line note of how and the date: BUG-001/002 fixed 2026-03-19 (Tone.js direct scheduling; figured-bass Roman numerals); BUG-003 fixed before 2026-09-10 (`admin_my_school` now lands staff on their school page).

**`screens.py` stale notes.** Rewrite the `condition` text for `SCHOOL_ADMIN_ENTRY` (no longer BUG-003; now lands any staff member on their school page), `TEACHER_SECTION_DETAIL` and `TEACHER_SECTION_EDIT` (section authority: in-section Section Teacher or owner, or a School Admin of the section's school), and `TEACHER_SECTION_DELETE` (owner or School Admin of the section's school). Where a route's actual gate differs from its `access` level, correct the level.

---

### Task 2: Module-exercise filters that work — D23, D24, D25 — and a reusable form

**D23 — Clef and Shortest Note Value are ignored.** Store them: both module-exercise handlers read `request.form.getlist('clef_cb')` into `params['clef']` and `getlist('min_dur_cb')` into `params['min_duration']`. Apply them: `_apply_exercise_filters` filters `model.clef.in_(…)` and `model.min_duration.in_(…)` when the model has the column (melody has both; rhythm has `min_duration` only). **First confirm the checkbox values in `_module_exercise_fields.html` are the same codes stored in `Melody.clef` / `Melody.min_duration` / `Rhythm.min_duration`** (e.g. `treble`, `q`) — the sandbox route near `app.py:901` filters the same columns; match it.

**D25 — several time signatures drop the filter.** Handlers read `getlist('time_signature_cb')`; store a list when more than one is ticked. `_apply_exercise_filters` accepts `time_signature` as either a string (existing stored rows) or a list (`in_`). The edit modal pre-ticks boxes from either shape.

**D24 — the live match counter is wrong.** Add `difficulty` to `melodies_data` and `rhythms_data` and to the counter's per-type dimensions, so the counter narrows by difficulty for every type. With D23 fixed the counter's clef/min-duration narrowing is now also true server-side.

**Reusable pieces for Task 5.** Extract, with no behaviour change:
- a helper that turns a submitted add/edit form into the module-exercise fields (type, exercise id, name, order, `params_json`, `completion_criterion_json`) — used by both course handlers;
- the exercise editor — the add form, exercises table, edit modal, and their `<script>` — out of `admin/module_exercises.html` into an include (e.g. `admin/_module_exercise_editor.html`) whose form actions and edit / duplicate / remove URLs are **passed in**, not hardcoded. This also removes the hardcoded `'/admin/module_exercises/'` path.

Tests: for each type, a module exercise saved with clef / min-duration / multiple time signatures launches only matching exercises (seed matching and non-matching library rows; a filter that matches nothing must produce the *"No exercises match"* path). The existing module-exercise tests (field parity, time-signature leak) keep passing.

---

### Task 3: Hiding actually hides — D12

Today hide rows (`SectionModuleExercise.action == 'hide'`) are written but `curriculum.effective_exercises()` never reads them.

- **Exercise-level hide** — `action='hide'`, `module_exercise_id` set. `effective_exercises()` skips it.
- **Module-level hide** — change `teacher_hide_module` to write **one** row: `action='hide'`, `module_id` set, `module_exercise_id` NULL. `teacher_restore_module` deletes it. `modules_with_progress()` skips hidden modules.
- **The launcher refuses hidden work:** `start_module_exercise` 404s for a hidden exercise or an exercise in a hidden module; `section_module_detail` 404s for a hidden module.
- The Edit page's hidden/restore state reads the new module-level row.

Tests, all as a **student**: a hidden exercise is absent from the module page and 404s when launched directly; a hidden module is absent from the module list and its page 404s; restoring brings each back. Existing progress on a hidden exercise isn't deleted.

---

### Task 4: Section content engine

The columns exist (commit `0c22646`). Wire them up:

- **Models.** `Module.section_id` and `ModuleExercise.section_id` → `db.Column('class_id', db.Integer, db.ForeignKey('class.id'), nullable=True)`. Add both to the mapping table in `docs/NAMING.md`.
- **Meaning.** `section_id IS NULL` → course content. `section_id = S` → section S's own. A section's own content is tied to the course it was made for (`Module.course_id`): while the section follows that course it's shown; if the section switches course it goes dormant, and returns if switched back.
- **`curriculum.py`.** For section S following course C: modules = `course_id == C and (section_id is NULL or section_id == S)`; a module's exercises = `module_id == M and (section_id is NULL or section_id == S)`, minus hides. Ordered by `order`.
- **Launcher.** `start_module_exercise` also accepts a section's own exercises, and 404s if `me.section_id` is set to a different section. Completion tracking already keys on `module_exercise_id` + section, so it needs no change.
- **Course-level pages exclude section content.** Anywhere course content is listed, counted, or copied for School Admins — `admin/courses.html` counts, `admin/modules.html`, `admin/module_exercises.html`, and **Duplicate course** — include only `section_id IS NULL`.

Tests: a section's own module and exercise appear to that section's students and launch; they do **not** appear to a second section following the same course, nor on the course's admin pages, nor in a duplicated course; switching the section's course hides them and switching back restores them.

---

### Task 5: Section curriculum pages — Section Teachers build their section's curriculum

New pages, under the section, reachable by anyone with `require_section_authority(section, 'class_teacher')` — the section's Section Teacher, its owner, a School Admin of its school, a Site Admin.

**`<section> — Curriculum`** (`/teacher/section/<id>/curriculum`):
- If the section has no course: say so, and that a School Admin must assign one.
- Lists the section's modules — the course's and its own — in order. Each name links to the module page. Mark which are *from the course* and which are *this section only*, and show each one's exercise count for this section.
- Course modules: **Hide module** / **Restore module**. The section's own modules: **Delete**, with a confirmation.
- **Add a module for this section only**: name + order → Add.

**`<section> — <module>`** (`/teacher/section/<id>/curriculum/modules/<module_id>`):
- Course exercises in this module, with **Hide** / **Restore** and a *Hidden* badge.
- This section's own exercises in this module, with **Edit**, **Duplicate**, **Remove** — the same table as the course page.
- **Add Exercise** — the full editor from Task 2, with this section's URLs. A new exercise is saved as a `ModuleExercise` with `section_id` set.
- On a section-own module, only the section's own exercises and the add form.

Edit / duplicate / remove are new section-scoped actions that check the exercise belongs to this section; delete-module checks the module belongs to this section. Reuse Task 2's form helper and Task 6's cascade helpers once they exist, or delete completions directly if Task 6 hasn't run yet.

**Wiring:**
- The section Edit page's *Section-Specific Overrides* card becomes a short card linking to **Curriculum**. The roster page and each **Sections I Teach** card get a **Curriculum** link.
- Retire the old raw-ID *"+ Add exercise to this section only"* form and its route `teacher_add_module_exercise` (and its `screens.py` entry). Leave `curriculum.py`'s support for old `action='add'` rows in place.
- Hide / restore routes return to whichever page the button was on.
- New pages get `screens.py` entries **and** `.drawio` boxes, and join the page-identity uniqueness tests.

Tests: a **Section Teacher** can add a section-only module, add a filter-based and a holistic exercise to it and to a course module, edit, duplicate and remove them, and a student in that section can launch them. A Section Teacher can't edit or remove another section's exercises, or course exercises (403). A student can't reach the curriculum pages (403).

**Rewrite `test_adding_an_exercise_affects_only_this_section`** in `tests/test_school_authority.py` (the one permitted change to that file). Keep its name and intent; replace the retired-route POST with the new add-exercise form, and assert: the course's own exercises (`section_id IS NULL`) are unchanged; the new exercise has `section_id` equal to this section; a **second section following the same course** doesn't see it. Prove it's a real guard: temporarily make the handler save with `section_id=None` and watch it fail, then restore.

---

### Task 6: Cascading deletes behind three confirmation pages — D19, D20, D21

**Cascade helpers**, used everywhere something is deleted:

```
_delete_module_exercise(me)  completions on it, override rows on it, the exercise
_delete_module(module)       each of its exercises (as above), its module-level
                             override rows, the module
_delete_section(section)     its own modules and exercises (as above), all
                             completions and override rows for it, its student
                             memberships, the section
_delete_course(course)       every section following it (as above), every module
                             of it — course and section-owned (as above), the course
_delete_school(school)       every course (as above), its memberships, the school;
                             then recalculate every former member's account role
_delete_user(user)           every section they own (as above); unassign them where
                             they're Section Teacher; remove them from sections;
                             their completions, their melodic / rhythmic /
                             harmonic / holistic attempts, their memberships, the user
```

**Before writing these, enumerate every foreign key** pointing at `user`, `school`, `course`, `module`, `module_exercise`, `class` and the attempt tables — including any child tables of attempts — and make sure each is handled. Test with a world containing every kind of dependent row: after each cascade, **no row anywhere references a deleted id**.

Use the helpers in the existing single-confirmation deletes too — section delete, module delete, module-exercise remove, and Task 5's section-module delete and section-exercise remove — so none of them orphan completion rows.

**Three confirmation pages** for deleting a **school**, a **user**, and a **course**. One shared template; the same endpoint serves every step:

1. `GET …/delete?step=1` — *"Delete <type> "<name>"? Are you sure?"* → **Continue** / **Cancel**
2. `GET …/delete?step=2` — everything it will delete, itemised with counts and names: sections by name and how many students are in them, courses, modules, exercises, progress records; for a school, that members' **accounts** are kept but their roles are recalculated. *"Are you sure?"* → **Continue** / **Cancel**
3. `GET …/delete?step=3` — *"Are you really sure? This can't be undone."* → **Delete permanently**, a POST carrying `step=3` / **Cancel**

`POST` performs the cascade only when `step=3` is posted; anything else deletes nothing and redirects to step 1. Each step has its own page heading (e.g. *"Delete Westfield — Step 2 of 3"*) and follows the page identity rule. The lists' **Delete** buttons (schools, users, courses) become links to step 1. Guards are unchanged: school and user deletes are Site Admin only; course delete needs School Admin of that school. You still can't delete your own account, at any step. These three endpoints become *pages* — update `screens.py` and add `.drawio` boxes.

Tests: deleting a school **with members** succeeds; members' accounts survive with recalculated roles; the school's courses, sections and progress are gone. Deleting a **student**, a **section owner**, and an **assigned Section Teacher** each succeed. Deleting a **course** deletes the sections following it. Step 2 lists what step 3 then deletes. A POST without `step=3` deletes nothing. Every step page renders with a heading.

---

## Done criteria

- Suite green, strictly above 167.
- Existing assertions in `test_school_authority.py` and `test_perspective.py` unmodified.
- `test_screens.py` green: registry, routes, templates and `.drawio` agree.
- Page identity tests green, including every new page.
