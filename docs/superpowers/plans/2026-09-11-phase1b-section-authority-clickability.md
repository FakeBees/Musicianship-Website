# Phase 1b — Section Authority (D11) + Admin Clickability Sweep (D10)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the guard inconsistency that lets a school admin delete a section they cannot open, then make every admin list clickable.

**Architecture:** One new authority helper in `app.py` applied to seven section-management routes, then a template-only sweep across nine admin list pages. No route paths change.

**Tech Stack:** Flask, Flask-SQLAlchemy, Flask-Login, Jinja2, Bootstrap 5, pytest.

**Spec:** `docs/superpowers/specs/2026-09-10-admin-ia-refactor-design.md` (§2.6, plus new defect D11)

## Global Constraints

- **No access may be REMOVED.** D11 only *adds* school-admin authority over sections. Every existing holder keeps what they have.
- `tests/test_school_authority.py` (46) and `tests/test_perspective.py` (29) must pass **UNMODIFIED**. I verified this is achievable: `effective_school_role` already caps by the active perspective, so the perspective tests still hold. **If either suite fails, you removed access or widened it past the design — stop and report; do not edit those files.**
- No URL/route path changes.
- Current suite is **145 passing**. Every task must end strictly higher.
- `timeout` is NOT available on this machine.
- **Do NOT write to `instance/musicianship.db`.** An earlier agent corrupted it. The suite is isolated via `tests/conftest.py`; `.venv/bin/python -m pytest -q` is safe.
- Templates use `url_for`, never hardcoded paths. Never hardcode "class"/"section"/"classroom" in user-visible copy — use `{{ section_term }}` / `{{ section_terms_title }}`.
- There is **no `login()` helper** in the suite. Use `client_as(uid)` in `tests/test_template_contracts.py`, or `client_for(user)` in `tests/test_school_authority.py`. Do not invent a third.
- Commit after each task, ending with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

---

### Task 1: Section authority helper (D11)

**The defect.** A school `admin_teacher` who does not personally own a section can **delete** it, set its course, assign its teacher, and add module exercises — but **cannot view its roster**, edit it, kick a student, manage overrides, or hide/restore a module. Destructive power granted where read access is denied.

Cause: the routes are split between two guards. `require_manage_section` consults school-level authority; `require_section_role` consults only the role held *within* the section, and `section_role()` deliberately ignores school authority.

**The trap — read this before coding.** Do **not** simply swap `require_section_role` for `require_manage_section`. `can_manage_section` demands `admin_teacher`-level, so that swap would **lock out assigned `class_teacher`s** who can view their own section today. That is removing access, which this plan forbids. You need a *union*: existing section-role access **OR** school-admin authority.

**Files:**
- Modify: `app.py` — add two helpers near the other section helpers (roughly lines 120-190); change the guard call in seven routes
- Test: `tests/test_school_authority.py` (new tests appended; existing assertions untouched)

**Interfaces:**
- Produces: `section_authority(section)` returning a role string or `None`, and `require_section_authority(section, minimum)` which aborts 403.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_school_authority.py`, following its existing `school()` / `course()` / `user()` / `member()` / `client_for()` helpers:

```python
def test_school_admin_can_open_a_section_they_do_not_own():
    """D11: a school admin could delete a section but not view its roster.

    teacher_delete_section already used require_manage_section (school-aware)
    while teacher_section_detail used require_section_role (section-only), so
    destructive power was granted where read access was denied.
    """
    s = school('Mine')
    crs = course(s)
    owner = user('admin_teacher', 'owner@x.com'); member(s, owner, 'admin_teacher')
    boss  = user('admin_teacher', 'boss@x.com');  member(s, boss,  'admin_teacher')
    sec = Section(name='S1', join_code='SEC1', teacher_id=owner.id, course_id=crs.id)
    db.session.add(sec); db.session.commit()

    c = client_for(boss)                      # administers the school, owns nothing
    assert c.get(f'/teacher/section/{sec.id}').status_code == 200


def test_assigned_class_teacher_keeps_section_access():
    """Guard against the obvious wrong fix: swapping to require_manage_section
    would demand admin_teacher-level and lock this person out."""
    s = school('Mine')
    crs = course(s)
    at = user('admin_teacher', 'at2@x.com'); member(s, at, 'admin_teacher')
    ct = user('class_teacher', 'ct2@x.com'); member(s, ct, 'class_teacher')
    sec = Section(name='S2', join_code='SEC2', teacher_id=at.id,
                  assigned_teacher_id=ct.id, course_id=crs.id)
    db.session.add(sec); db.session.commit()

    assert client_for(ct).get(f'/teacher/section/{sec.id}').status_code == 200


def test_school_admin_of_another_school_still_cannot_open_the_section():
    """The new authority is scoped to the section's own school."""
    mine, theirs = school('Mine'), school('Theirs')
    crs = course(mine)
    owner    = user('admin_teacher', 'owner2@x.com'); member(mine,   owner,    'admin_teacher')
    outsider = user('admin_teacher', 'out@x.com');    member(theirs, outsider, 'admin_teacher')
    sec = Section(name='S3', join_code='SEC3', teacher_id=owner.id, course_id=crs.id)
    db.session.add(sec); db.session.commit()

    assert client_for(outsider).get(f'/teacher/section/{sec.id}').status_code == 403
```

Adjust helper names/signatures to match what that file actually defines — read it first.

- [ ] **Step 2: Run and confirm the first test fails, the other two pass**

```bash
.venv/bin/python -m pytest tests/test_school_authority.py -k "school_admin_can_open or assigned_class_teacher_keeps or another_school_still" -v
```

Expected: `test_school_admin_can_open_a_section_they_do_not_own` FAILS with 403. The other two PASS already — they are regression guards, not new behaviour.

- [ ] **Step 3: Add the helpers**

In `app.py`, directly after `require_section_role`:

```python
def section_authority(section):
    """Effective role over one section, counting school-level authority.

    section_access() answers "what am I *within* this section". This answers
    "what may I do *to* this section", which additionally honours being an
    admin_teacher of the school the section belongs to.

    Management screens use this; student participation screens keep using
    section_access(), because doing a section's coursework requires actually
    being in it.
    """
    direct = section_access(section)
    if direct is not None and role_rank(direct) >= role_rank('class_teacher'):
        return direct
    sid = section_school_id(section)
    if sid is not None and \
            role_rank(effective_school_role(sid) or '') >= role_rank('admin_teacher'):
        return 'admin_teacher'
    return direct


def require_section_authority(section, minimum):
    """403 unless section_authority() is at least `minimum`."""
    role = section_authority(section)
    if role is None or role_rank(role) < role_rank(minimum):
        abort(403)
```

- [ ] **Step 4: Apply it to exactly these seven routes**

Replace `require_section_role(section, ...)` with `require_section_authority(section, ...)`, keeping each call's existing `minimum` argument unchanged, in:

| Route | View function |
|---|---|
| `/teacher/section/<id>` | `teacher_section_detail` |
| `/teacher/section/<id>/edit` | `teacher_edit_section` |
| `/teacher/section/<id>/kick/<user_id>` | `teacher_kick_student` |
| `/teacher/sections/<id>/overrides/add` | `teacher_add_override` |
| `/teacher/sections/<id>/overrides/<sme_id>/delete` | `teacher_delete_override` |
| `/teacher/sections/<id>/modules/<module_id>/hide` | `teacher_hide_module` |
| `/teacher/sections/<id>/modules/<module_id>/restore` | `teacher_restore_module` |

**Leave these four completely alone** — they are student participation routes and `require_section_role` is correct for them: `section_home`, `section_modules`, `section_module_detail`, `start_module_exercise`.

Leave the four routes already using `require_manage_section` alone too.

- [ ] **Step 5: Run the full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: 148 passed. **`test_school_authority.py`'s pre-existing tests and all of `test_perspective.py` must pass unmodified.** If a perspective test fails, your helper is not honouring the perspective cap — `effective_school_role` already applies it, so re-read rather than editing the test.

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_school_authority.py
git commit -m "fix: school admins can manage sections they do not own (D11)

A school admin_teacher could delete a section, set its course and assign
its teacher, but could not view its roster, edit it, kick a student or
manage overrides — destructive power granted where read access was denied.

Adds section_authority()/require_section_authority(), a union of existing
in-section role and school-level admin_teacher authority, and applies it to
the seven management routes. Student participation routes keep
require_section_role: doing a section's coursework requires being in it.

No access removed — an assigned class_teacher keeps exactly what they had,
which a naive swap to require_manage_section would have taken away.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Admin clickability sweep (D10)

Every listed entity the viewer can reach must link to it. `templates/home.html` is the in-repo precedent. Every destination below already exists, and because links go through `url_for`, Phase 3's rename carries them automatically.

**Files:** nine templates under `templates/admin/`; test in `tests/test_template_contracts.py`.

**Mapping — link the entity's name cell to:**

| Template | Entity | `url_for` target |
|---|---|---|
| `schools.html` | school name | `admin_school_detail(school_id=s.id)` |
| `courses.html` | course name | `admin_modules(course_id=c.id)` |
| `modules.html` | module name | `admin_module_exercises(module_id=m.id)` |
| `course_sections.html` | section name | `teacher_section_detail(section_id=section.id)` |
| `melodies.html` | name | `admin_edit_melody(mel_id=m.id)` |
| `rhythms.html` | name | `admin_edit_rhythm(rhythm_id=r.id)` |
| `harmonics.html` | name | `admin_edit_harmonic(prog_id=p.id)` |
| `holistic_list.html` | name | `admin_edit_holistic(ex_id=e.id)` |
| `gen_progressions.html` | name | `admin_edit_gen_progression(gp_id=gp.id)` |

**Leave plain — no destination exists, and a dead link is a defect:** the user email in `admin/users.html` and the member emails in `admin/school_detail.html`. Do **not** create a user-detail page.

In `course_sections.html`, link only the name — keep the `<code>` join code outside the anchor.

- [ ] **Step 1: Write the failing test**

```python
ADMIN_LIST_LINKS = [
    ('/admin/schools',                      'admin_school_detail'),
    ('/admin/melodies',                     'admin_edit_melody'),
    ('/admin/rhythms',                      'admin_edit_rhythm'),
    ('/admin/harmonics',                    'admin_edit_harmonic'),
    ('/admin/holistic',                     'admin_edit_holistic'),
    ('/admin/gen-progressions',             'admin_edit_gen_progression'),
]


@pytest.mark.parametrize('path,endpoint', ADMIN_LIST_LINKS)
def test_admin_lists_link_their_entities(client_as, world, strict_undefined,
                                         path, endpoint):
    """Every listed entity the viewer can reach must be clickable (D10)."""
    resp = client_as(world['admin_id']).get(path)
    assert resp.status_code == 200
    with app.test_request_context():
        # the row must contain a link whose path matches that endpoint's shape
        assert '/admin/' in resp.data.decode()
```

That last assertion is too weak to be useful — **replace it**. Build the expected href with `url_for(endpoint, ...)` for a real seeded row and assert that exact string appears in the body. Seed at least one row per content type; read the `world` fixture and extend it if it has none. A test that passes before your change is worthless — verify RED first.

- [ ] **Step 2: Run and confirm RED**

```bash
.venv/bin/python -m pytest tests/test_template_contracts.py -k admin_lists_link -v
```

- [ ] **Step 3: Add the links**

Wrap each name cell's content in `<a href="{{ url_for(...) }}" class="text-decoration-none">`, per the mapping table. Keep every existing action button in its own column untouched.

- [ ] **Step 4: Run the full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: strictly more than 148, all passing.

- [ ] **Step 5: Commit**

```bash
git add templates/admin/ tests/test_template_contracts.py
git commit -m "feat: make admin list entities clickable (D10)

Every listed entity the viewer has permission to reach now links to it,
following the existing home.html precedent. User emails stay plain text —
no user-detail page exists and a dead link would be a defect.

Links go through url_for, so the Phase 3 /manage/* rename carries them.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Done criteria

- Full suite green, strictly above 145.
- `tests/test_perspective.py` **unmodified** and passing — proof no perspective cap was weakened.
- Pre-existing assertions in `tests/test_school_authority.py` unmodified and passing — proof no access was removed.
- No route path changed; no hardcoded URLs added.
