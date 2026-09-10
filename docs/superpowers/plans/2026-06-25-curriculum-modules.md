# Curriculum & Module System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a School → Course → Class → Module curriculum hierarchy with a "Study by Module" student mode alongside the existing Sandbox mode, plus exercise visibility tiers (public / school / module-only).

**Architecture:** New SQLAlchemy models (School, Course, Module, ModuleExercise, ClassModuleExercise, ModuleCompletion) extend the existing Class model; a `curriculum.py` helper resolves the effective exercise list for a class; existing drill routes gain a thin module-context layer that tracks completion and navigates the student to the next exercise.

**Tech Stack:** Flask, SQLAlchemy (SQLite), Jinja2, Bootstrap 5; no new JS libraries; migration via `migrate_curriculum.py` script.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `models.py` | Modify | Add School, Course, Module, ModuleExercise, ClassModuleExercise, ModuleCompletion; add `course_id` to Class; add `visibility` + `school_id` to all four exercise models |
| `migrate_curriculum.py` | Create | `db.create_all()` + ALTER TABLE for new columns on existing tables |
| `curriculum.py` | Create | Helper: resolve effective module exercises for a class; check/mark completion |
| `app.py` | Modify | Admin CRUD routes (schools, courses, modules, module exercises); teacher class-course assignment + override UI; student mode selector; module navigation; sandbox visibility filter |
| `templates/admin/schools.html` | Create | List / create schools |
| `templates/admin/courses.html` | Create | List / create courses under a school |
| `templates/admin/modules.html` | Create | List / create modules under a course |
| `templates/admin/module_exercises.html` | Create | List / add exercises to a module |
| `templates/teacher/class_detail.html` | Modify | Add course assignment + override section to existing template |
| `templates/student/mode_select.html` | Create | Sandbox vs Study by Module picker (shown on class home) |
| `templates/student/module_list.html` | Create | List of modules in the class with completion badges |
| `templates/student/module_detail.html` | Create | Exercises in a module with completion status |
| `templates/me.html` | Modify | Add per-module completion section |

---

## Task 1: New Models

**Files:**
- Modify: `models.py`

- [ ] **Step 1: Add visibility + school_id columns to all four exercise models**

Add to `Melody`, `Rhythm`, `ChordProgression`, and `HolisticExercise` (after their existing `difficulty` column):

```python
visibility = db.Column(db.String(20), nullable=False, default='public')
# 'public' | 'school' | 'module'
school_id  = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=True)
```

Note: `school_id` FK references `school` table which we add in this same step. In SQLite forward references work fine.

- [ ] **Step 2: Add School model (before Class)**

```python
class School(db.Model):
    __tablename__ = 'school'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    courses = db.relationship('Course', backref='school', lazy='dynamic')

    def __repr__(self):
        return f'<School {self.name}>'
```

- [ ] **Step 3: Add Course model**

```python
class Course(db.Model):
    __tablename__ = 'course'
    id        = db.Column(db.Integer, primary_key=True)
    name      = db.Column(db.String(120), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    modules = db.relationship('Module', backref='course', lazy='dynamic',
                              order_by='Module.order')

    def __repr__(self):
        return f'<Course {self.name}>'
```

- [ ] **Step 4: Add course_id FK to Class model**

In the existing `Class` model, add:

```python
course_id  = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)
course     = db.relationship('Course', backref='classes')
```

- [ ] **Step 5: Add Module model**

```python
class Module(db.Model):
    __tablename__ = 'module'
    id        = db.Column(db.Integer, primary_key=True)
    name      = db.Column(db.String(120), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    order     = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    exercises = db.relationship('ModuleExercise', backref='module', lazy='dynamic',
                                order_by='ModuleExercise.order')

    def __repr__(self):
        return f'<Module {self.name}>'
```

- [ ] **Step 6: Add ModuleExercise model**

```python
class ModuleExercise(db.Model):
    __tablename__ = 'module_exercise'
    id            = db.Column(db.Integer, primary_key=True)
    module_id     = db.Column(db.Integer, db.ForeignKey('module.id'), nullable=False)
    exercise_type = db.Column(db.String(20), nullable=False)
    # 'melody' | 'rhythm' | 'harmonic' | 'holistic'
    exercise_id   = db.Column(db.Integer, nullable=False)
    order         = db.Column(db.Integer, nullable=False, default=0)
    # e.g. {"min_score": 70} or {"attempts": 1}
    completion_criterion_json = db.Column(db.Text, nullable=False, default='{"attempts":1}')

    @property
    def completion_criterion(self):
        import json
        return json.loads(self.completion_criterion_json)

    def __repr__(self):
        return f'<ModuleExercise {self.exercise_type}:{self.exercise_id}>'
```

- [ ] **Step 7: Add ClassModuleExercise (per-class overrides)**

```python
class ClassModuleExercise(db.Model):
    """Per-class override of a course module exercise."""
    __tablename__ = 'class_module_exercise'
    id                 = db.Column(db.Integer, primary_key=True)
    class_id           = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    module_exercise_id = db.Column(db.Integer, db.ForeignKey('module_exercise.id'), nullable=True)
    # action: 'remove' drops the exercise; 'override' replaces params;
    # 'add' introduces a class-only exercise (module_exercise_id=None)
    action             = db.Column(db.String(20), nullable=False, default='add')
    # For 'add': exercise_type + exercise_id + order describe the new exercise
    exercise_type      = db.Column(db.String(20), nullable=True)
    exercise_id        = db.Column(db.Integer, nullable=True)
    order              = db.Column(db.Integer, nullable=True)
    completion_criterion_json = db.Column(db.Text, nullable=True)
    # Which module this add/override belongs to (for 'add' actions)
    module_id          = db.Column(db.Integer, db.ForeignKey('module.id'), nullable=True)

    klass          = db.relationship('Class', backref='module_overrides')
    module_exercise = db.relationship('ModuleExercise', backref='class_overrides')

    @property
    def completion_criterion(self):
        import json
        return json.loads(self.completion_criterion_json) if self.completion_criterion_json else None

    def __repr__(self):
        return f'<ClassModuleExercise class={self.class_id} action={self.action}>'
```

- [ ] **Step 8: Add ModuleCompletion tracking**

```python
class ModuleCompletion(db.Model):
    """Tracks when a student completes a specific exercise in a class context."""
    __tablename__ = 'module_completion'
    id                 = db.Column(db.Integer, primary_key=True)
    user_id            = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    class_id           = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    # References a ModuleExercise or a ClassModuleExercise ('add' type)
    module_exercise_id = db.Column(db.Integer, db.ForeignKey('module_exercise.id'), nullable=True)
    class_exercise_id  = db.Column(db.Integer, db.ForeignKey('class_module_exercise.id'), nullable=True)
    best_score         = db.Column(db.Float, nullable=True)
    completed_at       = db.Column(db.DateTime, server_default=db.func.now())

    user  = db.relationship('User', backref='module_completions')
    klass = db.relationship('Class', backref='module_completions')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'class_id', 'module_exercise_id',
                            name='uq_completion_module_exercise'),
    )

    def __repr__(self):
        return f'<ModuleCompletion user={self.user_id} class={self.class_id}>'
```

- [ ] **Step 9: Update models.py import line**

Add new models to the `__all__` (or just ensure they exist in the file — no explicit `__all__` needed). Add to the import in `app.py` later.

- [ ] **Step 10: Verify models.py syntax**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
.venv/bin/python -c "from models import db, School, Course, Module, ModuleExercise, ClassModuleExercise, ModuleCompletion; print('OK')"
```

Expected: `OK`

- [ ] **Step 11: Commit**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
git add models.py
git commit -m "feat: add curriculum/module models (School, Course, Module, ModuleExercise, ClassModuleExercise, ModuleCompletion)"
```

---

## Task 2: Migration Script

**Files:**
- Create: `migrate_curriculum.py`

- [ ] **Step 1: Write the migration script**

```python
"""
migrate_curriculum.py — adds all new curriculum tables and columns.
Run once: .venv/bin/python migrate_curriculum.py
"""
from app import app
from models import db

with app.app_context():
    db.create_all()  # creates all new tables

    # Add visibility + school_id to existing exercise tables
    with db.engine.connect() as conn:
        for table in ('melody', 'rhythm', 'chord_progression', 'holistic_exercise'):
            try:
                conn.execute(db.text(
                    f"ALTER TABLE {table} ADD COLUMN visibility VARCHAR(20) NOT NULL DEFAULT 'public'"
                ))
                print(f"  Added visibility to {table}")
            except Exception as e:
                print(f"  Skipped visibility on {table}: {e}")
            try:
                conn.execute(db.text(
                    f"ALTER TABLE {table} ADD COLUMN school_id INTEGER REFERENCES school(id)"
                ))
                print(f"  Added school_id to {table}")
            except Exception as e:
                print(f"  Skipped school_id on {table}: {e}")

        # Add course_id to class table
        try:
            conn.execute(db.text(
                "ALTER TABLE class ADD COLUMN course_id INTEGER REFERENCES course(id)"
            ))
            print("  Added course_id to class")
        except Exception as e:
            print(f"  Skipped course_id on class: {e}")

        conn.commit()

    print("Migration complete.")
```

- [ ] **Step 2: Run migration**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
.venv/bin/python migrate_curriculum.py
```

Expected output: lines saying "Added ..." or "Skipped ...", then "Migration complete."

- [ ] **Step 3: Verify tables exist**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
.venv/bin/python -c "
from app import app
from models import db, School, Course, Module
with app.app_context():
    print(School.query.count(), 'schools')
    print(Course.query.count(), 'courses')
    print(Module.query.count(), 'modules')
"
```

Expected: `0 schools`, `0 courses`, `0 modules`

- [ ] **Step 4: Commit**

```bash
git add migrate_curriculum.py instance/musicianship.db
git commit -m "feat: run curriculum migration, add new tables and columns"
```

---

## Task 3: curriculum.py Helper

**Files:**
- Create: `curriculum.py`

This module provides functions that resolve what exercises are in a module for a given class (applying overrides) and check/record completion.

- [ ] **Step 1: Write curriculum.py**

```python
"""
curriculum.py — helper functions for the module/curriculum system.
"""
from models import db, Module, ModuleExercise, ClassModuleExercise, ModuleCompletion


def effective_exercises(class_obj, module):
    """
    Return the effective list of exercises for `module` in `class_obj`,
    applying ClassModuleExercise overrides.

    Returns a list of dicts:
      {
        'source': 'course' | 'class',
        'module_exercise_id': int | None,  # None for class-only 'add'
        'class_exercise_id': int | None,
        'exercise_type': str,
        'exercise_id': int,
        'order': int,
        'completion_criterion': dict,
      }
    """
    removed_ids = set()
    overrides   = {}  # module_exercise_id -> ClassModuleExercise
    additions   = []

    for cme in ClassModuleExercise.query.filter_by(class_id=class_obj.id).all():
        if cme.action == 'remove' and cme.module_exercise_id:
            removed_ids.add(cme.module_exercise_id)
        elif cme.action == 'override' and cme.module_exercise_id:
            overrides[cme.module_exercise_id] = cme
        elif cme.action == 'add' and cme.module_id == module.id:
            additions.append(cme)

    result = []
    for me in module.exercises.order_by(ModuleExercise.order).all():
        if me.id in removed_ids:
            continue
        if me.id in overrides:
            cme = overrides[me.id]
            result.append({
                'source': 'class',
                'module_exercise_id': me.id,
                'class_exercise_id': cme.id,
                'exercise_type': cme.exercise_type or me.exercise_type,
                'exercise_id': cme.exercise_id or me.exercise_id,
                'order': cme.order if cme.order is not None else me.order,
                'completion_criterion': cme.completion_criterion or me.completion_criterion,
            })
        else:
            result.append({
                'source': 'course',
                'module_exercise_id': me.id,
                'class_exercise_id': None,
                'exercise_type': me.exercise_type,
                'exercise_id': me.exercise_id,
                'order': me.order,
                'completion_criterion': me.completion_criterion,
            })

    for cme in additions:
        result.append({
            'source': 'class',
            'module_exercise_id': None,
            'class_exercise_id': cme.id,
            'exercise_type': cme.exercise_type,
            'exercise_id': cme.exercise_id,
            'order': cme.order or 9999,
            'completion_criterion': cme.completion_criterion or {'attempts': 1},
        })

    result.sort(key=lambda x: x['order'])
    return result


def get_completion(user_id, class_id, module_exercise_id=None, class_exercise_id=None):
    """Return ModuleCompletion or None."""
    q = ModuleCompletion.query.filter_by(user_id=user_id, class_id=class_id)
    if module_exercise_id is not None:
        q = q.filter_by(module_exercise_id=module_exercise_id)
    if class_exercise_id is not None:
        q = q.filter_by(class_exercise_id=class_exercise_id)
    return q.first()


def mark_complete(user_id, class_id, module_exercise_id=None, class_exercise_id=None, score=None):
    """
    Mark a module exercise complete for the student. Idempotent — updates best_score if higher.
    """
    existing = get_completion(user_id, class_id, module_exercise_id, class_exercise_id)
    if existing:
        if score is not None and (existing.best_score is None or score > existing.best_score):
            existing.best_score = score
            db.session.commit()
        return existing

    mc = ModuleCompletion(
        user_id=user_id,
        class_id=class_id,
        module_exercise_id=module_exercise_id,
        class_exercise_id=class_exercise_id,
        best_score=score,
    )
    db.session.add(mc)
    db.session.commit()
    return mc


def completion_map(user_id, class_id):
    """
    Return a set of (module_exercise_id, class_exercise_id) tuples that are completed
    for this user in this class.
    """
    completions = ModuleCompletion.query.filter_by(user_id=user_id, class_id=class_id).all()
    return {(c.module_exercise_id, c.class_exercise_id) for c in completions}


def next_incomplete(user_id, class_id, class_obj, module):
    """
    Return the first exercise dict (from effective_exercises) in `module` that is not
    yet completed for this user in this class. Returns None if all are done.
    """
    done = completion_map(user_id, class_id)
    for ex in effective_exercises(class_obj, module):
        key = (ex['module_exercise_id'], ex['class_exercise_id'])
        if key not in done:
            return ex
    return None


def modules_with_progress(user_id, class_id, class_obj):
    """
    For each module in the class's course, return:
      {'module': Module, 'total': int, 'completed': int, 'exercises': list}
    Returns [] if class has no course.
    """
    if not class_obj.course_id:
        return []
    result = []
    done = completion_map(user_id, class_id)
    for module in class_obj.course.modules.order_by(Module.order).all():
        exs = effective_exercises(class_obj, module)
        completed_count = sum(
            1 for ex in exs
            if (ex['module_exercise_id'], ex['class_exercise_id']) in done
        )
        result.append({
            'module': module,
            'total': len(exs),
            'completed': completed_count,
            'exercises': exs,
        })
    return result
```

- [ ] **Step 2: Verify syntax**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
.venv/bin/python -c "import curriculum; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add curriculum.py
git commit -m "feat: add curriculum helper (effective_exercises, completion tracking)"
```

---

## Task 4: Admin CRUD Routes (Schools, Courses, Modules, Module Exercises)

**Files:**
- Modify: `app.py`
- Create: `templates/admin/schools.html`
- Create: `templates/admin/courses.html`
- Create: `templates/admin/modules.html`
- Create: `templates/admin/module_exercises.html`

The existing `/admin` route is a role-gated stub. Extend it.

- [ ] **Step 1: Add curriculum models to the app.py import line**

Change:
```python
from models import db, Melody, Tag, UserAttempt, Rhythm, RhythmAttempt, \
                   ChordProgression, HarmonicAttempt, HolisticExercise, HolisticAttempt, User, Class
```
To:
```python
from models import db, Melody, Tag, UserAttempt, Rhythm, RhythmAttempt, \
                   ChordProgression, HarmonicAttempt, HolisticExercise, HolisticAttempt, \
                   User, Class, School, Course, Module, ModuleExercise, \
                   ClassModuleExercise, ModuleCompletion
```

Also add at top of app.py (after existing imports):
```python
import curriculum as cur
```

- [ ] **Step 2: Add admin routes to app.py**

Add these routes after the existing `/admin` route stub:

```python
# ── Admin: Schools ─────────────────────────────────────────────────────────
@app.route('/admin/schools', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_schools():
    if request.method == 'POST':
        name = request.form['name'].strip()
        if name:
            db.session.add(School(name=name))
            db.session.commit()
            flash('School created.', 'success')
        return redirect(url_for('admin_schools'))
    schools = School.query.order_by(School.name).all()
    return render_template('admin/schools.html', schools=schools)


# ── Admin: Courses ──────────────────────────────────────────────────────────
@app.route('/admin/schools/<int:school_id>/courses', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_courses(school_id):
    school = School.query.get_or_404(school_id)
    if request.method == 'POST':
        name = request.form['name'].strip()
        if name:
            db.session.add(Course(name=name, school_id=school_id))
            db.session.commit()
            flash('Course created.', 'success')
        return redirect(url_for('admin_courses', school_id=school_id))
    courses = Course.query.filter_by(school_id=school_id).order_by(Course.name).all()
    return render_template('admin/courses.html', school=school, courses=courses)


# ── Admin: Modules ──────────────────────────────────────────────────────────
@app.route('/admin/courses/<int:course_id>/modules', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_modules(course_id):
    course = Course.query.get_or_404(course_id)
    if request.method == 'POST':
        name  = request.form['name'].strip()
        order = int(request.form.get('order', 0))
        if name:
            db.session.add(Module(name=name, course_id=course_id, order=order))
            db.session.commit()
            flash('Module created.', 'success')
        return redirect(url_for('admin_modules', course_id=course_id))
    modules = Module.query.filter_by(course_id=course_id).order_by(Module.order).all()
    return render_template('admin/modules.html', course=course, modules=modules)


# ── Admin: Module Exercises ─────────────────────────────────────────────────
@app.route('/admin/modules/<int:module_id>/exercises', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_module_exercises(module_id):
    module = Module.query.get_or_404(module_id)
    if request.method == 'POST':
        ex_type = request.form['exercise_type']
        ex_id   = int(request.form['exercise_id'])
        order   = int(request.form.get('order', 0))
        criterion = request.form.get('completion_criterion', '{"attempts":1}')
        db.session.add(ModuleExercise(
            module_id=module_id,
            exercise_type=ex_type,
            exercise_id=ex_id,
            order=order,
            completion_criterion_json=criterion,
        ))
        db.session.commit()
        flash('Exercise added to module.', 'success')
        return redirect(url_for('admin_module_exercises', module_id=module_id))

    exercises = module.exercises.order_by(ModuleExercise.order).all()
    # For selection dropdowns
    melodies     = Melody.query.order_by(Melody.name).all()
    rhythms      = Rhythm.query.order_by(Rhythm.name).all()
    progressions = ChordProgression.query.order_by(ChordProgression.name).all()
    holistics    = HolisticExercise.query.order_by(HolisticExercise.name).all()
    return render_template('admin/module_exercises.html',
                           module=module,
                           exercises=exercises,
                           melodies=melodies,
                           rhythms=rhythms,
                           progressions=progressions,
                           holistics=holistics)


@app.route('/admin/module_exercises/<int:me_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_module_exercise(me_id):
    me = ModuleExercise.query.get_or_404(me_id)
    module_id = me.module_id
    db.session.delete(me)
    db.session.commit()
    flash('Exercise removed.', 'success')
    return redirect(url_for('admin_module_exercises', module_id=module_id))
```

- [ ] **Step 3: Create templates/admin/schools.html**

```html
{% extends 'base.html' %}
{% block title %}Admin — Schools{% endblock %}
{% block content %}
<div class="container py-4">
  <h2>Schools</h2>
  <a href="{{ url_for('admin') }}" class="btn btn-outline-secondary btn-sm mb-3">← Admin Home</a>
  <form method="post" class="d-flex gap-2 mb-4" style="max-width:420px">
    <input name="name" class="form-control" placeholder="New school name" required>
    <button class="btn btn-primary">Add</button>
  </form>
  <table class="table table-sm">
    <thead><tr><th>Name</th><th>Courses</th><th></th></tr></thead>
    <tbody>
    {% for s in schools %}
    <tr>
      <td>{{ s.name }}</td>
      <td>{{ s.courses.count() }}</td>
      <td><a href="{{ url_for('admin_courses', school_id=s.id) }}" class="btn btn-sm btn-outline-secondary">Courses →</a></td>
    </tr>
    {% else %}
    <tr><td colspan="3" class="text-muted">No schools yet.</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

- [ ] **Step 4: Create templates/admin/courses.html**

```html
{% extends 'base.html' %}
{% block title %}Admin — Courses{% endblock %}
{% block content %}
<div class="container py-4">
  <h2>{{ school.name }} — Courses</h2>
  <a href="{{ url_for('admin_schools') }}" class="btn btn-outline-secondary btn-sm mb-3">← Schools</a>
  <form method="post" class="d-flex gap-2 mb-4" style="max-width:420px">
    <input name="name" class="form-control" placeholder="New course name" required>
    <button class="btn btn-primary">Add</button>
  </form>
  <table class="table table-sm">
    <thead><tr><th>Name</th><th>Modules</th><th></th></tr></thead>
    <tbody>
    {% for c in courses %}
    <tr>
      <td>{{ c.name }}</td>
      <td>{{ c.modules.count() }}</td>
      <td><a href="{{ url_for('admin_modules', course_id=c.id) }}" class="btn btn-sm btn-outline-secondary">Modules →</a></td>
    </tr>
    {% else %}
    <tr><td colspan="3" class="text-muted">No courses yet.</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

- [ ] **Step 5: Create templates/admin/modules.html**

```html
{% extends 'base.html' %}
{% block title %}Admin — Modules{% endblock %}
{% block content %}
<div class="container py-4">
  <h2>{{ course.name }} — Modules</h2>
  <a href="{{ url_for('admin_courses', school_id=course.school_id) }}" class="btn btn-outline-secondary btn-sm mb-3">← Courses</a>
  <form method="post" class="d-flex gap-2 mb-4" style="max-width:520px">
    <input name="name" class="form-control" placeholder="Module name" required>
    <input name="order" type="number" class="form-control" style="max-width:80px" placeholder="Order" value="0">
    <button class="btn btn-primary">Add</button>
  </form>
  <table class="table table-sm">
    <thead><tr><th>#</th><th>Name</th><th>Exercises</th><th></th></tr></thead>
    <tbody>
    {% for m in modules %}
    <tr>
      <td>{{ m.order }}</td>
      <td>{{ m.name }}</td>
      <td>{{ m.exercises.count() }}</td>
      <td><a href="{{ url_for('admin_module_exercises', module_id=m.id) }}" class="btn btn-sm btn-outline-secondary">Exercises →</a></td>
    </tr>
    {% else %}
    <tr><td colspan="4" class="text-muted">No modules yet.</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

- [ ] **Step 6: Create templates/admin/module_exercises.html**

```html
{% extends 'base.html' %}
{% block title %}Admin — Module Exercises{% endblock %}
{% block content %}
<div class="container py-4">
  <h2>{{ module.name }} — Exercises</h2>
  <a href="{{ url_for('admin_modules', course_id=module.course_id) }}" class="btn btn-outline-secondary btn-sm mb-3">← Modules</a>

  <form method="post" class="card p-3 mb-4">
    <div class="row g-2">
      <div class="col-md-3">
        <select name="exercise_type" class="form-select" id="ex-type-select" required>
          <option value="">Type…</option>
          <option value="melody">Melodic</option>
          <option value="rhythm">Rhythmic</option>
          <option value="harmonic">Harmonic</option>
          <option value="holistic">Holistic</option>
        </select>
      </div>
      <div class="col-md-4">
        <select name="exercise_id" class="form-select" required>
          {% for ex in melodies %}<option value="{{ ex.id }}" data-type="melody">{{ ex.name }}</option>{% endfor %}
          {% for ex in rhythms %}<option value="{{ ex.id }}" data-type="rhythm">{{ ex.name }}</option>{% endfor %}
          {% for ex in progressions %}<option value="{{ ex.id }}" data-type="harmonic">{{ ex.name }}</option>{% endfor %}
          {% for ex in holistics %}<option value="{{ ex.id }}" data-type="holistic">{{ ex.name }}</option>{% endfor %}
        </select>
      </div>
      <div class="col-md-2">
        <input name="order" type="number" class="form-control" placeholder="Order" value="0">
      </div>
      <div class="col-md-2">
        <input name="completion_criterion" class="form-control" placeholder='{"attempts":1}' value='{"attempts":1}'>
      </div>
      <div class="col-md-1">
        <button class="btn btn-primary w-100">Add</button>
      </div>
    </div>
  </form>

  <table class="table table-sm">
    <thead><tr><th>#</th><th>Type</th><th>Exercise ID</th><th>Criterion</th><th></th></tr></thead>
    <tbody>
    {% for ex in exercises %}
    <tr>
      <td>{{ ex.order }}</td>
      <td>{{ ex.exercise_type }}</td>
      <td>{{ ex.exercise_id }}</td>
      <td><code>{{ ex.completion_criterion_json }}</code></td>
      <td>
        <form method="post" action="{{ url_for('admin_delete_module_exercise', me_id=ex.id) }}" onsubmit="return confirm('Remove?')">
          <button class="btn btn-sm btn-outline-danger">Remove</button>
        </form>
      </td>
    </tr>
    {% else %}
    <tr><td colspan="5" class="text-muted">No exercises yet.</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

- [ ] **Step 7: Update existing /admin route to link to schools**

Find the existing `admin` route stub in app.py. Replace its `render_template` call to pass a link context, or just render a simple admin home. Replace whatever it currently returns with:

```python
@app.route('/admin')
@login_required
@role_required('admin')
def admin():
    user_count   = User.query.count()
    school_count = School.query.count()
    class_count  = Class.query.count()
    return render_template('admin/index.html',
                           user_count=user_count,
                           school_count=school_count,
                           class_count=class_count)
```

And create `templates/admin/index.html`:

```html
{% extends 'base.html' %}
{% block title %}Admin{% endblock %}
{% block content %}
<div class="container py-4">
  <h2>Admin</h2>
  <div class="row g-3 mt-2">
    <div class="col-md-3">
      <div class="card text-center p-3">
        <div class="fs-2 fw-bold">{{ user_count }}</div>
        <div class="text-muted">Users</div>
        <a href="{{ url_for('admin_schools') }}" class="btn btn-sm btn-outline-primary mt-2">Manage Schools →</a>
      </div>
    </div>
    <div class="col-md-3">
      <div class="card text-center p-3">
        <div class="fs-2 fw-bold">{{ school_count }}</div>
        <div class="text-muted">Schools</div>
        <a href="{{ url_for('admin_schools') }}" class="btn btn-sm btn-outline-primary mt-2">Schools →</a>
      </div>
    </div>
    <div class="col-md-3">
      <div class="card text-center p-3">
        <div class="fs-2 fw-bold">{{ class_count }}</div>
        <div class="text-muted">Classes</div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 8: Smoke-test admin routes**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
.venv/bin/python -c "
from app import app
with app.test_client() as c:
    # Login as admin first
    c.post('/login', data={'email':'admin@musicianship.app','password':'10000BeesMusicianship!'}, follow_redirects=True)
    r = c.get('/admin/schools')
    print(r.status_code)  # expect 200
"
```

Expected: `200`

- [ ] **Step 9: Commit**

```bash
git add app.py templates/admin/
git commit -m "feat: admin CRUD for schools, courses, modules, module exercises"
```

---

## Task 5: Teacher UI — Course Assignment & Class Overrides

**Files:**
- Modify: `app.py` (teacher routes)
- Modify: `templates/teacher/class_detail.html`

- [ ] **Step 1: Add course-assignment route to app.py**

```python
@app.route('/teacher/classes/<int:class_id>/set_course', methods=['POST'])
@login_required
@role_required('teacher', 'admin')
def teacher_set_course(class_id):
    klass = Class.query.get_or_404(class_id)
    if klass.teacher_id != current_user.id and current_user.role != 'admin':
        abort(403)
    course_id = request.form.get('course_id')
    klass.course_id = int(course_id) if course_id else None
    db.session.commit()
    flash('Course assignment updated.', 'success')
    return redirect(url_for('teacher_class_detail', class_id=class_id))
```

- [ ] **Step 2: Add class override routes to app.py**

```python
@app.route('/teacher/classes/<int:class_id>/overrides/add', methods=['POST'])
@login_required
@role_required('teacher', 'admin')
def teacher_add_override(class_id):
    klass = Class.query.get_or_404(class_id)
    if klass.teacher_id != current_user.id and current_user.role != 'admin':
        abort(403)
    action    = request.form['action']          # 'add' | 'remove' | 'override'
    module_id = request.form.get('module_id', type=int)
    me_id     = request.form.get('module_exercise_id', type=int)
    ex_type   = request.form.get('exercise_type')
    ex_id     = request.form.get('exercise_id', type=int)
    order     = request.form.get('order', type=int)
    criterion = request.form.get('completion_criterion')

    cme = ClassModuleExercise(
        class_id=class_id,
        action=action,
        module_exercise_id=me_id,
        module_id=module_id,
        exercise_type=ex_type,
        exercise_id=ex_id,
        order=order,
        completion_criterion_json=criterion,
    )
    db.session.add(cme)
    db.session.commit()
    flash('Override added.', 'success')
    return redirect(url_for('teacher_class_detail', class_id=class_id))


@app.route('/teacher/classes/<int:class_id>/overrides/<int:cme_id>/delete', methods=['POST'])
@login_required
@role_required('teacher', 'admin')
def teacher_delete_override(class_id, cme_id):
    cme = ClassModuleExercise.query.get_or_404(cme_id)
    if cme.class_id != class_id:
        abort(403)
    db.session.delete(cme)
    db.session.commit()
    flash('Override removed.', 'success')
    return redirect(url_for('teacher_class_detail', class_id=class_id))
```

- [ ] **Step 3: Modify teacher_class_detail route to pass curriculum data**

Find the existing `teacher_class_detail` route in app.py. Add to its query context before `render_template`:

```python
all_courses = Course.query.order_by(Course.name).all()
modules_progress = []
if klass.course_id:
    for mod in klass.course.modules.order_by(Module.order).all():
        student_completions = {}
        for member in klass.members:
            exs = cur.effective_exercises(klass, mod)
            done = cur.completion_map(member.id, klass.id)
            completed = sum(1 for ex in exs if (ex['module_exercise_id'], ex['class_exercise_id']) in done)
            student_completions[member.id] = {'completed': completed, 'total': len(exs)}
        modules_progress.append({'module': mod, 'student_completions': student_completions})
overrides = ClassModuleExercise.query.filter_by(class_id=klass.id).all()
# ... existing melodies/rhythms queries ...
```

Pass to template: `all_courses=all_courses, modules_progress=modules_progress, overrides=overrides`

- [ ] **Step 4: Update templates/teacher/class_detail.html**

Read the existing file first. Then append two new sections after the existing roster table:

**Section A — Course Assignment:**
```html
<hr>
<h5>Course Assignment</h5>
<form method="post" action="{{ url_for('teacher_set_course', class_id=klass.id) }}" class="d-flex gap-2 align-items-center mb-3">
  <select name="course_id" class="form-select" style="max-width:280px">
    <option value="">— No course —</option>
    {% for c in all_courses %}
    <option value="{{ c.id }}" {% if klass.course_id == c.id %}selected{% endif %}>{{ c.school.name }} / {{ c.name }}</option>
    {% endfor %}
  </select>
  <button class="btn btn-primary">Save</button>
</form>

{% if modules_progress %}
<h6 class="mt-3">Module Completion by Student</h6>
<table class="table table-sm table-bordered">
  <thead>
    <tr>
      <th>Student</th>
      {% for mp in modules_progress %}<th>{{ mp.module.name }}</th>{% endfor %}
    </tr>
  </thead>
  <tbody>
  {% for member in klass.members %}
  <tr>
    <td>{{ member.display_name or member.email }}</td>
    {% for mp in modules_progress %}
    {% set sc = mp.student_completions.get(member.id, {'completed':0,'total':0}) %}
    <td>
      {% if sc.total == 0 %}—
      {% elif sc.completed == sc.total %}<span class="badge bg-success">Done</span>
      {% else %}<span class="text-muted">{{ sc.completed }}/{{ sc.total }}</span>
      {% endif %}
    </td>
    {% endfor %}
  </tr>
  {% endfor %}
  </tbody>
</table>
{% endif %}
```

**Section B — Class Overrides:**
```html
<hr>
<h5>Class-Specific Overrides</h5>
{% if overrides %}
<table class="table table-sm mb-3">
  <thead><tr><th>Action</th><th>Type</th><th>Exercise ID</th><th></th></tr></thead>
  <tbody>
  {% for o in overrides %}
  <tr>
    <td><span class="badge bg-secondary">{{ o.action }}</span></td>
    <td>{{ o.exercise_type or '—' }}</td>
    <td>{{ o.exercise_id or '—' }}</td>
    <td>
      <form method="post" action="{{ url_for('teacher_delete_override', class_id=klass.id, cme_id=o.id) }}">
        <button class="btn btn-sm btn-outline-danger">Remove</button>
      </form>
    </td>
  </tr>
  {% endfor %}
  </tbody>
</table>
{% endif %}
```

- [ ] **Step 5: Commit**

```bash
git add app.py templates/teacher/class_detail.html
git commit -m "feat: teacher course assignment, per-class overrides, module completion roster"
```

---

## Task 6: Student Mode Selector & Module List UI

**Files:**
- Create: `templates/student/mode_select.html`
- Create: `templates/student/module_list.html`
- Create: `templates/student/module_detail.html`
- Modify: `app.py` (new student routes)

- [ ] **Step 1: Add student routes to app.py**

```python
# ── Student: Class Home (mode selector) ─────────────────────────────────────
@app.route('/class/<int:class_id>')
@login_required
def class_home(class_id):
    klass = Class.query.get_or_404(class_id)
    if current_user not in klass.members and current_user.role not in ('teacher', 'admin'):
        abort(403)
    has_course = klass.course_id is not None
    return render_template('student/mode_select.html', klass=klass, has_course=has_course)


# ── Student: Module List ─────────────────────────────────────────────────────
@app.route('/class/<int:class_id>/modules')
@login_required
def class_modules(class_id):
    klass = Class.query.get_or_404(class_id)
    if current_user not in klass.members and current_user.role not in ('teacher', 'admin'):
        abort(403)
    if not klass.course_id:
        flash('This class has no course assigned yet.', 'info')
        return redirect(url_for('class_home', class_id=class_id))
    mods = cur.modules_with_progress(current_user.id, class_id, klass)
    return render_template('student/module_list.html', klass=klass, mods=mods)


# ── Student: Module Detail ───────────────────────────────────────────────────
@app.route('/class/<int:class_id>/modules/<int:module_id>')
@login_required
def class_module_detail(class_id, module_id):
    klass  = Class.query.get_or_404(class_id)
    if current_user not in klass.members and current_user.role not in ('teacher', 'admin'):
        abort(403)
    module = Module.query.get_or_404(module_id)
    exercises = cur.effective_exercises(klass, module)
    done = cur.completion_map(current_user.id, class_id)
    ex_with_status = []
    for ex in exercises:
        key = (ex['module_exercise_id'], ex['class_exercise_id'])
        completion = cur.get_completion(
            current_user.id, class_id,
            ex['module_exercise_id'], ex['class_exercise_id']
        )
        ex_with_status.append({
            **ex,
            'completed': key in done,
            'best_score': completion.best_score if completion else None,
        })
    return render_template('student/module_detail.html',
                           klass=klass,
                           module=module,
                           exercises=ex_with_status)
```

- [ ] **Step 2: Create templates/student/mode_select.html**

```html
{% extends 'base.html' %}
{% block title %}{{ klass.name }}{% endblock %}
{% block content %}
<div class="container py-5" style="max-width:600px">
  <h2 class="mb-1">{{ klass.name }}</h2>
  <p class="text-muted mb-4">Choose how you'd like to practice today.</p>

  <div class="row g-3">
    {% if has_course %}
    <div class="col-12">
      <a href="{{ url_for('class_modules', class_id=klass.id) }}" class="card text-decoration-none h-100 border-primary">
        <div class="card-body">
          <h5 class="card-title"><i class="bi bi-journal-bookmark me-2 text-primary"></i>Study by Module</h5>
          <p class="card-text text-muted">Work through your class assignments in order. Track your progress module by module.</p>
        </div>
      </a>
    </div>
    {% endif %}
    <div class="col-12">
      <a href="{{ url_for('melody_index') }}" class="card text-decoration-none h-100">
        <div class="card-body">
          <h5 class="card-title"><i class="bi bi-shuffle me-2 text-secondary"></i>Sandbox</h5>
          <p class="card-text text-muted">Practice freely — browse all available exercises across all modes.</p>
        </div>
      </a>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Create templates/student/module_list.html**

```html
{% extends 'base.html' %}
{% block title %}{{ klass.name }} — Modules{% endblock %}
{% block content %}
<div class="container py-4">
  <nav aria-label="breadcrumb" class="mb-3">
    <ol class="breadcrumb">
      <li class="breadcrumb-item"><a href="{{ url_for('class_home', class_id=klass.id) }}">{{ klass.name }}</a></li>
      <li class="breadcrumb-item active">Modules</li>
    </ol>
  </nav>
  <h2>{{ klass.course.name }}</h2>
  <div class="list-group mt-3">
  {% for m in mods %}
    {% set pct = (m.completed / m.total * 100) | int if m.total else 0 %}
    <a href="{{ url_for('class_module_detail', class_id=klass.id, module_id=m.module.id) }}"
       class="list-group-item list-group-item-action">
      <div class="d-flex justify-content-between align-items-center">
        <span class="fw-semibold">{{ m.module.name }}</span>
        {% if m.total == 0 %}
          <span class="text-muted small">No exercises</span>
        {% elif m.completed == m.total %}
          <span class="badge bg-success">Complete</span>
        {% else %}
          <span class="text-muted small">{{ m.completed }}/{{ m.total }}</span>
        {% endif %}
      </div>
      {% if m.total > 0 %}
      <div class="progress mt-1" style="height:4px">
        <div class="progress-bar" style="width:{{ pct }}%"></div>
      </div>
      {% endif %}
    </a>
  {% else %}
    <p class="text-muted">No modules in this course yet.</p>
  {% endfor %}
  </div>
</div>
{% endblock %}
```

- [ ] **Step 4: Create templates/student/module_detail.html**

```html
{% extends 'base.html' %}
{% block title %}{{ module.name }}{% endblock %}
{% block content %}
<div class="container py-4">
  <nav aria-label="breadcrumb" class="mb-3">
    <ol class="breadcrumb">
      <li class="breadcrumb-item"><a href="{{ url_for('class_home', class_id=klass.id) }}">{{ klass.name }}</a></li>
      <li class="breadcrumb-item"><a href="{{ url_for('class_modules', class_id=klass.id) }}">Modules</a></li>
      <li class="breadcrumb-item active">{{ module.name }}</li>
    </ol>
  </nav>
  <h2>{{ module.name }}</h2>

  <div class="list-group mt-3">
  {% for ex in exercises %}
    {% set drill_url = '' %}
    {% if ex.exercise_type == 'melody' %}
      {% set drill_url = url_for('melody_play', melody_id=ex.exercise_id) ~ '?class_id=' ~ klass.id ~ '&me_id=' ~ (ex.module_exercise_id or '') ~ '&cme_id=' ~ (ex.class_exercise_id or '') %}
    {% elif ex.exercise_type == 'rhythm' %}
      {% set drill_url = url_for('rhythm_play', rhythm_id=ex.exercise_id) ~ '?class_id=' ~ klass.id ~ '&me_id=' ~ (ex.module_exercise_id or '') ~ '&cme_id=' ~ (ex.class_exercise_id or '') %}
    {% elif ex.exercise_type == 'harmonic' %}
      {% set drill_url = url_for('harmonic_play', progression_id=ex.exercise_id) ~ '?class_id=' ~ klass.id ~ '&me_id=' ~ (ex.module_exercise_id or '') ~ '&cme_id=' ~ (ex.class_exercise_id or '') %}
    {% elif ex.exercise_type == 'holistic' %}
      {% set drill_url = url_for('holistic_play', exercise_id=ex.exercise_id) ~ '?class_id=' ~ klass.id ~ '&me_id=' ~ (ex.module_exercise_id or '') ~ '&cme_id=' ~ (ex.class_exercise_id or '') %}
    {% endif %}

    <a href="{{ drill_url }}" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
      <span>
        <span class="badge bg-secondary me-2">{{ ex.exercise_type }}</span>
        Exercise #{{ ex.exercise_id }}
      </span>
      {% if ex.completed %}
        <span class="badge bg-success">
          ✓{% if ex.best_score is not none %} {{ ex.best_score | int }}%{% endif %}
        </span>
      {% else %}
        <span class="badge bg-outline text-muted border">Not done</span>
      {% endif %}
    </a>
  {% else %}
    <p class="text-muted">No exercises in this module.</p>
  {% endfor %}
  </div>
</div>
{% endblock %}
```

- [ ] **Step 5: Commit**

```bash
git add app.py templates/student/
git commit -m "feat: student class home, module list, and module detail pages"
```

---

## Task 7: Drill Integration — Module Context & Completion Tracking

When a student arrives at a drill from a module (via `?class_id=X&me_id=Y`), the results page should:
1. Mark the exercise complete (criterion: `attempts=1` → on submit; `min_score` → on passing score).
2. After results, show "Next exercise" button pointing to next incomplete in the module (or "Back to module" if done).

This affects the four results routes: `melody_results`, `rhythm_results`, `harmonic_results`, `holistic_results`.

**Files:**
- Modify: `app.py` (results routes)
- Modify: `templates/melody_results.html`
- Modify: `templates/rhythm_results.html`
- Modify: `templates/harmonic_results.html`
- Modify: `templates/holistic_results.html`

- [ ] **Step 1: Add a helper to app.py for resolving module context after a submission**

Add this helper function near the top of app.py (after imports):

```python
def _handle_module_completion(class_id, me_id, cme_id, score):
    """
    Called after a drill submission when the student came from a module.
    Returns dict with 'next_url' and 'module_done' for use in results templates.
    Returns None if no module context.
    """
    if not class_id:
        return None
    try:
        class_id = int(class_id)
        klass = Class.query.get(class_id)
        if not klass:
            return None
    except (ValueError, TypeError):
        return None

    me_id_int  = int(me_id)  if me_id  else None
    cme_id_int = int(cme_id) if cme_id else None

    # Determine the exercise's completion criterion
    criterion = {'attempts': 1}
    me = ModuleExercise.query.get(me_id_int) if me_id_int else None
    if me:
        criterion = me.completion_criterion

    # Check if criterion met
    completed = False
    if 'attempts' in criterion:
        completed = True  # any attempt qualifies
    elif 'min_score' in criterion and score is not None:
        completed = score >= criterion['min_score']

    if completed:
        cur.mark_complete(current_user.id, class_id, me_id_int, cme_id_int, score)

    # Find the module for "next" navigation
    module = me.module if me else (
        ClassModuleExercise.query.get(cme_id_int).module if cme_id_int else None
    )
    if not module:
        return {'next_url': url_for('class_modules', class_id=class_id), 'module_done': False, 'class_id': class_id}

    next_ex = cur.next_incomplete(current_user.id, class_id, klass, module)
    if next_ex:
        type_to_route = {
            'melody': 'melody_play',
            'rhythm': 'rhythm_play',
            'harmonic': 'harmonic_play',
            'holistic': 'holistic_play',
        }
        # Note: each play route uses a different parameter name — handle below
        route = type_to_route.get(next_ex['exercise_type'], 'class_modules')
        ex_param = {
            'melody': 'melody_id',
            'rhythm': 'rhythm_id',
            'harmonic': 'progression_id',
            'holistic': 'exercise_id',
        }.get(next_ex['exercise_type'], 'id')
        next_url = url_for(route, **{ex_param: next_ex['exercise_id']},
                           class_id=class_id,
                           me_id=next_ex['module_exercise_id'] or '',
                           cme_id=next_ex['class_exercise_id'] or '')
        return {'next_url': next_url, 'module_done': False, 'class_id': class_id,
                'module_id': module.id}
    else:
        return {'next_url': url_for('class_module_detail', class_id=class_id, module_id=module.id),
                'module_done': True, 'class_id': class_id, 'module_id': module.id}
```

- [ ] **Step 2: Call _handle_module_completion in each results route**

For each of the four results routes (`melody_results`, `rhythm_results`, `harmonic_results`, `holistic_results`), add these lines just before the `return render_template(...)`:

```python
# Module context
class_id = request.args.get('class_id') or session.pop('module_class_id', None)
me_id    = request.args.get('me_id')    or session.pop('module_me_id', None)
cme_id   = request.args.get('cme_id')  or session.pop('module_cme_id', None)
module_ctx = _handle_module_completion(class_id, me_id, cme_id, attempt.overall_score) \
             if current_user.is_authenticated else None
```

Then pass `module_ctx=module_ctx` to `render_template`.

For rhythm results use `attempt.duration_accuracy` as the score (since there's no `overall_score`).

- [ ] **Step 3: Update results templates to show module navigation**

In each of the four results templates, find the "Next" button / actions row and add conditionally:

```html
{% if module_ctx %}
  <div class="alert alert-info mt-3 d-flex justify-content-between align-items-center">
    {% if module_ctx.module_done %}
      <span>🎉 Module complete! All exercises done.</span>
      <a href="{{ module_ctx.next_url }}" class="btn btn-success">Back to Module</a>
    {% else %}
      <span>Exercise complete. Keep going!</span>
      <a href="{{ module_ctx.next_url }}" class="btn btn-primary">Next Exercise →</a>
    {% endif %}
  </div>
{% endif %}
```

- [ ] **Step 4: Ensure the melody_play, rhythm_play, harmonic_play, holistic_play routes pass class_id through to results**

For each `play` route, if `class_id` is in `request.args`, pass it through to the results URL via the form's hidden fields or redirect params. The simplest approach: in each play template, add hidden inputs:

```html
<input type="hidden" name="class_id" value="{{ request.args.get('class_id', '') }}">
<input type="hidden" name="me_id"    value="{{ request.args.get('me_id', '') }}">
<input type="hidden" name="cme_id"   value="{{ request.args.get('cme_id', '') }}">
```

And in each submit route handler, read and pass these through to the redirect URL:

```python
class_id = request.form.get('class_id')
me_id    = request.form.get('me_id')
cme_id   = request.form.get('cme_id')
# Then in the redirect:
return redirect(url_for('melody_results', attempt_id=attempt.id,
                        class_id=class_id or '', me_id=me_id or '', cme_id=cme_id or ''))
```

- [ ] **Step 5: Commit**

```bash
git add app.py templates/
git commit -m "feat: drill integration — module context passthrough, completion tracking, next-exercise navigation"
```

---

## Task 8: Exercise Visibility Filtering

Sandbox mode should respect visibility:
- `public` exercises: shown to everyone
- `school` exercises: shown only to students enrolled in a class belonging to that school
- `module` exercises: not shown in sandbox at all

**Files:**
- Modify: `app.py` (the four index/list routes: `melody_index`, `rhythm_index`, `harmonic_index`, `holistic_index`)

- [ ] **Step 1: Add a helper function to app.py**

```python
def _visible_exercise_ids(model):
    """
    Return a SQLAlchemy filter for exercises visible to current_user in sandbox mode.
    Public: always. School: if user is in a class in that school. Module: never in sandbox.
    """
    from sqlalchemy import or_, and_
    if not current_user.is_authenticated:
        return model.visibility == 'public'

    # Get school IDs the user has access to via their classes
    user_school_ids = set()
    for klass in current_user.classes:
        if klass.course_id:
            user_school_ids.add(klass.course.school_id)

    if user_school_ids:
        return or_(
            model.visibility == 'public',
            and_(model.visibility == 'school', model.school_id.in_(user_school_ids))
        )
    return model.visibility == 'public'
```

- [ ] **Step 2: Apply visibility filter to each index route**

In each of the four index routes, add `.filter(_visible_exercise_ids(Melody))` (substituting the appropriate model) to the exercise query. For example, in `melody_index`:

```python
# Before: melodies = Melody.query.order_by(Melody.difficulty, Melody.name).all()
# After:
melodies = Melody.query.filter(_visible_exercise_ids(Melody)) \
                       .order_by(Melody.difficulty, Melody.name).all()
```

Apply the same pattern to `Rhythm`, `ChordProgression`, `HolisticExercise`.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: exercise visibility filtering in sandbox (public/school/module tiers)"
```

---

## Task 9: /me Progress — Per-Module Completion

**Files:**
- Modify: `app.py` (`/me` route)
- Modify: `templates/me.html`

- [ ] **Step 1: Add module progress data to /me route**

In the `/me` route, after the existing attempt queries, add:

```python
# Module progress per class
module_progress_by_class = []
for klass in current_user.classes:
    mods = cur.modules_with_progress(current_user.id, klass.id, klass)
    if mods:
        module_progress_by_class.append({'class': klass, 'modules': mods})
```

Pass `module_progress_by_class=module_progress_by_class` to `render_template`.

- [ ] **Step 2: Add module progress section to templates/me.html**

Add after the join-class form:

```html
{% if module_progress_by_class %}
<hr>
<h5>Module Progress</h5>
{% for item in module_progress_by_class %}
<h6 class="mt-3">{{ item.class.name }}</h6>
<div class="list-group mb-3">
{% for m in item.modules %}
  {% set pct = (m.completed / m.total * 100) | int if m.total else 0 %}
  <div class="list-group-item">
    <div class="d-flex justify-content-between">
      <span>{{ m.module.name }}</span>
      {% if m.total == 0 %}—
      {% elif m.completed == m.total %}<span class="badge bg-success">Complete</span>
      {% else %}<span class="text-muted small">{{ m.completed }}/{{ m.total }}</span>
      {% endif %}
    </div>
    {% if m.total > 0 %}
    <div class="progress mt-1" style="height:4px">
      <div class="progress-bar" style="width:{{ pct }}%"></div>
    </div>
    {% endif %}
  </div>
{% endfor %}
</div>
{% endfor %}
{% endif %}
```

- [ ] **Step 3: Commit**

```bash
git add app.py templates/me.html
git commit -m "feat: per-module completion progress in /me"
```

---

## Task 10: Link Classes in Nav & /me

Students need a way to reach their class home. Add class links to the nav dropdown and /me page.

**Files:**
- Modify: `templates/base.html`
- Modify: `templates/me.html`

- [ ] **Step 1: Add class links to nav dropdown in base.html**

In the authenticated nav dropdown (already has "My Progress", "Log out"), add after "My Progress":

```html
{% if current_user.classes %}
<li><hr class="dropdown-divider"></li>
{% for klass in current_user.classes %}
<li><a class="dropdown-item" href="{{ url_for('class_home', class_id=klass.id) }}">
  <i class="bi bi-people me-1"></i>{{ klass.name }}
</a></li>
{% endfor %}
<li><hr class="dropdown-divider"></li>
{% endif %}
```

- [ ] **Step 2: Add class links to /me enrolled section**

In `me.html`, find the existing enrolled classes paragraph and replace with:

```html
{% if current_user.classes %}
<div class="mt-3">
  <strong>Your classes:</strong>
  <ul class="list-unstyled mt-1">
  {% for klass in current_user.classes %}
    <li><a href="{{ url_for('class_home', class_id=klass.id) }}">{{ klass.name }}</a>
    {% if klass.course_id %}<span class="text-muted small ms-1">({{ klass.course.name }})</span>{% endif %}
    </li>
  {% endfor %}
  </ul>
</div>
{% endif %}
```

- [ ] **Step 3: Commit**

```bash
git add templates/base.html templates/me.html
git commit -m "feat: class home links in nav and /me page"
```

---

## Self-Review Against Spec

### Spec Coverage Check

| Requirement | Task |
|---|---|
| School → Course → Class → Module hierarchy | Tasks 1, 2 |
| Class inherits coursework from course, can add/remove/override | Tasks 1 (ClassModuleExercise), 5 |
| Exercise visibility: public / school / module-only | Tasks 1, 8 |
| Study by Module student UX | Task 6 |
| Module list with progress | Task 6 |
| Module exercise navigation (not sequential, free order) | Task 6 (module_detail) |
| Completion tracking (stays completed) | Tasks 1 (ModuleCompletion), 7 |
| After exercise: next incomplete in module, nudge if done | Task 7 |
| Completion criterion: attempts or min_score | Tasks 1, 7 |
| Show score on completion badge | Tasks 6, 7 |
| Admin UI: schools, courses, modules, module exercises | Task 4 |
| Teacher UI: course assignment, overrides | Task 5 |
| Teacher roster: per-module completion | Task 5 |
| /me: per-module completion | Task 9 |
| Class home accessible from nav | Task 10 |

### Known Gaps & Notes

1. **module_detail.html shows "Exercise #ID" not the exercise name** — Task 7 implementer should look up the actual exercise object by type+id and display its `.name`. Add a Jinja macro or do the lookup in the route.
2. **Play route templates need hidden inputs** (Task 7, Step 4) — must check actual template names and form action for each of the four drill types.
3. **rhythm_results** uses `duration_accuracy` not `overall_score` — ensure `_handle_module_completion` receives the right score field.
4. **melody_play route name** — verify exact Flask route function names before using in `url_for`. Read app.py if uncertain.
