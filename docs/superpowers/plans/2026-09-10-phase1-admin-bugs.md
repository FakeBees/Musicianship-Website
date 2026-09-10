# Phase 1 — Real Admin Bugs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the four defects that are genuinely broken today, without changing a single URL.

**Architecture:** Four independent fixes against the existing Flask monolith. No route paths change, no authorization outcomes change, no new dependencies. Each task is self-contained and leaves the suite green.

**Tech Stack:** Flask, Flask-SQLAlchemy, Flask-Login, Jinja2, Bootstrap 5, pytest.

**Spec:** `docs/superpowers/specs/2026-09-10-admin-ia-refactor-design.md` (defects D1, D4, D6, D10)

## Global Constraints

- **Routes move, guards do not change.** No task may alter an authorization outcome. `tests/test_school_authority.py` (46 tests) and `tests/test_perspective.py` (29 tests) must pass **unmodified**.
- **No URL changes in this phase.** Route paths are Phase 3 work.
- Run the full suite with `.venv/bin/python -m pytest -q`. Baseline is **137 passing**. Every task must end green with a strictly higher count.
- `timeout` is not available on this machine — do not use it in commands.
- Templates must use `url_for`, never hardcoded paths.
- Section wording comes from `{{ section_term }}` / `{{ section_terms_title }}` etc. Never hardcode "class", "section" or "classroom" in user-visible template copy.
- New template tests belong in `tests/test_template_contracts.py` and must use its existing `world` and `strict_undefined` fixtures.
- Commit after each task with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` as the final line.

---

### Task 1: Give melodies the difficulty filter (D4)

Melodies is the only content type with no difficulty filter, despite rendering a Diff column. Its three siblings (`admin_rhythms`, `admin_harmonics`, `admin_holistic`) all accept `difficulty`. The melody-only `container` filter is **correct and must be kept** — `Container` is a melody-only FK.

**Files:**
- Modify: `app.py` — `admin_melodies()` at line 2053
- Modify: `templates/admin/melodies.html` — filter row
- Test: `tests/test_template_contracts.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `admin_melodies` accepts a `difficulty` query param (int, optional) and passes `diff_filter` to the template — matching the name `admin_rhythms` already uses.

- [ ] **Step 1: Read the sibling implementation first**

Read `admin_rhythms()` in `app.py` (around line 2342) and `templates/admin/rhythms.html`. Match its naming exactly: the query param is `difficulty`, the template variable is `diff_filter`. Do not invent new names.

- [ ] **Step 2: Write the failing test**

Add to `tests/test_template_contracts.py`:

```python
def test_admin_melodies_supports_difficulty_filter(client, world, strict_undefined):
    """Melodies must filter by difficulty like every other content type.

    It was the only list page without this, despite rendering a Diff column.
    """
    login(client, 'admin@t.com')
    resp = client.get('/admin/melodies?difficulty=3')
    assert resp.status_code == 200
    assert b'name="difficulty"' in resp.data, \
        'melodies.html must render a difficulty filter control'
```

Use whatever login helper `tests/test_template_contracts.py` already defines. If it defines none, read `tests/test_school_authority.py` and reuse that one rather than writing a third.

- [ ] **Step 3: Run it and confirm it fails**

```bash
.venv/bin/python -m pytest tests/test_template_contracts.py::test_admin_melodies_supports_difficulty_filter -v
```

Expected: FAIL — `name="difficulty"` not found in the response body.

- [ ] **Step 4: Add the filter to the route**

In `admin_melodies()`, mirror `admin_rhythms()`: read `difficulty` with `request.args.get('difficulty', type=int)`, apply `query.filter_by(difficulty=diff_filter)` when set, and pass `diff_filter=diff_filter` to `render_template`. Keep the existing `container` filter untouched.

- [ ] **Step 5: Add the control to the template**

In `templates/admin/melodies.html`, add a difficulty `<select>` to the existing filter row, copying the markup from `templates/admin/rhythms.html` so the two pages match. Keep the container select.

- [ ] **Step 6: Run the full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: 138 passed.

- [ ] **Step 7: Commit**

```bash
git add app.py templates/admin/melodies.html tests/test_template_contracts.py
git commit -m "fix: add difficulty filter to admin melodies list (D4)

Melodies was the only content type without a difficulty filter, despite
rendering a Diff column. Matches admin_rhythms naming exactly. The
melody-only container filter is kept — Container is a melody-only FK.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Give `class_teacher` a reachable school entry (D6)

`/admin/schools/<id>/detail` allows `class_teacher`, but `templates/base.html` gives that role no admin nav entry — so the permission is unreachable through the UI.

**Files:**
- Modify: `templates/base.html` — nav dropdown, lines 43-50
- Modify: `app.py` — `admin_my_school()` at line 2993
- Test: `tests/test_template_contracts.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `admin_my_school()` resolves for `class_teacher` as well as `admin_teacher`.

- [ ] **Step 1: Write the failing test**

```python
def test_class_teacher_has_a_reachable_school_link(client, world, strict_undefined):
    """A class_teacher may view school detail, so the nav must offer a way in.

    The permission existed with no path to it: /admin/schools/<id>/detail
    allows class_teacher, but base.html gave the role no entry at all.
    """
    login(client, 'ct@t.com')          # the class_teacher in the world fixture
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'/admin/my-school' in resp.data, \
        'class_teacher nav must link to the school entry point'


def test_class_teacher_my_school_does_not_403(client, world, strict_undefined):
    login(client, 'ct@t.com')
    resp = client.get('/admin/my-school', follow_redirects=True)
    assert resp.status_code == 200
```

Check the `world` fixture for the actual `class_teacher` email and use it; `ct@t.com` is a guess.

- [ ] **Step 2: Run and confirm both fail**

```bash
.venv/bin/python -m pytest tests/test_template_contracts.py -k class_teacher -v
```

Expected: FAIL on both.

- [ ] **Step 3: Widen the route guard**

Change `admin_my_school()`'s decorator from `@role_required('admin_teacher', 'admin')` to `@role_required('class_teacher', 'admin_teacher', 'admin')`.

Then widen its body: it currently looks up a membership with `role='admin_teacher'` only. Make it fall back to **any** membership, so a `class_teacher` lands on the school detail page they are permitted to see. Preserve the existing site-admin branch and the existing no-membership flash.

**This does not change an authorization outcome** — `/admin/schools/<id>/detail` already allowed `class_teacher` and `require_school_role` still gates the destination. It only makes the existing permission reachable.

- [ ] **Step 4: Add the nav entry**

In `templates/base.html`, the `{% elif active_role in ('admin_teacher', 'class_teacher') %}` branch currently wraps the Admin link in an inner `{% if active_role == 'admin_teacher' %}`. Remove that inner condition so both roles get the entry. Label it `Manage School` — this is the label Phase 4 standardises on, so adopting it now avoids renaming twice.

- [ ] **Step 5: Run the full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: 140 passed. **`test_school_authority.py` and `test_perspective.py` must pass unmodified.** If either fails, you changed an authorization outcome — stop and report rather than editing those tests.

- [ ] **Step 6: Commit**

```bash
git add app.py templates/base.html tests/test_template_contracts.py
git commit -m "fix: give class_teacher a reachable school entry point (D6)

/admin/schools/<id>/detail already allowed class_teacher, but base.html
gave the role no nav entry, so the permission was unreachable. Widens the
admin_my_school guard and membership lookup to match the permission that
already existed. require_school_role still gates the destination, so no
authorization outcome changes.

Labelled 'Manage School' to match the Phase 4 target and avoid renaming twice.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Make listed entities clickable (D10, acute half)

On "Your Classrooms" the only affordance per row is a red **Leave** button. The classroom name is plain text, the course name is plain text, and `/section/<id>` exists with the viewer as a member. `templates/home.html` already does this correctly by wrapping the card in an `<a>` — **that is the precedent to follow.**

**Files:**
- Modify: `templates/student/my_sections.html` — lines 40-52
- Modify: `templates/teacher/dashboard.html` — line 22
- Test: `tests/test_template_contracts.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: nothing later tasks depend on. The `primary_link()` global is **Phase 4** — do not build it here.

- [ ] **Step 1: Write the failing tests**

```python
def test_my_sections_links_each_section(client, world, strict_undefined):
    """A student's own classroom list must let them open a classroom.

    The only affordance per row was a destructive Leave button.
    """
    login(client, 'student@t.com')
    resp = client.get('/my-sections')
    assert resp.status_code == 200
    body = resp.data.decode()
    assert '/section/' in body, 'section name must link to the section'
    leave_at = body.find('Leave')
    link_at = body.find('/section/')
    assert link_at < leave_at, \
        'a destructive action must not be the only or first affordance'


def test_teacher_dashboard_links_each_section(client, world, strict_undefined):
    login(client, 'at@t.com')
    resp = client.get('/teacher')
    assert resp.status_code == 200
    assert b'teacher_section_detail' not in resp.data  # url_for is resolved
    assert b'/teacher/section/' in resp.data
```

Confirm the student's email against the `world` fixture before running.

- [ ] **Step 2: Run and confirm they fail**

```bash
.venv/bin/python -m pytest tests/test_template_contracts.py -k "links_each_section" -v
```

Expected: FAIL.

- [ ] **Step 3: Link the section name in `my_sections.html`**

Wrap `<strong>{{ section.name }}</strong>` in an `<a href="{{ url_for('section_modules', section_id=section.id) }}">`. Use `section_modules` — it is where `home.html` already sends students for a section, so the two agree.

If `section.course` exists, link the course name to the same destination rather than leaving it as dead grey text.

Keep the Leave button, but it must no longer be the only affordance.

- [ ] **Step 4: Link the school names in `my_sections.html`**

The "Your schools:" line renders `<strong>{{ m.school.name }}</strong>` as plain text. Leave it plain for students — there is no student-facing school page. Do **not** invent one.

- [ ] **Step 5: Link the section card title in `teacher/dashboard.html`**

Wrap `{{ section.name }}` in the card title with an `<a href="{{ url_for('teacher_section_detail', section_id=section.id) }}" class="text-decoration-none">`. The footer buttons stay as they are.

- [ ] **Step 6: Run the full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: 142 passed.

- [ ] **Step 7: Commit**

```bash
git add templates/student/my_sections.html templates/teacher/dashboard.html tests/test_template_contracts.py
git commit -m "fix: make listed sections clickable (D10, acute cases)

On 'Your Classrooms' the only affordance per row was a destructive Leave
button — the name was plain text while /section/<id> existed and the
viewer was a member. Same on the teacher dashboard card title.

Follows the existing home.html precedent rather than inventing a pattern.
The general primary_link() global is Phase 4.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Module-exercise add/edit field parity (D1)

`templates/admin/module_exercises.html` has an add form (lines 12-180) and an edit modal (lines 293-386) for the same object, exposing **complementary** field sets:

- Add renders the exercise picker + `clef_cb` / `min_dur_cb`, but **not** `difficulty` or `key_signature`
- Edit renders `difficulty` / `key_signature`, but **not** clef / min-dur

Both handlers (`app.py:1535` and `app.py:1632`) read the *same* fields. So difficulty and key signature can never be set at creation, and clef / min-dur can never be changed after it.

**Files:**
- Create: `templates/admin/_module_exercise_fields.html`
- Modify: `templates/admin/module_exercises.html`
- Test: `tests/test_template_contracts.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: a Jinja partial included by both the add form and the edit modal. It takes one variable, `mode`, which is `'add'` or `'edit'`, used only to namespace element `id` attributes so the two copies on one page do not collide. Field `name` attributes are **identical** in both modes — that is the point of the task.

- [ ] **Step 1: Write the failing test**

```python
CRITERION_FIELDS = [
    'name', 'order', 'category', 'tag', 'criterion_type',
    'completion_attempts', 'completion_min_score', 'completion_passing',
    'time_signature', 'difficulty', 'key_signature',
]


def test_module_exercise_add_and_edit_expose_the_same_fields(
        client, world, strict_undefined):
    """The add form and the edit modal must accept the same fields.

    They had complementary gaps: difficulty and key_signature could never be
    set at creation, and clef / min_dur could never be changed after it,
    even though both handlers read the same fields.
    """
    login(client, 'admin@t.com')
    resp = client.get(f'/admin/modules/{world["module_id"]}/exercises')
    assert resp.status_code == 200
    body = resp.data.decode()

    for field in CRITERION_FIELDS:
        found = body.count(f'name="{field}"')
        assert found >= 2, (
            f'{field!r} must appear in BOTH the add form and the edit modal; '
            f'found {found} occurrence(s)'
        )
```

Read the `world` fixture to get the correct key for the module id — `world["module_id"]` is a guess and will need adjusting to whatever the fixture actually yields.

- [ ] **Step 2: Run and confirm it fails**

```bash
.venv/bin/python -m pytest tests/test_template_contracts.py::test_module_exercise_add_and_edit_expose_the_same_fields -v
```

Expected: FAIL on `difficulty` (present once, in the edit modal only).

- [ ] **Step 3: Extract the shared partial**

Create `templates/admin/_module_exercise_fields.html` containing the union of both field sets: name, order, category, tag, criterion_type, completion_attempts, completion_min_score, completion_passing, time_signature (+ `time_signature_cb`), difficulty, key_signature, clef (+ `clef_cb`), min_dur (+ `min_dur_cb`).

Namespace every `id` as `{{ mode }}-<field>` and point each `<label for="">` at the same, so the add and edit copies do not collide in the DOM. **`name` attributes must be identical in both modes.**

The exercise picker (`exercise_id` / `exercise_type`) stays in the add form only — you pick what an exercise *is* at creation and change its parameters later. Do not move it into the partial.

- [ ] **Step 4: Include the partial from both places**

Replace the add form's field block with `{% include 'admin/_module_exercise_fields.html' with context %}` after setting `{% set mode = 'add' %}`, and do the same in the edit modal with `mode = 'edit'`. Keep each form's own `<form>` tag, action, and submit button.

- [ ] **Step 5: Run the full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: 143 passed.

- [ ] **Step 6: Verify the round-trip by hand**

Start the dev server and confirm in the browser that creating a module exercise with a difficulty persists it, and that editing one can change the clef filter:

```bash
.venv/bin/python app.py
```

Report what you observed. If either direction still drops a value, the handlers — not the templates — need a follow-up; say so rather than editing the tests.

- [ ] **Step 7: Commit**

```bash
git add templates/admin/_module_exercise_fields.html templates/admin/module_exercises.html tests/test_template_contracts.py
git commit -m "fix: module-exercise add and edit expose the same fields (D1)

The add form and the edit modal had complementary gaps: difficulty and
key_signature could never be set at creation, and clef/min_dur could never
be changed after it — even though both handlers read the same fields.

Extracts one shared partial included by both, with ids namespaced by mode
so the two copies coexist in the DOM. The exercise picker stays add-only.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Done criteria

- `.venv/bin/python -m pytest -q` reports **143 passed**, up from 137.
- `tests/test_school_authority.py` and `tests/test_perspective.py` pass **unmodified** — proof no authorization outcome changed.
- No route path changed.
- No hardcoded URLs added; every new link uses `url_for`.
