# Naming: Section / Classroom / Course

*Established 2026-08-28.*

## The three concepts

| Concept | What it is | Who owns it |
|---|---|---|
| **School** | An institution. Has members with per-school roles, and a join code. | Site admin |
| **Course** | The default coursework — an ordered list of Modules, each holding ModuleExercises. Belongs to a School. | Site admin / school admin |
| **Section** | A group of students taught together. Points at one Course, and may override it per-section. Has a join code. | Teacher |

A Course is the *syllabus*. A Section is the *group of people working through it*. One Course
typically has several Sections.

## One concept, two words on screen

A Section is called different things depending on who is looking:

| Audience | Word they read |
|---|---|
| Site admin, school admin, teachers | **Section** |
| Students | **Classroom** |

**Code, routes, templates, and the screen map always say "section".** Only the rendered words change.

That switch happens in exactly one place — `section_word()` in `app.py`, exposed to every template
by a context processor as four variables:

| Variable | Student sees | Staff sees |
|---|---|---|
| `{{ section_term }}` | classroom | section |
| `{{ section_terms }}` | classrooms | sections |
| `{{ section_term_title }}` | Classroom | Section |
| `{{ section_terms_title }}` | Classrooms | Sections |

Use these in templates rather than hardcoding either word. In `app.py`, call
`section_word(plural=..., title=...)` directly — it's already used in every flash message that
mentions a section.

### Students and the word "course"

Students are not meant to think in terms of Courses. Two places still surface it, deliberately:

1. `templates/home.html` — a section card with no course attached reads **"No work assigned"**.
2. `app.py` — opening a section with no course flashes **"This course has no work assigned yet."**

`templates/student/module_list.html` also uses the Course's *name* as the page heading, which is
the coursework the student is working through.

---

## ⚠️ Code says "section", the database still says "class"

This is the one place where the naming is deliberately inconsistent, so read this before writing
a migration or a raw SQL query.

The Python layer was renamed from `Class` to `Section`. **The physical database schema was not.**
No migration has been run; the existing `instance/musicianship.db` is untouched.

### The full mapping

| Python | Physical database | Where it's pinned |
|---|---|---|
| `Section` (model) | table `class` | `models.py` — `__tablename__ = 'class'` |
| `section_members` (assoc table) | table `class_members` | `models.py` — first arg to `db.Table` |
| `SectionModuleExercise` | table `class_module_exercise` | `models.py` — `__tablename__` |
| `SectionModuleExercise.section_id` | column `class_id` | `models.py` — `db.Column('class_id', …)` |
| `ModuleCompletion.section_id` | column `class_id` | `models.py` — `db.Column('class_id', …)` |
| `ModuleCompletion.section_exercise_id` | column `class_exercise_id` | `models.py` — `db.Column('class_exercise_id', …)` |
| `ModuleCompletion` unique constraints | reference `class_id`, `class_exercise_id` | `models.py` — `__table_args__` uses **column** names |

Foreign keys are declared against physical names too — `db.ForeignKey('class.id')`, not
`'section.id'`.

### One more inconsistency: the `class_teacher` role

`User.role` still stores the literal string `'class_teacher'`. That's **data, not schema** — changing
it means an `UPDATE` over the `user` table, so it was left alone. The UI label for that role reads
"Section Teacher"; the stored value is `class_teacher`. Same for the `assigned_teacher_id` column on
`Section`, which is what makes someone a `class_teacher` for a given section.

### If you migrate the schema later

The work is mechanical:

1. **Back up `instance/musicianship.db` first.**
2. Rename tables: `class` → `section`, `class_members` → `section_members`,
   `class_module_exercise` → `section_module_exercise`.
3. Rename columns: `class_id` → `section_id` (in `class_members`, `class_module_exercise`,
   `module_completion`), `class_exercise_id` → `section_exercise_id` (in `module_completion`).
4. Update the `ForeignKey('class.id')` strings in `models.py`.
5. Delete the explicit overrides — `__tablename__ = 'class'`, the `db.Table('class_members', …)`
   name, and every `db.Column('class_id', …)` / `db.Column('class_exercise_id', …)` first argument.
   Once the physical names match the attribute names, SQLAlchemy infers them.
6. Update the two `db.UniqueConstraint` argument lists in `ModuleCompletion.__table_args__`.
7. Optionally `UPDATE user SET role='section_teacher' WHERE role='class_teacher'`, then update the
   role literals in `app.py` and `screens.py`.

Note that SQLite's `ALTER TABLE ... RENAME COLUMN` needs 3.25+, and renaming a table referenced by
foreign keys behaves differently depending on the `legacy_alter_table` pragma — the safest route is
create-new-table, copy, drop-old, rename.

---

## URLs

URLs were renamed to match the code. No redirects from the old paths were added.

| Old | New |
|---|---|
| `/class/<id>` | `/section/<id>` |
| `/class/<id>/modules` | `/section/<id>/modules` |
| `/class/<id>/modules/<mid>` | `/section/<id>/modules/<mid>` |
| `/class/<id>/module_exercise/<meid>/start` | `/section/<id>/module_exercise/<meid>/start` |
| `/class/<id>/leave` | `/section/<id>/leave` |
| `/my-classes` | `/my-sections` |
| `/teacher/join` | `/section/join` |
| `/teacher/class/...` | `/teacher/section/...` |
| `/teacher/classes/...` | `/teacher/sections/...` |
| `/admin/courses/<id>/classes` | `/admin/courses/<id>/sections` |

## Screen names

The names in `screens.py` and `docs/SCREEN_MAP.drawio` were renamed to match:
`CLASS_HOME` → `SECTION_HOME`, `CLASS_MODULE_LIST` → `SECTION_MODULE_LIST`,
`CLASS_MODULE_DETAIL` → `SECTION_MODULE_DETAIL`, `MY_CLASSES` → `MY_SECTIONS`,
`CLASS_JOIN` → `SECTION_JOIN`, `CLASS_LEAVE` → `SECTION_LEAVE`,
`TEACHER_CLASS_*` → `TEACHER_SECTION_*`, `COURSE_CLASSES` → `COURSE_SECTIONS`.
The `class_member` access level is now `section_member`.

`tests/test_screens.py` enforces that the registry, the app's routes, the template files and the
diagram all agree.

## Renamed template files

`student/my_classes.html` → `student/my_sections.html` ·
`teacher/class_detail.html` → `teacher/section_detail.html` ·
`teacher/edit_class.html` → `teacher/edit_section.html` ·
`teacher/new_class.html` → `teacher/new_section.html` ·
`teacher/confirm_delete_class.html` → `teacher/confirm_delete_section.html` ·
`admin/course_classes.html` → `admin/course_sections.html`


---

## Permission perspectives ("view as")

Any account can drop into a role at or below its own to see the site as that role sees it — a
teacher previewing the student experience, a site admin checking what a school admin can reach.
Selected from the **View as** group in the account dropdown; a banner shows the active perspective
with a one-click way back.

The perspective is stored in `session['perspective']` and **genuinely restricts**: `role_required()`
and every section guard consult `active_role()`, not `User.role`.

### Two safety invariants

1. **`active_role()` is always `min(session perspective, real role)`.** A perspective can only ever
   reduce privileges. A session value forged above the account's real role is ignored, not honoured
   — and `/perspective/<role>` refuses an elevated role with a 403 at the entry point too.
2. **The switcher is never role-gated**, and the banner renders outside the nav dropdown, so you can
   always get back out of a perspective that has hidden the menu.

### The per-section rule

Teacher authority is per-section, so there is a second, narrower resolution in
`effective_section_role()`:

> Your effective role in a section is the highest role you genuinely hold there that does not
> exceed the perspective you selected.

**Roles are inclusive** — holding `admin_teacher` over a section also confers `class_teacher` and
`student` over it. That is what makes the feature useful: a section owner viewing as a student gets
the student view of *their own* section rather than being locked out of it. `require_section_role()`
is the single guard that enforces this; routes state the minimum they need rather than comparing
ids by hand.

Site admins have blanket authority over every section, but only at full `admin` role — drop to any
lower perspective and they are judged purely on their real relationships. `related_sections()` (the
list shown on the perspective home screen) never expands for admins: it is always sections the
account owns, is assigned to, or is enrolled in.

### Where it shows up

| Surface | Behaviour under a perspective |
|---|---|
| Nav dropdown | Branches on `active_role`, so the menu matches the role |
| Section wording | Follows the perspective — an admin viewing as a student reads "classroom" |
| Home screen | Renders the chosen role's home; empty state explains an unrelated admin sees nothing |
| Debug panel | Adds a `viewing as` row showing perspective and real role |
| Banner | Always visible while a perspective is active |

Covered by `tests/test_perspective.py` (29 tests), most of which exist to prove escalation is
impossible.


---

## School authority

Three levels of scope, each with its own guard. The pattern matters: a bare
`@role_required('admin_teacher')` says *"is this person a school admin somewhere"*, not
*"of this school"* — which is how any admin_teacher was once able to rename any other school's
course.

| Scope | Guard | Answers |
|---|---|---|
| Site | `@role_required(...)` | Does this account hold the role at all? |
| School | `require_school_role(school_id, minimum)` | Does it hold that role **over this school**? |
| Section | `require_section_role(section, minimum)` | Does it hold that role **over this section**? |

`require_manage_section(section)` combines the last two: you may administer a section if you own it
*or* you are a school admin of the school it belongs to.

**A section's school is derived through its course** (`section_school_id()`), so a section with no
course assigned belongs to no school — and only its owner has authority over it.

### Who can do what

| Action | Required |
|---|---|
| Create/delete schools; assign an admin_teacher to a school | Site admin |
| Create, rename, duplicate, delete courses; edit modules and module exercises | admin_teacher **of that school** |
| Create sections; assign a section teacher; set a section's course; delete a section | admin_teacher of the school, or the section's owner |
| View/regenerate the **school** join code | admin_teacher of that school |
| Edit section details, curriculum overrides, roster; view the **section** join code | class_teacher of that section, or higher |
| Remove a member from a school | Anyone whose school role is strictly above theirs |

### The "strictly below" rule

Membership changes — adding, re-roling, removing — all require the target's school role to be
**strictly below** the actor's own, via `outranks_in_school()`. Two consequences fall out of that
single rule:

* Nobody can grant a role at or above their own, so **only a site admin can seat an admin_teacher**.
* Students outrank nobody, so they can never act on anyone — which is why "anyone other than a
  student" needs no separate check.

`grantable_school_roles()` drives the role dropdowns from the same rule, so the UI never offers
something the route will refuse.

### People are identified by email

Every form that names a person takes an **email address**, not an id from a dropdown — adding a
school member, appointing a school administrator, and assigning a section teacher. Lookups go
through `find_user_by_email()`, which trims and lower-cases (deliberately not `ilike`, which would
treat `_` and `%` in an address as wildcards).

Failures say which of the two possible things went wrong rather than a generic refusal:

| Situation | Message |
|---|---|
| No such account | *No account found for "…"* |
| Account exists, not in this school | *… is not a member of <school>. Add them to the school first.* |
| Member, but not a teacher there | *… is a student in <school>, not a teacher. Change their school role first.* |

**Appointing a school administrator** has its own card on the school page (`SCHOOL_SET_ADMIN`,
`/admin/schools/<id>/set-admin`). It handles both cases — adds a non-member, promotes an existing
member — and is site-admin only, not by a special case but because granting `admin_teacher` requires
a school role ranking above it. Stepping someone down is the ordinary role control in the members
table.

### Side effects worth knowing

* **`_sync_global_role()`** keeps `User.role` equal to the highest role the person holds across all
  their schools. Promote them anywhere and they gain it globally; strip their last staff membership
  and they fall back to student. Site admins are never demoted this way.
* **Removing someone from a school also drops them from that school's sections** and clears any
  assigned-teacher links. Attempt history and completion records are left alone.
* **Removal is refused if the person still owns sections** in that school — `Section.teacher_id` is
  not nullable, so the alternative would be cascade-deleting their sections. Reassign or delete
  those first.

### Creating a section requires administering a school

`@role_required('admin_teacher')` only asks whether the account is a school admin *somewhere*. A
user with that global role but no `admin_teacher` membership anywhere could still open
`/teacher/section/new` and create a section — and because a section's school is derived through its
course, a section created with no course belongs to no school and answers to nobody but its creator.
`teacher_new_section` now refuses unless `administered_schools()` is non-empty, and the dashboard
hides the button in that case.

### Two nav entries, not one

Joining a school or a section happens on `MY_SECTIONS` (`/my-sections`), and **every role needs it** —
a teacher may also be enrolled somewhere, and everyone needs the join-by-code forms. The nav
therefore carries two distinct entries for staff:

| Entry | Route | Shows |
|---|---|---|
| "Sections I Teach" | `teacher_dashboard` | sections you own or are assigned to |
| "My Sections" / "My Classrooms" | `my_sections` | sections you are *enrolled in*, plus join-by-code |

Students see only the second, labelled "My Classrooms".

Covered by `tests/test_school_authority.py` (46 tests).
