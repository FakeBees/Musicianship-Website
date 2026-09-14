# School Admin Guide

**Musicianship Trainer** · for the people who run a school's courses, sections and members

Checked against the site on September 14, 2026. Menu names and page addresses will change when the
planned admin reorganisation lands; the tasks themselves won't. The other two guides are the
**Section Teacher Guide** and the **Site Admin Guide**.

---

## Contents

1. [Your role at a glance](#1-your-role-at-a-glance)
2. [Key ideas](#2-key-ideas)
3. [Getting around](#3-getting-around)
4. [Setting up a school: the checklist](#4-setting-up-a-school-the-checklist)
5. [Your school page](#5-your-school-page)
6. [People](#6-people)
7. [Courses](#7-courses)
8. [Modules](#8-modules)
9. [Module exercises](#9-module-exercises)
10. [Sections](#10-sections)
11. [Section overrides](#11-section-overrides)
12. [Rosters and progress](#12-rosters-and-progress)
13. [Getting students in](#13-getting-students-in)
14. [Seeing the site as another role](#14-seeing-the-site-as-another-role)
15. [When something goes wrong](#15-when-something-goes-wrong)
16. [Known issues](#16-known-issues)
17. [Quick reference](#17-quick-reference)

---

## 1. Your role at a glance

You're a **School Admin**. You build your school's courses, create its sections, and manage its
people. A Site Admin appointed you. On the school page you're listed as an **administrative
teacher** — that's the same role under an older name.

| You can | Ask a Site Admin to |
|---|---|
| See and regenerate the school join code | Appoint or remove a School Admin |
| Add people to the school as students or Section Teachers | Create or delete a school |
| Change the role of, or remove, members below you | Add, edit or delete exercises in the library |
| Create, rename, duplicate and delete courses | Delete a user account |
| Create and delete modules | Reset someone's password |
| Add, edit, duplicate and remove module exercises | |
| Create, edit and delete sections; set their course and teacher | |
| Add an exercise to a single section | |
| View rosters and remove students | |

You can do everything a Section Teacher can, for every section in your school.

**The one rule behind every permission:** you can only give or take away roles *below your own*. You
can grant **Student** and **Section Teacher**, but not School Admin — that's why only a Site Admin can
appoint one.

---

## 2. Key ideas

### The building blocks

**School.** Your organisation. People join it, and it owns the courses.

**Course.** A curriculum, such as *Theory 1*. A course is made of modules. Many sections can follow
the same course.

**Module.** A unit within a course, such as *Intervals*. Modules appear to students in a fixed order.

**Module exercise.** One assignment inside a module, with a **completion rule**. See
[section 9](#9-module-exercises).

**Section.** A group of students taught together, usually named like a class section, such as
*MUS201-002*. **Students see the word "Classroom" instead of "Section" — it's the same thing.** A
section follows one course, which gives its students their modules. The School Admin who creates a
section is its **owner**, and it can also have one **Section Teacher** assigned.

**Join codes.** Short codes students type to join. There are two — a **school join code** and a
**section join code** — and students need both, in that order.

**Section overrides.** Changes made to one section without touching its course, such as adding an
extra exercise just for that section. See [section 11](#11-section-overrides).

```
School
 └─ Course                    e.g. Theory 1
     └─ Module                e.g. Intervals          (ordered)
         └─ Module exercise   e.g. "Seconds"          (ordered, with a completion rule)

Section                       e.g. MUS201-002         (students see: Classroom)
 ├─ follows one Course        → gives students its modules
 ├─ Owner                     → the School Admin who created it
 ├─ Section Teacher           → optional, one per section
 ├─ Students                  → joined with the section join code
 └─ Overrides                 → section-only changes
```

### Roles

| Role | In the app it's also shown as | Who they are |
|---|---|---|
| **Student** | `student` | Anyone who registers |
| **Section Teacher** | `class_teacher` | Teaches the sections assigned to them |
| **School Admin** | `admin_teacher`, "administrative teacher" | You |
| **Site Admin** | `admin` | Runs the whole website |

Everyone registers as a Student. **A person's account role follows their school role**: when you give
someone the Section Teacher role in your school, their account becomes a Section Teacher account
straight away. If they lose their last staff role anywhere, their account goes back to Student.

---

## 3. Getting around

Everything starts from the **account menu** in the top-right corner of every page.

| Menu item | Takes you to |
|---|---|
| **Sections I Teach** | Sections you created, with a **+ New section** button. |
| **My Sections** | Sections you're enrolled in *as a participant*, plus join-code forms. Rarely needed. |
| **Manage School** | Your school's page: join code, courses, members. |
| **Home** | Your school's courses under *"School courses — default coursework"*, plus free practice. |
| **My Progress** | Your own practice history. |
| **View as** | Preview the site as a Section Teacher or a Student. See [section 14](#14-seeing-the-site-as-another-role). |
| **Log out** | |

> **Finding a section you didn't create.** **Sections I Teach** only lists sections *you* created. To
> reach any other section in your school: **Manage School** → **Manage courses →** → on the course's
> row, **Manage** in the *Sections* column → click the section's name. The course cards on **Home**
> (**View →**) lead to the same list.

> **Heads-up.** The page you reach from **Sections I Teach** is titled *My Sections* at the top — and so
> is the different page you reach from **My Sections**. If you can see **+ New section** and section
> cards with **View roster**, you're in the right place.

---

## 4. Setting up a school: the checklist

The first time you set up your school, work through these in order.

1. **Make sure the school has a join code.** **Manage School** → *School Join Code*. If it shows
   **—**, press **Regenerate** and confirm. New schools start without a code, and nobody can join until
   one exists.
2. **Add your teachers.** They register first, then you add them as `class_teacher`.
   See [section 6](#6-people).
3. **Build a course.** Create the course, then its modules, then each module's exercises.
   See sections [7](#7-courses), [8](#8-modules) and [9](#9-module-exercises).
4. **Create sections.** Choose the course while creating each one. See [section 10](#10-sections).
5. **Assign a Section Teacher** to each section. See [section 10](#10-sections).
6. **Share both join codes** with students. See [section 13](#13-getting-students-in).
7. **Check it as a student.** Use **View as → Student**. See
   [section 14](#14-seeing-the-site-as-another-role).

---

## 5. Your school page

Open the account menu → **Manage School**.

| Card | What it's for |
|---|---|
| **Your role here** | Shows `admin_teacher` — that's School Admin. |
| **School Join Code** | The code students use to join your school, and the **Regenerate** button. |
| **Courses** | *"Create courses, edit modules, and see their sections."* → **Manage courses →** |
| **Administrative teachers** | The school's School Admins. Read-only for you: *"Only a site admin can appoint an administrative teacher."* |
| **Add member by email** | Add a person to the school with a role. |
| **Members** | Everyone in the school, with controls to change roles and remove people. |

### Regenerating the school join code

1. Press **Regenerate** on the *School Join Code* card.
2. Confirm: *"Regenerate join code? The old code will stop working."*
3. The page shows *"Join code regenerated: …"* with the new code.

People who've already joined stay in the school. Only new joins need the new code. Do this if a code
has been shared somewhere it shouldn't have been.

---

## 6. People

### Adding a teacher or a student

The person must already have an account.

1. Ask them to register on the site's **Register** page.
2. **Manage School** → **Add member by email**.
3. Type their email **exactly as they registered it**.
4. Choose a role: `class_teacher` for a Section Teacher, or `student`.
5. Press **Add**. You'll see *"Added … as …"*.

Their account takes on the new role immediately.

Students don't need to be added this way — they can join by themselves with the school join code.
Use **Add member by email** for teachers, or to skip the join code for a particular student.

| Message | Meaning |
|---|---|
| *No user with email "…".* | They haven't registered yet, or the email doesn't match. |
| *… is already a member.* | Change their role in the *Members* table instead. |
| *You cannot grant the role "…".* | That role isn't below yours. |

### Changing someone's role

1. **Manage School** → *Members*.
2. On their row, pick the new role and press **Set**.
3. You'll see *"… is now … in …"*.

You can only change people whose role is below yours, and only to roles below yours.

If you change a Section Teacher to `student`, they lose their teacher access. **Assign a new Section
Teacher to any sections they were teaching.**

### Removing someone from the school

1. **Manage School** → *Members* → **Remove** on their row.
2. Confirm: *"Remove … from …? They will also be dropped from this school's sections."*

Removing someone from the school:

- takes them out of **every section** in the school
- unassigns them from any section they were teaching
- keeps their practice history and completion records

### Onboarding a new Section Teacher, start to finish

1. The teacher registers an account.
2. **Manage School** → **Add member by email** → their email → `class_teacher` → **Add**.
3. Open the section they'll teach → **Edit** → **Assign Section Teacher** → their email → **Assign**.
4. Give them the **school join code** — Section Teachers can't see it, but their students need it.
5. Send them the **Section Teacher Guide**, and point out its warning about **Save Changes**
   ([Known issues](#16-known-issues)).

---

## 7. Courses

**Manage School** → **Manage courses →**. The page is titled *"<school> — Courses"*.

> **⚠️** The **← Schools** link at the top of this page leads to a **Forbidden** page for School Admins.
> Use the account menu → **Manage School** to go back instead.

### Creating a course

Type a name into **New course name** and press **Add**. You'll see *"Course created."*

### The courses table

| Column | What's there |
|---|---|
| **Name** | Click to open the course's modules. |
| **Modules** | How many modules it has, and **Manage** to open them. |
| **Sections** | How many sections follow this course, and **Manage** to list them. |
| *(actions)* | **Rename**, **Duplicate**, **Delete** |

### Renaming a course

Press **Rename**, edit the name, and press **Save**. Sections that follow the course pick up the new
name straight away.

### Duplicating a course

Press **Duplicate** and confirm. This creates **"<name> (copy)"** with copies of all its modules and
module exercises. Sections aren't copied, and no section follows the copy until you choose it for one.

This is the easiest way to start next term's version of a course without disturbing this term's
students.

### Deleting a course

Press **Delete** and confirm *"Delete course "…" and all its modules?"*

> **⚠️ Deleting a course deletes more than the confirmation says.**
>
> - Every student's progress on that course's exercises is **permanently deleted**.
> - Any section following the course is left **with no course**, so its students lose access to their
>   modules.
>
> There's no undo. If you only want a section to study something different, change that section's
> course instead ([section 10](#10-sections)).

---

## 8. Modules

Click a course's name. The page is titled *"<course> — Modules"*.

### Creating a module

1. Type a **Module name**.
2. Type an **Order** number. Students see modules sorted by this number, lowest first.
3. Press **Add**. You'll see *"Module created."*

> **Tip.** Number your modules with gaps — 10, 20, 30 — rather than 1, 2, 3. Modules can't be
> re-ordered after they're created, so gaps leave room to slot a new module in between later.

### The modules table

Each row shows the module's order (**#**), its **Name** (click to open its exercises), how many
**Exercises** it has with an **Exercises →** link, and **Delete**.

### Deleting a module

Press **Delete** and confirm. This deletes the module, all of its module exercises, and every
student's progress on them.

> **Note.** Modules can't be renamed or re-ordered once created. To change one, create a replacement
> and delete the old one. Because deleting removes student progress, do this before students start.

---

## 9. Module exercises

Click a module's name. The page is titled *"<module> — Exercises"*. This is where you decide what
students actually do.

### How module exercises work

There are two kinds, and they behave differently:

- **Melodic, Rhythmic and Harmonic** exercises describe a *kind* of exercise using filters —
  difficulty, time signature, topic and so on. **Each time a student starts one, the site picks a
  random exercise from the library that matches your filters.** Students get variety, and repeat
  attempts give different material.
- **Holistic** exercises point at **one specific exercise** that you choose. Every student gets that
  same exercise.

A module exercise is complete for a student once they meet its **completion rule**.

### Adding a module exercise

1. Choose the **Type**: Melodic, Rhythmic, Harmonic or Holistic.
2. Give it a **Name** — this is what students see, such as *Basic Melodic Dictation*.
3. Set the **Order** — its position within the module, lowest first.
4. Choose a **Completion** rule (below).
5. **Holistic:** choose the exercise from the **Exercise** list.
   **Melodic, Rhythmic, Harmonic:** set the filters (below).
6. Check the **live match count**, which shows how many library exercises your filters currently
   select. Make sure it's above zero.
7. Press **Add Exercise**. You'll see *"Exercise added to module."*

### Completion rules

| Option | A student completes it when… | Example |
|---|---|---|
| **By attempts** | they've submitted it this many times, whatever they scored | *3 attempt(s) to complete* |
| **By passing score** | they've submitted this many times at or above the minimum score | *2 pass(es) at 80 % minimum score* |

The defaults are 1 attempt, or 1 pass at 70 %. The site records each student's best score either way.

What students see: a check mark and their best score once they've completed it, and a progress bar
whenever more than one attempt or pass is required.

### Filters

Filters appear for Melodic, Rhythmic and Harmonic exercises. **Leave a filter empty to allow
anything.**

| Filter | Used for | How ticking several boxes behaves |
|---|---|---|
| **Difficulty** — 1 to 5 stars | All three | Matches **any** ticked difficulty |
| **Time Signature** | Melodic, Rhythmic | **Tick only one.** Ticking several currently drops the time-signature filter entirely. |
| **Shortest Note Value** | Melodic, Rhythmic | ⚠️ Currently ignored — has no effect |
| **Clef** | Melodic | ⚠️ Currently ignored — has no effect |
| **Category** — Diatonic, Chromatic, Mode Mixture, Modal | Harmonic | Matches **any** ticked category |
| **Key Signature** — type one key, such as *C*, *G* or *Bb* | Harmonic | One key only |
| **Topics** | All three | An exercise must have **all** the ticked topics |

Only the topics that exist for the chosen type are offered.

> **⚠️ The live match count isn't always right.** For Melodic and Rhythmic exercises it doesn't take
> **Difficulty** into account, and it does count the ignored **Clef** and **Shortest Note Value**
> filters. Treat it as a rough guide, and check the result with **View as → Student**.

### What happens if nothing matches

A student who starts the exercise sees *"No exercises match the filters for this module exercise. Ask
your teacher to adjust the filters."* and can't complete it. Loosen the filters — usually Topics or
Key Signature are the culprits.

### The exercises table

Columns: order (**#**), **Name**, **Type**, **Filters / Exercise** (a summary of the filters, or which
holistic exercise), **Completion**, then the actions.

- **Edit** opens a panel with the same fields as the add form. For Holistic exercises you can change
  the name, order and completion rule, but not which exercise it is — *"To change the exercise, remove
  and re-add it."*
- **Duplicate** makes a copy you can then edit. Handy for *"the same thing, but harder"*.
- **Remove** takes it out of the module, after confirming *"Remove this exercise from the module?"*
  Students' progress on it no longer counts.

---

## 10. Sections

### Creating a section

1. Account menu → **Sections I Teach** → **+ New section**.
2. **Section Name** — name it like a section number, such as *MUS201-002*.
3. **Course (optional)** — choose it now. *"Selecting a course gives students access to its modules."*
   Until a section has a course, it doesn't belong to your school, and you can't assign it a teacher.
4. Press **Create Section**.

You'll see *"Section "…" created. Join code: …"* You're the new section's owner, and it appears on
**Sections I Teach**.

### The section card

On **Sections I Teach**, each card shows the section's name (click it for the roster), its **Join
code**, the number of students, and **View roster**, **Edit** and **Delete** buttons.

### Changing a section's name or course

1. Open the section → **Edit**.
2. On the **Section Settings** card, change **Section Name** or **Course**.
3. Press **Save Changes**. You'll see *"Section updated."*

Changing the course changes what students see immediately. Their progress on the previous course is
kept — it just isn't shown while the section follows a different course.

> **⚠️ Warn your Section Teachers about this page.**
>
> Because of a known issue, if a **Section Teacher** presses **Save Changes** here, the section's
> course is removed and every student in it loses access to their modules.
>
> **If a section suddenly shows students no modules:** open its Edit page, choose the course again, and
> press **Save Changes**. Progress isn't deleted, so everything comes back.

### Assigning a Section Teacher

1. Open the section → **Edit** → the **Assign Section Teacher** card.
2. Type the teacher's email and press **Assign**. You'll see *"… is now the section teacher."*
3. To unassign them, press **Clear**.

A section has one Section Teacher at a time; assigning someone new replaces the previous one. The card
tells you how many eligible teachers your school has.

The teacher must already be a **Section Teacher or School Admin in your school**, and the section must
have a course.

| Message | What to do |
|---|---|
| *This section has no course, so it does not belong to a school yet. Assign a course first.* | Choose a course under **Section Settings** first. |
| *No account found for "…".* | They haven't registered, or the email doesn't match. |
| *… is not a member of <school>. Add them to the school first.* | Add them on **Manage School** ([section 6](#6-people)). |
| *… is a student in <school>, not a teacher. Change their school role first.* | Change their role to `class_teacher` ([section 6](#6-people)). |

### Deleting a section

1. **Sections I Teach** → **Delete**, or the **Delete Section** link at the bottom of the Edit page.
2. Read the confirmation. It lists what will happen:
   - its students will be removed from the section
   - all its section-specific overrides will be deleted
   - students' module completion data for this section will be deleted
   - this cannot be undone
3. Press **Yes, delete "…"** — or **Cancel**.

Students stay in the school, and their overall practice history is kept.

---

## 11. Section overrides

Open a section → **Edit** → the **Section-Specific Overrides** card. It lists each module in the
section's course, with its exercises.

### Hiding modules and exercises

The card has **Hide module** and **Hide** buttons, and **Restore** to undo.

> **⚠️ Hiding doesn't currently affect students.**
>
> Pressing **Hide** or **Hide module** shows a success message and marks the item *Hidden* on this page,
> but students still see those exercises and can still complete them. Until this is fixed, don't rely
> on hiding. To keep work away from one section, duplicate the course, remove that work from the copy,
> and switch the section to the copy. Students' existing progress doesn't carry over to a copied course,
> so do this before they start.

### Adding an exercise to one section only

This gives a single section an extra exercise without changing the course for everyone else.

1. Under the module where it belongs, open **+ Add exercise to this section only**.
2. Choose the **Type**.
3. Enter the **Exercise ID** — see *Finding an exercise ID*, below.
4. Optionally, give it a **Display name**.
5. Press **Add**. You'll see *"Exercise added to this section only."*

Unlike course module exercises, a section-only exercise is always **one specific exercise** (no
filters). It appears at the end of its module and counts as complete after **one attempt**.

### Finding an exercise ID

Exercise IDs aren't listed anywhere you can see, so use the page address:

1. **Home** → **Open Sandbox** → choose the mode → open the exercise you want.
2. Look at the address bar. The number right after `/exercise/` is the ID.

| Type | The address looks like |
|---|---|
| Melodic | `…/exercise/12` |
| Rhythmic | `…/rhythm/exercise/12` |
| Harmonic | `…/harmonic/exercise/12` |
| Holistic | `…/holistic/exercise/12` |

Codes such as *MEL-0012* that you may see elsewhere are a different number — use the one from the
address.

---

## 12. Rosters and progress

Open a section's name, or **View roster** on its card.

The roster lists one row per student, with their average score in each mode:

| Column | What it shows |
|---|---|
| **Student** | Name, or email if they haven't set one |
| **Melodic**, **Harmonic**, **Holistic** | Average score over their 20 most recent attempts in that mode |
| **Rhythmic** | Average rhythm accuracy over their 20 most recent rhythmic attempts |

A dash (**—**) means no attempts in that mode yet.

> **Good to know.** These averages include *everything* the student has practised in that mode — free
> practice and other sections too — not only this section's work. The roster doesn't yet show which
> module exercises each student has completed.

### Removing a student from a section

1. Roster → **Remove** on their row.
2. The confirmation notes: *"The student can rejoin using the section join code if needed. Their
   attempt history will not be deleted."*
3. Press **Remove Student**.

To remove a student from the whole school, use **Manage School** instead ([section 6](#6-people)).

---

## 13. Getting students in

Students join in three steps, and the order matters:

1. **Create an account** on the site's **Register** page.
2. **Join the school.** Account menu → **My Classrooms** → under **Join a school**, enter the
   **school join code** → **Join School**. They'll see *"Joined school "…"! Now you can join classrooms
   at that school."*
3. **Join the section.** On the same page, under **Join a classroom**, enter the **section join code**
   → **Join**.

**Where the codes are:**

- **School join code** — **Manage School** → *School Join Code*. Only School Admins and Site Admins can
  see it, so your Section Teachers will need it from you.
- **Section join code** — on each section's card, at the top of its roster, and in the message shown
  when the section was created. Section join codes can't be changed.

If a student skips step 2 they'll see *"You must join school "…" first. Ask your teacher for the school
join code."*

---

## 14. Seeing the site as another role

Account menu → **View as** → **Section Teacher** or **Student**.

The site now behaves exactly as it would for that role: the menu changes, and pages that role couldn't
open are blocked for you too. A banner across the top reads *"Viewing as …. Pages beyond this role are
blocked, exactly as they would be for a real …"*

Press **Back to School Admin** in the banner to return. It stays visible on every page, so you can
always get back.

Use it to check what your Section Teachers and students will see before you hand things over.

---

## 15. When something goes wrong

| You see | What it means | What to do |
|---|---|---|
| A **Forbidden** page — *"You don't have the permission to access the requested resource."* | That page is for Site Admins, or belongs to another school | Go back with the account menu. |
| Students in a section suddenly see no modules | The section's course was removed — often by a Section Teacher saving Section Settings, or because the course was deleted | Edit the section, choose the course, **Save Changes**. If the course was deleted, its progress is gone. |
| A student reports *"No exercises match the filters for this module exercise. Ask your teacher to adjust the filters."* | That module exercise's filters match nothing in the library | Loosen its filters ([section 9](#9-module-exercises)). |
| *You must join school "…" first.* | The student skipped joining the school | Give them the school join code. |
| *Invalid school join code.* | A typo, or the code was regenerated | Share the current code from **Manage School**. |
| *No user with email "…".* / *No account found for "…".* | The person hasn't registered, or the email doesn't match | Ask them to register, then type the email exactly. |
| *You can only change the role of members below your own.* / *You can only remove members below your own role.* | They're a School Admin, like you | Ask a Site Admin. |
| *Only a site admin can appoint a school administrator.* | Appointing School Admins is Site Admin only | Ask a Site Admin. |
| *That course is not in a school you administer.* | You chose a course from another school | Choose one of your school's courses. |
| *All fields required.* | A section-only exercise was missing its type or ID | Fill in **Type** and **Exercise ID**. |
| A section you need isn't on **Sections I Teach** | That list only shows sections you created | Find it through **Manage School** → **Manage courses →** ([section 3](#3-getting-around)). |

---

## 16. Known issues

These are problems in the current version of the site. They're being tracked, and this guide will be
updated as they're fixed.

- **Section Teachers who save Section Settings remove the section's course.** Warn your teachers; fix it
  by choosing the course again ([section 10](#10-sections)).
- **Hide and Hide module don't hide anything from students** ([section 11](#11-section-overrides)).
- **Deleting a course also deletes all student progress** on it, and leaves its sections without a
  course. The confirmation doesn't say so ([section 7](#7-courses)).
- **Clef** and **Shortest Note Value** filters are ignored ([section 9](#9-module-exercises)).
- **Ticking several Time Signatures** drops that filter entirely ([section 9](#9-module-exercises)).
- **The live match count can be wrong** for Melodic and Rhythmic exercises — too high when Difficulty is
  set, too low when Clef or Shortest Note Value is set ([section 9](#9-module-exercises)).
- **Exercise IDs aren't shown anywhere**, so section-only exercises need the page-address workaround
  ([section 11](#11-section-overrides)).
- **"← Schools"** on the courses page leads to a Forbidden page ([section 7](#7-courses)).
- **Modules can't be renamed or re-ordered** after they're created ([section 8](#8-modules)).
- **Section Teachers see School Admin controls** — **Assign** and **Delete Section** — that lead to a
  Forbidden page.
- **Internal role names** such as `class_teacher` appear on the school page, and School Admins are also
  called "administrative teachers".
- **Two different pages are both titled "My Sections"** ([section 3](#3-getting-around)).

---

## 17. Quick reference

| To… | Go to |
|---|---|
| See or regenerate the school join code | **Manage School** → *School Join Code* → **Regenerate** |
| Add a teacher or student | **Manage School** → **Add member by email** |
| Change someone's role | **Manage School** → *Members* → role → **Set** |
| Remove someone from the school | **Manage School** → *Members* → **Remove** |
| Create a course | **Manage School** → **Manage courses →** → **Add** |
| Copy a course for next term | Courses → **Duplicate** |
| Add modules | Courses → click the course → **Add** |
| Add module exercises | Modules → click the module → **Add Exercise** |
| Create a section | **Sections I Teach** → **+ New section** |
| Find a section you didn't create | Courses → **Manage** in the *Sections* column → click it |
| Change a section's name or course | Section → **Edit** → *Section Settings* → **Save Changes** |
| Assign a Section Teacher | Section → **Edit** → *Assign Section Teacher* |
| Add an exercise to one section | Section → **Edit** → **+ Add exercise to this section only** |
| Open a roster | Click the section's name |
| Preview as a teacher or student | Account menu → **View as** |
