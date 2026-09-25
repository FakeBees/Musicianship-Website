# School Admin Guide

**Musicianship Trainer** · for the people who run a school's courses, sections and members

Checked against the site on September 21, 2026. Menu names and page addresses will change when the
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
9. [Assignments](#9-assignments)
10. [Sections](#10-sections)
11. [A section's own curriculum](#11-a-sections-own-curriculum)
12. [Rosters and progress](#12-rosters-and-progress)
13. [Getting students in](#13-getting-students-in)
14. [Seeing the site as another role](#14-seeing-the-site-as-another-role)
15. [When something goes wrong](#15-when-something-goes-wrong)
16. [Limitations](#16-limitations)
17. [Quick reference](#17-quick-reference)

---

## 1. Your role at a glance

You're a **School Admin**. You build your school's courses, create its sections, and manage its
people. A Site Admin appointed you.

| You can | Ask a Site Admin to |
|---|---|
| See and regenerate the school join code | Appoint or remove a School Admin |
| Add people to the school as Students or Section Teachers | Create or delete a school |
| Change the role of, or remove, members below you | Add, edit or delete exercises in the library |
| Create, rename, duplicate and delete courses | Delete a user account |
| Create and delete modules; add, edit, duplicate and remove assignments | Reset someone's password |
| Create, edit and delete sections; set their course and teacher | |
| Shape any section's own curriculum — hide course work, add its own modules and exercises | |
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

**Assignment.** One task inside a module, with a **completion rule**. See
[section 9](#9-assignments).

**Section.** A group of students taught together, usually named like a class section, such as
*MUS201-002*. **Students see the word "Classroom" instead of "Section" — it's the same thing.** A
section follows one course, which gives its students their modules. The School Admin who creates a
section is its **owner**, and it can also have one **Section Teacher** assigned.

**A section's own curriculum.** Each section sees its course's modules and exercises, **plus** anything
added for that section alone, **minus** anything hidden for it. Those changes never touch the course or
any other section. See [section 11](#11-a-sections-own-curriculum).

**Join codes.** Short codes students type to join. There are two — a **school join code** and a
**section join code** — and students need both, in that order.

```
School
 └─ Course                    e.g. Theory 1
     └─ Module                e.g. Intervals          (ordered)
         └─ Assignment   e.g. "Seconds"          (ordered, with a completion rule)

Section                       e.g. MUS201-002         (students see: Classroom)
 ├─ follows one Course        → gives students its modules
 ├─ its own additions         → modules and exercises for this section only
 ├─ its hides                 → course work this section doesn't see
 ├─ Owner                     → the School Admin who created it
 ├─ Section Teacher           → optional, one per section
 └─ Students                  → joined with the school code, then the section code
```

### Roles

| Role | Who they are |
|---|---|
| **Student** | Anyone who registers |
| **Section Teacher** | Teaches the sections assigned to them, and can shape those sections' curricula |
| **School Admin** | You |
| **Site Admin** | Runs the whole website |

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

Each page is titled to match the menu item or button that opens it.

> **Finding a section you didn't create.** **Sections I Teach** only lists sections *you* created. To
> reach any other section in your school: **Manage School** → **Manage courses →** → on the course's
> row, **Manage** in the *Sections* column → click the section's name. The course cards on **Home**
> (**View →**) lead to the same list.

---

## 4. Setting up a school: the checklist

The first time you set up your school, work through these in order.

1. **Check the school's join code.** **Manage School** → *School Join Code*. It should show a code. If it
   shows **—**, press **Regenerate**.
2. **Add your teachers.** They register first, then you add them as **Section Teacher**.
   See [section 6](#6-people).
3. **Build a course.** Create the course, then its modules, then each module's exercises.
   See sections [7](#7-courses), [8](#8-modules) and [9](#9-assignments).
4. **Create sections.** Choose the course while creating each one. See [section 10](#10-sections).
5. **Assign a Section Teacher** to each section. See [section 10](#10-sections).
6. **Share both join codes** with students. See [section 13](#13-getting-students-in).
7. **Check it as a student.** Use **View as → Student**. See
   [section 14](#14-seeing-the-site-as-another-role).

---

## 5. Your school page

Open the account menu → **Manage School**. The page is titled *<school> — Manage School*.

| Card | What it's for |
|---|---|
| **Your role here** | Shows *School Admin*. |
| **School Join Code** | The code students use to join your school, and the **Regenerate** button. Your Section Teachers see the code too, but can't regenerate it. |
| **Courses** | *"Create courses, edit modules, and see their sections."* → **Manage courses →** |
| **School Admins** | The school's School Admins. Read-only for you: *"Only a site admin can appoint a School Admin."* |
| **Add member by email** | Add a person to the school with a role. |
| **Members** | Everyone in the school, with controls to change roles and remove people. |

### Regenerating the school join code

1. Press **Regenerate** on the *School Join Code* card.
2. Confirm: *"Regenerate join code? The old code will stop working."*
3. The page shows *"Join code regenerated: …"* with the new code.

People who've already joined stay in the school. Only new joins need the new code. Do this if a code
has been shared somewhere it shouldn't have been — and let your Section Teachers know the new one is
on their rosters.

---

## 6. People

### Adding a teacher or a student

The person must already have an account.

1. Ask them to register on the site's **Register** page.
2. **Manage School** → **Add member by email**.
3. Type their email **exactly as they registered it**.
4. Choose a role: **Section Teacher** or **Student**.
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

If you change a Section Teacher to Student, they lose their teacher access. **Assign a new Section
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
2. **Manage School** → **Add member by email** → their email → **Section Teacher** → **Add**.
3. Open the section they'll teach → **Edit** → **Assign Section Teacher** → their email → **Assign**.
4. Send them the **Section Teacher Guide**. Both join codes are on their section's roster.

---

## 7. Courses

**Manage School** → **Manage courses →**. The page is titled *"<school> — Courses"*. The back link at
the top returns to your school's page.

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
assignments. Sections aren't copied, sections' own additions aren't copied, and no section follows
the copy until you choose it for one.

This is the easiest way to start next term's version of a course without disturbing this term's
students.

### Deleting a course

**Deleting a course deletes every section that follows it.** Because that's so much, it takes three
confirmation pages:

1. **Delete** on the course's row → *"Delete Course "…" — Step 1 of 3"*: *"Are you sure?"* →
   **Continue**.
2. *Step 2 of 3* lists everything that will go: each section following the course by name, with how
   many students are in it; the course's modules and exercises; and how many progress records. *"Are
   you sure?"* → **Continue**.
3. *Step 3 of 3*: *"Are you really sure? This can't be undone."* → **Delete permanently**.

**Cancel** on any page backs out without deleting anything.

What's deleted: the course, all its modules and exercises (including sections' own additions), every
section following it, and all students' progress in those sections. What's kept: the students' and
teachers' accounts, their school memberships, and their practice history outside those sections.

> If you only want a section to study something different, change that **section's** course instead
> ([section 10](#10-sections)) — nothing is deleted.

---

## 8. Modules

Click a course's name. The page is titled *"<course> — Modules"*.

### Creating a module

1. Type a **Module name**.
2. Type an **Order** number. Students see modules sorted by this number, lowest first.
3. Press **Add**. You'll see *"Module created."*

> **Tip.** Number your modules with gaps — 10, 20, 30 — rather than 1, 2, 3. Modules can't be
> re-ordered after they're created, so gaps leave room to slot a new module in between later, and let
> Section Teachers slot their own modules between yours.

### The modules table

Each row shows the module's order (**#**), its **Name** (click it to open its exercises), how many
**Assignments** it has with an **Assignments →** link, and **Delete**.

### Deleting a module

Press **Delete** and confirm. This deletes the module, all of its assignments — including any a
section added to it — and every student's progress on them.

> **Note.** Modules can't be renamed or re-ordered once created. To change one, create a replacement
> and delete the old one. Because deleting removes student progress, do this before students start.

---

## 9. Assignments

Click a module's name. The page is titled *"<module> — Assignments"*. This is where you decide what
students actually do.

### How assignments work

There are two kinds, and they behave differently:

- **Melodic, Rhythmic and Harmonic** assignments describe a *kind* of exercise using filters —
  difficulty, time signature, topic and so on. **Each time a student starts one, the site picks a
  random exercise from the library that matches your filters.** Students get variety, and repeat
  exercises give different material.
- **Holistic** assignments point at **one specific exercise** that you choose. Every student gets that
  same exercise.

An assignment is complete for a student once they meet its **completion rule**.

### Adding an assignment

1. Choose the **Type**: Melodic, Rhythmic, Harmonic or Holistic.
2. Give it a **Name** — this is what students see, such as *Basic Melodic Dictation*.
3. Set the **Order** — its position within the module, lowest first.
4. Choose a **Completion** rule (below).
5. **Holistic:** choose the exercise from the **Exercise** list.
   **Melodic, Rhythmic, Harmonic:** set the filters (below).
6. Check the **live match count**, which shows how many library exercises your filters currently
   select. Make sure it's above zero.
7. Press **Add Assignment**. You'll see *"Exercise added to module."*

### Completion rules

| Option | A student completes it when… | Example |
|---|---|---|
| **By number of exercises** | they've submitted it this many times, whatever they scored | *3 exercise(s) to complete* |
| **By passing score** | they've submitted this many times at or above the minimum score | *2 pass(es) at 80 % minimum score* |

The defaults are 1 exercise, or 1 pass at 70 %. The site records each student's best score either way.

What students see: a check mark and their best score once they've completed it, and a progress bar
whenever more than one exercise or pass is required.

### Filters

Filters appear for Melodic, Rhythmic and Harmonic exercises. **Leave a filter empty to allow
anything.**

| Filter | Used for | Ticking several boxes means |
|---|---|---|
| **Difficulty** — 1 to 5 stars | All three | any of them |
| **Time Signature** | Melodic, Rhythmic | any of them |
| **Shortest Note Value** | Melodic, Rhythmic | any of them |
| **Clef** | Melodic | any of them |
| **Category** — Diatonic, Chromatic, Mode Mixture, Modal | Harmonic | any of them |
| **Key Signature** — type one key, such as *C*, *G* or *Bb* | Harmonic | — one key only |
| **Topics** | All three | an exercise must have **all** of them |

Only the topics that exist for the chosen type are offered. The live match count reflects every filter,
so if it shows zero, students will have nothing to do.

### What happens if nothing matches

A student who starts the exercise sees *"No exercises match the filters for this assignment. Ask
your teacher to adjust the filters."* and can't complete it. Loosen the filters — usually Topics or Key
Signature are the culprits.

### The exercises table

Columns: order (**#**), **Name**, **Type**, **Filters / Exercise** (a summary of the filters, or which
holistic exercise), **Completion**, then the actions.

- **Edit** opens a panel with the same fields as the add form. For Holistic exercises you can change
  the name, order and completion rule, but not which exercise it is — *"To change the exercise, remove
  and re-add it."*
- **Duplicate** makes a copy you can then edit. Handy for *"the same thing, but harder"*.
- **Remove** takes it out of the module, after confirming *"Remove this exercise from the module?"*,
  along with students' progress on it.

This page shows only the course's own assignments. Anything a section added for itself lives on that
section's curriculum pages ([section 11](#11-a-sections-own-curriculum)).

---

## 10. Sections

### Creating a section

1. Account menu → **Sections I Teach** → **+ New section**.
2. **Section Name** — name it like a section number, such as *MUS201-002*.
3. **Course (optional)** — choose it now. *"Selecting a course gives students access to its modules."*
   Until a section has a course, it doesn't belong to your school, and you can't assign it a teacher or
   build its curriculum.
4. Press **Create Section**.

You'll see *"Section "…" created. Join code: …"* You're the new section's owner, and it appears on
**Sections I Teach**.

### The section card

On **Sections I Teach**, each card shows the section's name (click it for the roster), its **Join
code**, the number of students, and **View roster**, **Curriculum**, **Edit** and **Delete** buttons.

### Changing a section's name or course

1. Open the section → **Edit**.
2. On the **Section Settings** card, change **Section Name** or **Course**.
3. Press **Save Changes**. You'll see *"Section updated."*

Changing the course changes what students see immediately. Their progress on the previous course is
kept — it just isn't shown while the section follows a different course. Anything added to the section
for the old course is set aside the same way, and comes back if you switch the course back.

Section Teachers can rename their sections here too, but only you can change the course.

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
| *… is a Student in <school>, not a teacher. Change their school role first.* | Change their role to Section Teacher ([section 6](#6-people)). |

### Deleting a section

1. **Sections I Teach** → **Delete**, or the **Delete Section** link at the bottom of the Edit page.
2. Read the confirmation. It lists what will happen:
   - its students will be removed from the section
   - all of the section's own modules and exercises will be deleted
   - all its section-specific overrides will be deleted
   - students' module completion data for this section will be deleted
   - this cannot be undone
3. Press **Yes, delete "…"** — or **Cancel**.

Students stay in the school, and their overall practice history is kept.

---

## 11. A section's own curriculum

Every section has a **Curriculum** page — on its card, its roster, and its Edit page. Section Teachers
can use it for their sections, and you can use it for any section in your school. Changes here affect
only that one section.

### The Curriculum page

Titled *<section> — Curriculum*. It lists every module the section's students see, in order:

| Column | What it shows |
|---|---|
| **#** | The module's order |
| **Module** | Its name — click it to open the module's page |
| **Source** | **From course** — shared with every section on the course. **This Section only** — added for this section. **Hidden** — hidden from this section. |
| **Assignments** | How many assignments this section sees in it |

- **Hide module** / **Restore module** — for course modules. Hidden modules vanish from the section's
  module list, and students can't open them even with a direct link.
- **Delete** — for the section's own modules, after *"Delete module "…" and all its exercises? This
  cannot be undone."*
- **Add** — with a **Module name** and **Order**, adds a module for this section only.

### A module's page

Click a module's name. Titled *<section> — <module>*.

- **Course exercises** — with **Hide** and **Restore**.
- **This Section's own assignments** — with **Edit**, **Duplicate** and **Remove**.
- **Add Assignment** — the same form as the course's assignments page ([section 9](#9-assignments)):
  type, name, order, completion rule, filters or holistic exercise, and the live match count.

**Hiding is never deleting.** Students' progress on hidden work is kept, and reappears when it's restored.

**A section's own content belongs to the course it was made for.** If you switch the section to another
course, its additions are set aside, and they come back if you switch it back.

---

## 12. Rosters and progress

Open a section's name, or **View roster** on its card. The page is titled *<section> — Roster*.

At the top: the **Section code** and the **School code**, plus **Curriculum** and **Edit Section**
buttons. Below, one row per student, with their average score in each mode:

| Column | What it shows |
|---|---|
| **Student** | Name, or email if they haven't set one |
| **Melodic**, **Harmonic**, **Holistic** | Average score over their 20 most recent exercises in that mode |
| **Rhythmic** | Average rhythm accuracy over their 20 most recent rhythmic exercises |

A dash (**—**) means no exercises in that mode yet.

> **Good to know.** These averages include *everything* the student has practised in that mode — free
> practice and other sections too — not only this section's work. The roster doesn't yet show which
> assignments each student has completed.

### Removing a student from a section

1. Roster → **Remove** on their row.
2. The confirmation notes: *"The student can rejoin using the section join code if needed. Their
   exercise history will not be deleted."*
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

**Both codes are at the top of each section's roster**, where you and your Section Teachers can see
them. The school code is also on **Manage School**. Section join codes can't be changed.

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
| Students in a section suddenly see no modules | The section's course was removed or changed | Edit the section, choose the course, **Save Changes**. Progress isn't deleted — unless the course itself was deleted. |
| A student reports *"No exercises match the filters for this assignment. Ask your teacher to adjust the filters."* | That exercise's filters match nothing in the library | Loosen its filters — on the course's page ([section 9](#9-assignments)) if it's a course exercise, or on the section's curriculum pages if it's the section's own. |
| *"Delete not confirmed."* | A delete was sent without going through all three confirmation steps | Start again from the **Delete** button and use **Continue** on each page. |
| *You must join school "…" first.* | The student skipped joining the school | Give them the school code from the roster. |
| *Invalid school join code.* | A typo, or the code was regenerated | Share the current code from **Manage School**. |
| *No user with email "…".* / *No account found for "…".* | The person hasn't registered, or the email doesn't match | Ask them to register, then type the email exactly. |
| *You can only change the role of members below your own.* / *You can only remove members below your own role.* | They're a School Admin, like you | Ask a Site Admin. |
| *Only a site admin can appoint a school administrator.* | Appointing School Admins is Site Admin only | Ask a Site Admin. |
| *That course is not in a school you administer.* | You chose a course from another school | Choose one of your school's courses. |
| A section you need isn't on **Sections I Teach** | That list only shows sections you created | Find it through **Manage School** → **Manage courses →** ([section 3](#3-getting-around)). |

---

## 16. Limitations

Nothing currently known is broken for School Admins. These are limits of the current design:

- **Modules can't be renamed or re-ordered** after they're created ([section 8](#8-modules)).
- **A section's owner can't be changed.** The School Admin who created a section always owns it.
- **The roster shows averages across all practice**, not which of the section's exercises each student
  has completed ([section 12](#12-rosters-and-progress)).

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
| Delete a course and its sections | Courses → **Delete** → three confirmation pages |
| Add modules | Courses → click the course → **Add** |
| Add assignments | Modules → click the module → **Add Assignment** |
| Create a section | **Sections I Teach** → **+ New section** |
| Find a section you didn't create | Courses → **Manage** in the *Sections* column → click it |
| Change a section's name or course | Section → **Edit** → *Section Settings* → **Save Changes** |
| Assign a Section Teacher | Section → **Edit** → *Assign Section Teacher* |
| Hide course work from one section | Section → **Curriculum** → **Hide module**, or a module's **Hide** |
| Add to one section's curriculum | Section → **Curriculum** → **Add**, or a module's **Add Assignment** |
| Open a roster | Click the section's name |
| Preview as a teacher or student | Account menu → **View as** |
