# Site Admin Guide

**Musicianship Trainer** · for the people who run the whole website

Checked against the site on September 21, 2026. Menu names and page addresses will change when the
planned admin reorganisation lands; the tasks themselves won't. The other two guides are the
**School Admin Guide** and the **Section Teacher Guide** — hand those to the people in those roles.

---

## Contents

**Part 1 — Running the platform**
1. [Your role at a glance](#1-your-role-at-a-glance)
2. [Key ideas](#2-key-ideas)
3. [Getting around](#3-getting-around)
4. [The Admin dashboard](#4-the-admin-dashboard)
5. [Schools](#5-schools)
6. [School Admins](#6-school-admins)
7. [Users and accounts](#7-users-and-accounts)

**Part 2 — Running a school**
8. [People in a school](#8-people-in-a-school)
9. [Courses, modules and module exercises](#9-courses-modules-and-module-exercises)
10. [Sections and their curricula](#10-sections-and-their-curricula)
11. [Getting students in](#11-getting-students-in)

**Part 3 — The exercise library**
12. [How the library works](#12-how-the-library-works)
13. [Melodies](#13-melodies)
14. [The melody generator](#14-the-melody-generator)
15. [GenProgressions](#15-genprogressions)
16. [Rhythms](#16-rhythms)
17. [Chord progressions](#17-chord-progressions)
18. [Holistic exercises](#18-holistic-exercises)
19. [Visibility, tags and containers](#19-visibility-tags-and-containers)

**Part 4 — Reference**
20. [Previewing other roles](#20-previewing-other-roles)
21. [When something goes wrong](#21-when-something-goes-wrong)
22. [Known issues and limitations](#22-known-issues-and-limitations)
23. [Quick reference](#23-quick-reference)

---

# Part 1 — Running the platform

## 1. Your role at a glance

You're a **Site Admin**: you have authority over every school, every user account, and the exercise
library. Inside any school you can do everything that school's School Admin can, and more.

**Only a Site Admin can:**

- create and delete schools
- appoint and remove School Admins
- see every user account, and delete accounts
- upload, generate, edit and delete exercises in the library
- create and edit GenProgressions for the melody generator

**Nobody can do these in the app** — they need access to the server or the database:

- reset a password
- make another account a Site Admin
- create new tags or containers

---

## 2. Key ideas

### Roles

| Role | Who they are |
|---|---|
| **Student** | Anyone who registers |
| **Section Teacher** | Teaches the sections assigned to them, and can shape those sections' curricula |
| **School Admin** | Runs one school's courses, sections and members |
| **Site Admin** | You |

Three rules govern every role:

1. **Everyone registers as a Student.** There's no sign-up for staff.
2. **Staff roles come from schools.** Someone's account role follows their highest role in any school.
   Give them Section Teacher in a school and their account becomes a Section Teacher account; remove
   their last staff role and it returns to Student. **Site Admin is the exception** — it's set on the
   account itself, and school memberships never change it.
3. **You can only grant or remove roles below your own.** That's why only a Site Admin can appoint a
   School Admin, and why a School Admin can't create another.

In the database, roles are stored as `student`, `class_teacher`, `admin_teacher` and `admin`. You'll only
need those names for tasks done outside the app ([section 7](#7-users-and-accounts)).

### The building blocks

**School** → owns **Courses** → made of ordered **Modules** → made of ordered **Module exercises**,
each with a completion rule.

**Section** — a group of students taught together, such as *MUS201-002*. **Students see the word
"Classroom" instead.** A section follows one course, has an **owner** (whoever created it), can have one
assigned **Section Teacher**, and holds its students. A section only belongs to a school *through its
course*, so a section with no course isn't part of any school.

**A section's own curriculum** — each section sees its course's modules and exercises, **plus** anything
added for that section alone, **minus** anything hidden for it. Those changes never touch the course or
any other section.

**Join codes** — students join a school with its **school join code**, then a section with its **section
join code**, in that order.

**The exercise library** — four types of content (Melodic, Rhythmic, Harmonic and Holistic), shared by
every school. Students use it in free practice (**Sandbox**) and through module exercises.

```
School
 └─ Course                    e.g. Theory 1
     └─ Module                e.g. Intervals
         └─ Module exercise   e.g. "Seconds" — draws from the library

Section                       e.g. MUS201-002         (students see: Classroom)
 ├─ follows one Course
 ├─ its own additions and hides
 ├─ Owner + optional Section Teacher
 └─ Students

Exercise library              Melodies · Rhythms · Chord progressions · Holistic exercises
 └─ GenProgressions           templates the melody generator builds on
```

---

## 3. Getting around

Everything starts from the **account menu** in the top-right corner of every page.

| Menu item | Takes you to |
|---|---|
| **Sections I Teach** | Sections you created, with **+ New section**. |
| **My Sections** | Sections you're enrolled in *as a participant*, plus join-code forms. |
| **Admin** | The Admin dashboard — your starting point for everything in this guide. |
| **Home** | The home page, including free practice (**Sandbox**). |
| **My Progress** | Your own practice history. |
| **View as** | Preview the site as any lower role. See [section 20](#20-previewing-other-roles). |
| **Log out** | |

> **There's no "Manage School" item for Site Admins.** School Admins and Section Teachers have one; you
> reach any school through **Admin** → *Schools* → **Manage →** → **Manage School**.

---

## 4. The Admin dashboard

Account menu → **Admin**.

**Site Overview**

| Card | Links |
|---|---|
| **Users** — how many accounts exist | *None on this card — see the Schools card* |
| **Schools** — how many schools | **Manage →** (the schools list) and **Users →** (the user list) |
| **Sections** — how many sections exist | *None* |
| **GenProgressions** — how many | **Manage →** |

**Exercise Library** — one card each for **Melodies**, **Chord Progressions**, **Rhythms** and
**Holistic Exercises**, with a count and **Manage →**. Each card is named after the page it opens.

> The link to the user list lives on the **Schools** card, not the Users card.

---

## 5. Schools

Admin → *Schools* → **Manage →**. The page is titled *Schools*.

The table shows each school's **Name** (click it for the school page), how many **Courses** it has
(with **Manage** to open them), how many **Students** and **Teachers**, its **Join Code**, and
**Manage School** and **Delete** buttons.

### Creating a school

1. Type the name into **New school name** and press **Add**. School names must be unique. You'll see
   *"School created."* The new school gets a join code automatically.
2. **Appoint a School Admin.** See [section 6](#6-school-admins).

### The school page

Press **Manage School**, or click the school's name. The page is titled *<school> — Manage School* and
shows:

| Card | What it's for |
|---|---|
| **Your role here** | Shows *Site Admin* |
| **School Join Code** | The code, and **Regenerate** |
| **Courses** | **Manage courses →** |
| **School Admins** | The school's School Admins, and the form to appoint one |
| **Add member by email** | Add anyone to the school with any role below yours |
| **Members** | Everyone in the school, with role changes and removal |

**← Schools** at the top returns to the schools list.

### Regenerating a join code

**Regenerate** → confirm *"Regenerate join code? The old code will stop working."* → the page shows
*"Join code regenerated: …"*. Existing members stay in; only new joins need the new code.

### Deleting a school

**Deleting a school deletes all of its courses and every section following them.** It takes three
confirmation pages:

1. **Delete** on the school's row → *"Delete School "…" — Step 1 of 3"*: *"Are you sure?"* →
   **Continue**.
2. *Step 2 of 3* lists everything that will go: the school's courses by name; each section following
   them, with how many students are in it; the modules and progress records; and how many member
   accounts are affected. *"Are you sure?"* → **Continue**.
3. *Step 3 of 3*: *"Are you really sure? This can't be undone."* → **Delete permanently**.

**Cancel** on any page backs out without deleting anything.

What's deleted: the school, its courses with all their modules and exercises, every section following
those courses, all progress in them, and every school membership. What's kept: **every member's
account** — their roles are recalculated from whatever other schools they belong to — and any library
content that was tied to the school, which stays in the library.

---

## 6. School Admins

### Appointing a School Admin

The person must already have an account.

1. Open the school's page (*Schools* → **Manage School**).
2. On the **School Admins** card, type their email and press **Make School Admin**.

*"Works whether or not they are already a member — they will be added or promoted."* Their account
becomes a School Admin account immediately. A school can have several School Admins, and one person can
be School Admin of several schools.

| Message | Meaning |
|---|---|
| *No account found for "…".* | They haven't registered, or the email doesn't match. |
| *… already administers ….* | Nothing to do. |

### Stepping a School Admin down

On the school page's *Members* table, change their role to **Section Teacher** or **Student** and press
**Set**. *"To step someone down, change their role in the members table below."*

### Removing a School Admin from a school

On the *Members* table, press **Remove** and confirm. If they own sections in that school you'll see
*"… still owns N sections here (…). Reassign or delete them first."*

> There's no way to change a section's owner in the app, so those sections have to be deleted before the
> person can be removed from the school. If you only want to take away their admin powers, **step them
> down** instead.

Once a School Admin is set up, send them the **School Admin Guide**.

---

## 7. Users and accounts

Admin → *Schools* card → **Users →**. The page is titled *Users*.

The table shows each account's **Email**, **Name**, **Role**, when they **Joined**, and **Delete**. Your
own row is marked **(you)**.

There's no screen to edit an account's name, email or role. Roles change through school membership
([section 2](#2-key-ideas)).

### Deleting an account

It takes three confirmation pages:

1. **Delete** on the user's row → *"Delete User "…" — Step 1 of 3"*: *"Are you sure?"* → **Continue**.
2. *Step 2 of 3* lists everything that will go: sections they **own**, which are deleted with all their
   content and progress; sections where they're the **assigned teacher**, which are kept and just
   unassigned; sections they're a **member** of; and their practice attempts, progress records and
   school memberships. *"Are you sure?"* → **Continue**.
3. *Step 3 of 3*: *"Are you really sure? This can't be undone."* → **Delete permanently**.

What's deleted: the account, every section it owns (and everything in them), its practice history in all
four modes, its progress records, and its school memberships.

You can't delete your own account, at any step: *"You cannot delete your own account."*

> To take away someone's access without deleting anything, remove them from their school instead
> ([section 8](#8-people-in-a-school)).

### Resetting a password

There's no *forgot password* feature in the app. Someone with access to the server resets passwords from
the project folder:

```
.venv/bin/python reset_password.py their@email.com
```

It asks for the new password without showing it on screen. With no email given, it resets the main admin
account.

### Making another Site Admin

There's no screen for this. It requires setting that account's role to `admin` directly in the database.
Once set, nothing in the app — including school membership changes — will lower it.

---

# Part 2 — Running a school

You can act inside any school. Open it from Admin → *Schools* → **Manage School**. Everything School
Admins do, you can do too; the **School Admin Guide** walks through each task in more detail, and the
essentials are here.

## 8. People in a school

On the school page:

- **Add member by email** — type the email exactly as registered, choose a role, press **Add**. You can
  grant **Student**, **Section Teacher** or **School Admin**. The person must already have an account.
- **Change a role** — *Members* table → choose the role → **Set**.
- **Remove** — *Members* table → **Remove** → confirm. This drops them from **every section** in the
  school and unassigns them from any section they teach. Their practice history and completion records
  are kept.

If you demote a Section Teacher, assign a new teacher to the sections they were teaching.

---

## 9. Courses, modules and module exercises

School page → **Manage courses →**.

### Courses

- **Create** — **New course name** → **Add**.
- **Rename** — **Rename** → edit → **Save**.
- **Duplicate** — creates *"<name> (copy)"* with copies of all its modules and module exercises. Sections,
  and sections' own additions, aren't copied. Good for starting next term's version.
- **Delete** — three confirmation pages, like deleting a school. **Deleting a course deletes every section
  following it**, with all their progress, and all the course's modules and exercises. Step 2 lists the
  sections by name and how many students are in each. To change what one section studies, change that
  section's course instead.

### Modules

Click a course's name.

- **Create** — **Module name** + **Order** → **Add**. Students see modules sorted by order, lowest first.
  Number with gaps (10, 20, 30): modules can't be renamed or re-ordered later, and gaps leave room for
  sections' own modules.
- **Delete** — confirm. Deletes the module, its module exercises (including sections' additions to it),
  and student progress on them.

### Module exercises

Click a module's name.

**How they work.** **Melodic, Rhythmic and Harmonic** module exercises describe a *kind* of exercise with
filters; each time a student starts one, the site picks a **random library exercise that matches**.
**Holistic** module exercises point at **one specific exercise**.

**To add one:** choose the **Type** → give it a **Name** (what students see) → set the **Order** → choose
a **Completion** rule → for Holistic, pick the **Exercise**; otherwise set filters → check the live match
count is above zero → **Add Exercise**.

**Completion rules**

| Option | Complete when the student… | Default |
|---|---|---|
| **By attempts** | has submitted it this many times, whatever the score | 1 attempt |
| **By passing score** | has submitted it this many times at or above the minimum score | 1 pass at 70 % |

**Filters** — leave one empty to allow anything.

| Filter | Used for | Ticking several means |
|---|---|---|
| **Difficulty** (1–5 stars) | All three | any of them |
| **Time Signature** | Melodic, Rhythmic | any of them |
| **Shortest Note Value** | Melodic, Rhythmic | any of them |
| **Clef** | Melodic | any of them |
| **Category** — Diatonic, Chromatic, Mode Mixture, Modal | Harmonic | any of them |
| **Key Signature** | Harmonic | — one key, such as *C* or *Bb* |
| **Topics** | All three | must have **all** of them |

Filters only draw from exercises whose visibility is **public** ([section 19](#19-visibility-tags-and-containers)).
The live match count reflects every filter.

If nothing matches, students who start it see *"No exercises match the filters for this module exercise.
Ask your teacher to adjust the filters."* and can't complete it.

**The exercises table** has **Edit** (Holistic exercises can't change which exercise they point at —
remove and re-add), **Duplicate**, and **Remove**. It shows only the course's own exercises; sections'
additions live on their curriculum pages.

---

## 10. Sections and their curricula

### Creating a section

Account menu → **Sections I Teach** → **+ New section** → **Section Name** (like *MUS201-002*) →
**Course** (shown as *School / Course*; choose it now) → **Create Section**. The message shows the new
join code. You become the section's owner.

### Finding sections

**Sections I Teach** lists only sections you created. For any other section: the school page →
**Manage courses →** → **Manage** in the course's *Sections* column → click the section's name.

> A section with **no course** doesn't belong to any school, so it only appears on its owner's
> **Sections I Teach**. There's no way to list every section on the site.

### The Edit page

Open a section → **Edit**.

- **Section Settings** — **Section Name** and **Course** → **Save Changes**. Section Teachers can rename
  their sections, but only admins can change the course.
- **Assign Section Teacher** — email → **Assign**; **Clear** to unassign. The person must already be a
  Section Teacher or School Admin in the section's school, and the section must have a course.
- **Curriculum →** — the section's curriculum page (below).
- **Delete Section** — the confirmation lists what's lost: students removed from the section, its own
  modules and exercises, its overrides, and its module completion data. No undo.

### A section's own curriculum

Every section has a **Curriculum** page (*<section> — Curriculum*), reachable from its card, roster and
Edit page. Its Section Teacher can use it, and so can the school's School Admins and you.

- The module list shows each module's **Source**: **From course**, **This Section only**, or **Hidden**.
- **Hide module** / **Restore module** for course modules; hidden work vanishes for that section's
  students, even from direct links. Nothing is deleted.
- **Add** (a **Module name** and **Order**) creates a module for this section only; its own modules can
  be deleted.
- A module's page (*<section> — <module>*) lists the **Course exercises** with **Hide** / **Restore**, the
  section's own exercises with **Edit** / **Duplicate** / **Remove**, and **Add Exercise** — the same full
  form as the course's module-exercises page.

A section's own content belongs to the course it was made for: switch the section to another course and
its additions are set aside; switch back and they return.

### Rosters

Click a section's name. The page (*<section> — Roster*) shows the **Section code** and **School code**,
then one row per student with their average over their 20 most recent attempts in each mode (rhythm
accuracy for **Rhythmic**). These averages cover all of the student's practice, not just this section.
**Remove** takes a student out of the section, keeping their history.

---

## 11. Getting students in

1. The student **registers**.
2. Account menu → **My Classrooms** → **Join a school** → school join code → **Join School**.
3. Same page → **Join a classroom** → section join code → **Join**.

Both codes are at the top of every section's roster, where teachers can hand them out. The school code
is also on the school page. Section join codes can't be changed.

---

# Part 3 — The exercise library

## 12. How the library works

The library holds four types of content, shared by every school:

| Type | Students… | Public ID | Created by |
|---|---|---|---|
| **Melodies** | hear a melody and notate it | `MEL-0001` | Uploading MIDI, or the melody generator |
| **Rhythms** | hear a rhythm and notate it | `RHY-0001` | Uploading MIDI |
| **Chord progressions** | hear chords and identify them | `HRM-0001` | Uploading MIDI |
| **Holistic** | hear a recording and transcribe several parts | `HOL-0001` | Uploading WAV, then adding a MIDI file per part |

**Where content shows up:** in free practice (**Sandbox**), and in module exercises — drawn at random by
filters for Melodic, Rhythmic and Harmonic, or picked individually for Holistic.

**Every list page works the same way:** a title with the count, upload buttons at the top, a search box
and filters, and a table. **Click a name** or press **Edit** to open it, **Del** to delete it. Search
matches names and public IDs.

**Every piece of content has:** a name and description, a **Difficulty** from 1 to 5, **Tags** (shown to
teachers as *Topics*), and **Visibility**.

**Uploads always finish on the Edit page**, so you can fill in anything the upload form didn't ask for.

**Deleting** asks you to confirm: *"This cannot be undone. Existing student attempt records referencing
this exercise will remain but the exercise will no longer be playable."*

> **Before deleting content,** remember that module exercises may depend on it. A Holistic module exercise
> pointing at a deleted exercise will break, and Melodic, Rhythmic or Harmonic filters that matched only
> this content will start telling students that nothing matches.

---

## 13. Melodies

Admin → *Melodies* → **Manage →**. The page is titled *Melodies (N)*.

**Filters:** search by name or ID, **All tags**, **All containers**, **Any difficulty** → **Filter**.
**Columns:** ID, Name, Key, Time, Clef, Diff, Container, Tags.

### Uploading a melody from MIDI

1. **Upload MIDI**. The page is titled *Upload Melody from MIDI*.
2. **MIDI File** — required; must be a `.mid` file.
3. **Melody Name** — leave blank to use the file name.
4. **Key Signature**.
5. **Time Signature** — required.
6. **Tempo (BPM)** — required.
7. **Upload & Parse**. You'll land on its Edit page with *"Melody "…" uploaded (MEL-…)."*
8. **The upload form doesn't ask for Difficulty or Tags** — set them now on the Edit page, then
   **Save Changes**.

### Editing a melody

Fields: **Name**, **Description**, **Key**, **Time Sig**, **Clef**, **Min Duration**, **Tempo (BPM)**,
**Difficulty**, **Visibility**, **Container**, **Tags**, and **Notes JSON**.

> **Notes JSON (edit with care)** is the melody's raw note data. A mistake here can break the exercise
> for students. Change it only if you know the format.

---

## 14. The melody generator

Melodies → **Generate →**. The generator composes a new melody over a chord progression, lets you hear and
see it, and only saves it if you approve it.

You need at least one GenProgression first ([section 15](#15-genprogressions)).

### Generating

Set the **Parameters**:

| Parameter | What it does |
|---|---|
| **GenProgression** * | The chord progression to build over (required) |
| **Key**, **Mode** | Major or minor, in any key |
| **Time Sig**, **Measures** | Meter and length |
| **Clef**, **Min Duration**, **Tempo (BPM)** | Notation and playback |
| **Contour** — **Start**, **Peak**, **Low** | The melody's range, as MIDI note numbers (60 is middle C) |
| **Rhythm** — **Complexity (1–3)**, **Syncopation** | How busy and off-beat the rhythm is |
| **Ornament Techniques** | Notes to decorate the chord tones with, such as passing tones, neighbor tones, escape tones, appoggiaturas and suspensions |
| **Random seed** | Blank gives a different melody each time; a number reproduces the same melody for the same settings |

Press **Generate →**. The **Sheet Music Preview** shows the melody with a suggested difficulty. Use
**▶ Play** and **■ Stop** to listen.

### Keeping or discarding it

- **Keep it:** under **Approve & Save**, enter a **Name** (required), and optionally a **Description**,
  **Difficulty**, **Container** and **Tags** → **✓ Approve & Save**. It's saved to the library and opens
  on its Edit page.
- **Discard it:** **✗ Reject — Discard** → *"Melody discarded. Generate another."*

---

## 15. GenProgressions

GenProgressions are chord-progression templates for the melody generator. Students never see them.

Admin → *GenProgressions* → **Manage →**. The page is titled *GenProgressions (N)*.

### Creating one

1. **+ New**.
2. **Number** — leave blank to number it automatically.
3. **Name**, **Length (bars)**, **Mode** (Major or Minor), **Difficulty**.
4. **Create → Build Chords**. You'll land on its Edit page.

### Building the chords

On the Edit page, under **Chord Progression Builder**:

1. Click chords in the **Diatonic chords** palette to add them to the progression, in order.
2. Click a chord block in the progression to select it, then use the modifier panel to change it.
3. **Undo Last** removes the most recent chord; **Clear All** starts over.
4. **Save Changes**.

The list page's **Chord Preview** column shows each progression's chords. Filter by name, **All modes**,
or **All difficulties**. Delete with **Del**, or **Delete** on the Edit page.

---

## 16. Rhythms

Admin → *Rhythms* → **Manage →**.

### Uploading a rhythm from MIDI

**Upload MIDI** → **MIDI File** (`.mid`) → **Name** (blank uses the file name) → **Time Signature**
(required) → **Min Duration** → **Difficulty** → **Tempo (BPM)** (required) → **Tags** →
**Upload & Parse**. You'll land on its Edit page.

### Editing a rhythm

Fields: **Name**, **Description**, **Time Signature**, **Min Duration**, **Difficulty**, **Tempo**,
**Visibility**, **Tags**, and **Notes JSON** (raw note data — edit with care).

---

## 17. Chord progressions

Admin → *Chord Progressions* → **Manage →**.

### Uploading a progression from MIDI

**Upload MIDI** → **MIDI File** (required, `.mid`) → **Progression Name** (blank uses the file name) →
**Key Signature** → **Category** → **Tempo (BPM)** (required) → **Difficulty** → **Tags** →
**Upload & Parse**. You'll land on its Edit page.

**Category** is one of Diatonic, Chromatic, Mode Mixture or Modal. Teachers filter harmonic module
exercises by it, so set it carefully.

### Editing a progression

Fields: **Name**, **Description**, **Key**, **Tempo (BPM)**, **Difficulty**, **Visibility**, **Category**,
**Tags**, and **Chords JSON** (raw chord data — edit with care).

---

## 18. Holistic exercises

A holistic exercise is a recording with several parts, such as a melody, a bass line and chords.
Students transcribe each part. Creating one takes **two steps**.

Admin → *Holistic Exercises* → **Manage →**.

### Step 1 — Upload the recording

**Upload WAV** → **Name** (optional; defaults to the file name) → **Key Signature** → **Time Signature**
(required) → **Tempo (BPM)** (required) → **WAV File** (required, `.wav`) → **Upload**.

You'll land on its Edit page with *"Exercise "…" uploaded (HOL-…). Now add lines below."*

### Step 2 — Add the lines

Each **line** is one part students transcribe. Under **Lines**, for each part:

1. **Name** — such as *Melody* or *Bass*.
2. **Type** — Melodic, Rhythmic or Harmonic.
3. **Clef** — Treble, Bass, Alto or Tenor.
4. **MIDI File** — the correct answer for that part, as a `.mid` file.
5. **Add**. You'll see *"Line "…" added."*

**Drag** lines to reorder them. **Remove** deletes a line after *"Remove this line?"* With many lines, the
page warns that they *"may be hard to read for students."*

Finish by setting **Difficulty**, **Tags** and **Visibility**, then **Save Changes**.

---

## 19. Visibility, tags and containers

### Visibility

Each exercise's Edit page has **Visibility**: `public` or `private`.

> **⚠️ "private" hides an exercise from every student, everywhere.**
>
> A private exercise doesn't appear in free practice, and filter-based module exercises can't select it.
> If a module exercise's filters matched only private content, students will be told nothing matches.
> There's also no option to make content visible to just one school, even though the site partly
> supports it. **Leave content public unless you mean to take it out of use.** (Known issue D18.)

### Tags

Tick tags on any upload or Edit page. Teachers see them as **Topics** when filtering module exercises,
and a module exercise must match **all** the topics it ticks — so tag consistently.

You can assign tags but not create new ones in the app.

### Containers

Containers group melodies for organising the library. Assign one on a melody's Edit page, or when
approving a generated melody, and filter the melody list by container. They apply to melodies only, and
new ones can't be created in the app.

---

# Part 4 — Reference

## 20. Previewing other roles

Account menu → **View as** → **School Admin**, **Section Teacher** or **Student**.

The site now behaves exactly as it would for that role, and pages beyond it are blocked for you. A banner
reads *"Viewing as …. Pages beyond this role are blocked, exactly as they would be for a real …"*
Press **Back to Site Admin** in the banner to return; it's on every page, so you can always get back.

> **You lose your Site Admin reach while previewing.** As a School Admin or Section Teacher you only have
> access where your own account is actually a member, so most schools' pages will be blocked. Previewing
> is best for checking menus, layouts and the student experience.

---

## 21. When something goes wrong

| You see | What it means | What to do |
|---|---|---|
| *"Delete not confirmed."* | A delete was sent without going through all three confirmation steps | Start again from the **Delete** button and use **Continue** on each page. |
| A **Forbidden** page | You're previewing a lower role, or it's a page for someone else | Press **Back to Site Admin** in the banner. |
| *Please upload a .mid file.* / *Please upload a .wav file.* | Wrong file type | Check the file extension. |
| *Time signature is required.* / *BPM is required and must be a number.* | A required upload field was empty | Fill it in and upload again. |
| *Please select a GenProgression.* | The generator needs a progression | Choose one, or create one first ([section 15](#15-genprogressions)). |
| *Generation error: …* | The generator couldn't build a melody with those settings | Check that the contour's **Low**, **Start** and **Peak** make sense together, then try again or choose another GenProgression. |
| *No pending melody to approve.* | That preview was already saved or discarded, or your session expired | Generate again. |
| *Invalid JSON in chords field.* | The chord builder's data was malformed | Reload the Edit page and rebuild the chords. |
| *Line name and a valid type are required.* | A holistic line was missing its name or type | Fill both in. |
| *No account found for "…".* / *No user with email "…".* | Not registered, or the email doesn't match | Ask them to register; type the email exactly. |
| *… still owns N sections here (…). Reassign or delete them first.* | You're removing someone who created sections in that school | Delete those sections first, or step them down instead ([section 6](#6-school-admins)). |
| Students report *"No exercises match the filters…"* | A module exercise's filters match no public content | Loosen the filters, check content visibility, or add library content. |
| A school says its students suddenly see no modules | A section's course was removed or changed | Re-choose the course on the section's Edit page. A deleted course can't be recovered. |

---

## 22. Known issues and limitations

### Known issues

| ID | Issue | Workaround |
|---|---|---|
| **D18** | Visibility `private` hides content from every student and every filter-based module exercise, and there's no school-only option | Keep content public ([section 19](#19-visibility-tags-and-containers)) |

The IDs refer to `docs/superpowers/specs/2026-09-10-admin-ia-refactor-design.md`, which lists every defect
found and fixed.

### Limitations

These aren't bugs, but they're worth knowing:

- No in-app password reset — use `reset_password.py` ([section 7](#7-users-and-accounts)).
- No screen to make a Site Admin, or to create tags or containers.
- No way to edit an account's name, email or role directly.
- Modules can't be renamed or re-ordered after creation.
- A section's owner can't be changed.
- There's no list of every section on the site; sections without a course are only visible to their owner.
- The roster shows mode averages across all practice, not per-exercise completion for the section.
- The melody upload form doesn't ask for Difficulty or Tags; set them on the Edit page afterwards.

---

## 23. Quick reference

| To… | Go to |
|---|---|
| Open the Admin dashboard | Account menu → **Admin** |
| Create a school | Admin → *Schools* **Manage →** → **Add** |
| Open a school | *Schools* → **Manage School** |
| Delete a school, user or course | Its **Delete** button → three confirmation pages |
| Appoint a School Admin | School page → *School Admins* → **Make School Admin** |
| Step a School Admin down | School page → *Members* → role → **Set** |
| See all users | Admin → *Schools* card → **Users →** |
| Reset a password | Server: `.venv/bin/python reset_password.py their@email.com` |
| Upload a melody, rhythm or progression | Its list page → **Upload MIDI** |
| Generate a melody | Melodies → **Generate →** |
| Create a GenProgression | Admin → *GenProgressions* **Manage →** → **+ New** |
| Create a holistic exercise | Holistic Exercises → **Upload WAV**, then add lines on the Edit page |
| Shape one section's curriculum | The section → **Curriculum** |
| Hide content from students | Edit → **Visibility** → `private` (see D18 first) |
| Preview another role | Account menu → **View as** |
| Return from a preview | **Back to Site Admin** in the banner |
