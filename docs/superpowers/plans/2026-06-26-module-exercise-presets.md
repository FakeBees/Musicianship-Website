# Module Exercise Presets & Class-Course Linking Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace manual exercise picks in module exercises with filter presets (for melody/rhythm/harmonic) and specific picks (holistic only), add count-based completion tracking, fix class-course linking on creation, and give students a block-style module detail view.

**Architecture:** `ModuleExercise` gains `name` and `params_json` (filter preset); holistic keeps `exercise_id`. `ModuleCompletion` gains `attempt_count`, `passing_count`, `is_complete` to track progress toward a count criterion. A new `/start` route picks a random filtered exercise each time. The student module detail page shows Bootstrap cards per exercise; results pages show a live counter.

**Tech Stack:** Flask, SQLAlchemy (SQLite), Jinja2, Bootstrap 5, vanilla JS (for admin form type-switching).

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `models.py` | Modify | Add `name`, `params_json` to ModuleExercise; add `attempt_count`, `passing_count`, `is_complete` to ModuleCompletion |
| `migrate_presets.py` | Create | ALTER TABLE for the five new columns |
| `curriculum.py` | Modify | Replace `mark_complete` with `record_attempt`; update `completion_map`; add `get_progress` |
| `app.py` | Modify | Update `teacher_new_class` (course_id); update admin module exercise POST; add `start_module_exercise` route; update `_handle_module_completion` |
| `templates/teacher/new_class.html` | Modify | Add course dropdown |
| `templates/admin/courses.html` | Modify | Add classes-under-course section |
| `templates/admin/module_exercises.html` | Modify | Type-specific filter form with JS show/hide |
| `templates/student/module_detail.html` | Modify | Block-card view instead of list |
| `templates/results.html` | Modify | Progress counter banner |
| `templates/rhythm_results.html` | Modify | Progress counter banner |
| `templates/harmonic_results.html` | Modify | Progress counter banner |
| `templates/holistic_results.html` | Modify | Progress counter banner |

---

## Task A: Model Changes

**Files:**
- Modify: `models.py`

- [ ] **Step 1: Add `name` and `params_json` to ModuleExercise**

In `models.py`, in the `ModuleExercise` class, add after `exercise_id`:

```python
name      = db.Column(db.String(100), nullable=False, default='')
params_json = db.Column(db.Text, nullable=True)
```

Also add a property after `completion_criterion`:

```python
@property
def params(self):
    return json.loads(self.params_json) if self.params_json else {}
```

And update `__repr__`:
```python
def __repr__(self):
    return f'<ModuleExercise {self.name or self.exercise_type}>'
```

- [ ] **Step 2: Add `attempt_count`, `passing_count`, `is_complete` to ModuleCompletion**

In `models.py`, in the `ModuleCompletion` class, add after `best_score`:

```python
attempt_count = db.Column(db.Integer, nullable=False, default=0)
passing_count = db.Column(db.Integer, nullable=False, default=0)
is_complete   = db.Column(db.Boolean, nullable=False, default=False)
```

- [ ] **Step 3: Verify models import cleanly**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
.venv/bin/python -c "from models import ModuleExercise, ModuleCompletion; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
git add models.py
git commit -m "feat: add name/params_json to ModuleExercise, add attempt_count/passing_count/is_complete to ModuleCompletion"
```

---

## Task B: Migration

**Files:**
- Create: `migrate_presets.py`

- [ ] **Step 1: Write migrate_presets.py**

```python
"""
migrate_presets.py — adds new columns for module exercise presets and completion tracking.
Run once: .venv/bin/python migrate_presets.py
"""
from app import app
from models import db

with app.app_context():
    with db.engine.connect() as conn:
        alterations = [
            ("ALTER TABLE module_exercise ADD COLUMN name VARCHAR(100) NOT NULL DEFAULT ''",
             "Added name to module_exercise"),
            ("ALTER TABLE module_exercise ADD COLUMN params_json TEXT",
             "Added params_json to module_exercise"),
            ("ALTER TABLE module_completion ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0",
             "Added attempt_count to module_completion"),
            ("ALTER TABLE module_completion ADD COLUMN passing_count INTEGER NOT NULL DEFAULT 0",
             "Added passing_count to module_completion"),
            ("ALTER TABLE module_completion ADD COLUMN is_complete INTEGER NOT NULL DEFAULT 0",
             "Added is_complete to module_completion"),
        ]
        for sql, label in alterations:
            try:
                conn.execute(db.text(sql))
                print(f"  {label}")
            except Exception as e:
                print(f"  Skipped ({label}): {e}")
        conn.commit()

    # Backfill: existing ModuleCompletion rows were created as "complete" (old behavior)
    with db.engine.connect() as conn:
        conn.execute(db.text(
            "UPDATE module_completion SET is_complete = 1, attempt_count = 1 WHERE is_complete = 0"
        ))
        conn.commit()
        print("  Backfilled existing completions as is_complete=1")

    print("Migration complete.")
```

- [ ] **Step 2: Run the migration**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
.venv/bin/python migrate_presets.py
```

Expected: lines saying "Added ...", then "Migration complete."

- [ ] **Step 3: Verify columns exist**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
.venv/bin/python -c "
from app import app
from models import db
with app.app_context():
    from sqlalchemy import inspect
    insp = inspect(db.engine)
    me_cols = [c['name'] for c in insp.get_columns('module_exercise')]
    mc_cols = [c['name'] for c in insp.get_columns('module_completion')]
    print('me cols OK:', 'name' in me_cols and 'params_json' in me_cols)
    print('mc cols OK:', 'attempt_count' in mc_cols and 'is_complete' in mc_cols)
"
```

Expected: both `OK`

- [ ] **Step 4: Commit**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
git add migrate_presets.py instance/musicianship.db
git commit -m "feat: migrate module_exercise and module_completion with preset/tracking columns"
```

---

## Task C: curriculum.py — Count-Based Completion

**Files:**
- Modify: `curriculum.py`

Replace `mark_complete` with `record_attempt`, update `completion_map`, add `get_progress`.

- [ ] **Step 1: Replace `mark_complete` with `record_attempt` in curriculum.py**

Remove the existing `mark_complete` function and replace with:

```python
def record_attempt(user_id, class_id, module_exercise_id=None, class_exercise_id=None,
                   score=None, criterion=None):
    """
    Record one attempt toward a module exercise. Increments counters and marks complete
    when criterion is met. Returns (ModuleCompletion, just_completed: bool).
    """
    if criterion is None:
        criterion = {'attempts': 1}

    mc = get_completion(user_id, class_id, module_exercise_id, class_exercise_id)
    if mc is None:
        mc = ModuleCompletion(
            user_id=user_id,
            class_id=class_id,
            module_exercise_id=module_exercise_id,
            class_exercise_id=class_exercise_id,
            attempt_count=0,
            passing_count=0,
            is_complete=False,
            best_score=None,
        )
        db.session.add(mc)

    was_complete = mc.is_complete
    mc.attempt_count += 1

    if score is not None:
        if mc.best_score is None or score > mc.best_score:
            mc.best_score = score
        min_score = criterion.get('min_score', 70)
        if score >= min_score:
            mc.passing_count += 1

    if not was_complete:
        required_attempts = criterion.get('attempts')
        required_passing  = criterion.get('passing')
        if required_attempts is not None and mc.attempt_count >= required_attempts:
            mc.is_complete = True
        elif required_passing is not None and mc.passing_count >= required_passing:
            mc.is_complete = True

    db.session.commit()
    return mc, (mc.is_complete and not was_complete)
```

- [ ] **Step 2: Update `get_completion` to stay the same (no change needed)**

The existing `get_completion` function is fine as-is.

- [ ] **Step 3: Update `completion_map` to only include completed records**

Replace the existing `completion_map` function with:

```python
def completion_map(user_id, class_id):
    """
    Return a set of (module_exercise_id, class_exercise_id) tuples that are
    fully complete (is_complete=True) for this user in this class.
    """
    completions = ModuleCompletion.query.filter_by(
        user_id=user_id, class_id=class_id, is_complete=True
    ).all()
    return {(c.module_exercise_id, c.class_exercise_id) for c in completions}
```

- [ ] **Step 4: Add `get_progress` function**

Add after `completion_map`:

```python
def get_progress(user_id, class_id, module_exercise_id=None, class_exercise_id=None,
                 criterion=None):
    """
    Return progress dict: {'count': int, 'required': int, 'complete': bool}.
    'count' is attempts or passing_count depending on criterion type.
    """
    if criterion is None:
        criterion = {'attempts': 1}

    mc = get_completion(user_id, class_id, module_exercise_id, class_exercise_id)
    if mc is None:
        count = 0
    elif 'passing' in criterion:
        count = mc.passing_count
    else:
        count = mc.attempt_count

    required = criterion.get('attempts') or criterion.get('passing') or 1
    complete = mc.is_complete if mc else False
    return {'count': count, 'required': required, 'complete': complete}
```

- [ ] **Step 5: Verify curriculum.py imports cleanly**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
.venv/bin/python -c "import curriculum; print(dir(curriculum))"
```

Expected: output includes `record_attempt`, `get_progress`, `completion_map`

- [ ] **Step 6: Commit**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
git add curriculum.py
git commit -m "feat: curriculum record_attempt with count tracking, get_progress helper"
```

---

## Task D: Class Creation with Course + Course Page Lists Classes

**Files:**
- Modify: `app.py` (teacher_new_class route)
- Modify: `templates/teacher/new_class.html`
- Modify: `templates/admin/courses.html`

- [ ] **Step 1: Update teacher_new_class route in app.py**

Find the `teacher_new_class` function. Read the current version (lines ~1119–1133). Replace its body with:

```python
def teacher_new_class():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        course_id = request.form.get('course_id', type=int)
        if not name:
            flash('Class name is required.', 'danger')
            courses = Course.query.order_by(Course.name).all()
            return render_template('teacher/new_class.html', courses=courses)
        join_code = secrets.token_urlsafe(8)[:8].upper()
        cls = Class(name=name, join_code=join_code,
                    teacher_id=current_user.id,
                    course_id=course_id if course_id else None)
        db.session.add(cls)
        db.session.commit()
        flash(f'Class "{name}" created. Join code: {join_code}', 'success')
        return redirect(url_for('teacher_class_detail', class_id=cls.id))
    courses = Course.query.order_by(Course.name).all()
    return render_template('teacher/new_class.html', courses=courses)
```

- [ ] **Step 2: Update templates/teacher/new_class.html**

Read the existing template, then replace the form body to add a course selector. The full new template:

```html
{% extends 'base.html' %}
{% block title %}New Class{% endblock %}
{% block content %}
<div class="container py-4" style="max-width:500px">
  <h2 class="mb-4">Create a New Class</h2>
  <form method="post">
    <div class="mb-3">
      <label class="form-label fw-semibold">Class Name</label>
      <input name="name" class="form-control" placeholder="e.g. TEST101-001" required>
      <div class="form-text">Name your class like a section number, e.g. MUS201-002.</div>
    </div>
    <div class="mb-3">
      <label class="form-label fw-semibold">Course <span class="text-muted fw-normal">(optional)</span></label>
      <select name="course_id" class="form-select">
        <option value="">— No course —</option>
        {% for c in courses %}
        <option value="{{ c.id }}">{{ c.school.name }} / {{ c.name }}</option>
        {% endfor %}
      </select>
      <div class="form-text">Selecting a course gives students access to its modules.</div>
    </div>
    <button type="submit" class="btn btn-primary">Create Class</button>
    <a href="{{ url_for('teacher_dashboard') }}" class="btn btn-outline-secondary ms-2">Cancel</a>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 3: Add classes section to templates/admin/courses.html**

Read the existing `courses.html`. Update the courses table row to include a "Classes" link, and add a classes section below the courses table. Replace the file with:

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
    <thead><tr><th>Name</th><th>Modules</th><th>Classes</th><th></th></tr></thead>
    <tbody>
    {% for c in courses %}
    <tr>
      <td>{{ c.name }}</td>
      <td>{{ c.modules.count() }}</td>
      <td>{{ c.classes | length }}</td>
      <td class="d-flex gap-1">
        <a href="{{ url_for('admin_modules', course_id=c.id) }}" class="btn btn-sm btn-outline-secondary">Modules →</a>
        <form method="post" action="{{ url_for('admin_delete_course', course_id=c.id) }}" onsubmit="return confirm('Delete course &quot;{{ c.name }}&quot; and all its modules? This cannot be undone.')">
          <button class="btn btn-sm btn-outline-danger">Delete</button>
        </form>
      </td>
    </tr>
    {% else %}
    <tr><td colspan="4" class="text-muted">No courses yet.</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

- [ ] **Step 4: Verify app still starts**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
.venv/bin/python -c "from app import app; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
git add app.py templates/teacher/new_class.html templates/admin/courses.html
git commit -m "feat: class creation with course selector, course page shows class count"
```

---

## Task E: Admin Module Exercise Form (Filter Presets)

**Files:**
- Modify: `app.py` (admin_module_exercises POST handler)
- Modify: `templates/admin/module_exercises.html`

The new form collects: `name`, `exercise_type`, `order`, `completion_criterion` (JSON), and type-specific fields. For holistic: `exercise_id`. For others: `difficulty[]` (multi-value checkboxes), `tags` (comma-separated), `time_signature`, `key_signature`.

- [ ] **Step 1: Update admin_module_exercises POST in app.py**

Find the `admin_module_exercises` function. Replace its POST block:

```python
if request.method == 'POST':
    ex_type   = request.form['exercise_type']
    name      = request.form.get('name', '').strip() or ex_type.capitalize()
    order     = int(request.form.get('order', 0))
    criterion = request.form.get('completion_criterion', '{"attempts":1}')
    try:
        json.loads(criterion)
    except (ValueError, TypeError):
        criterion = '{"attempts":1}'

    if ex_type == 'holistic':
        ex_id      = int(request.form['exercise_id'])
        params_val = None
    else:
        ex_id = 0  # sentinel — not used for filter-based exercises
        difficulties = request.form.getlist('difficulty')
        tags_raw     = request.form.get('tags', '').strip()
        time_sig     = request.form.get('time_signature', '').strip()
        key_sig      = request.form.get('key_signature', '').strip()
        params_dict  = {}
        if difficulties:
            params_dict['difficulty'] = [int(d) for d in difficulties]
        if tags_raw:
            params_dict['tags'] = [t.strip() for t in tags_raw.split(',') if t.strip()]
        if time_sig:
            params_dict['time_signature'] = time_sig
        if key_sig and ex_type == 'harmonic':
            params_dict['key_signature'] = key_sig
        params_val = json.dumps(params_dict) if params_dict else None

    db.session.add(ModuleExercise(
        module_id=module_id,
        name=name,
        exercise_type=ex_type,
        exercise_id=ex_id,
        order=order,
        completion_criterion_json=criterion,
        params_json=params_val,
    ))
    db.session.commit()
    flash('Exercise added to module.', 'success')
    return redirect(url_for('admin_module_exercises', module_id=module_id))
```

- [ ] **Step 2: Replace templates/admin/module_exercises.html**

Write the new template with type-specific fields (JS toggles sections):

```html
{% extends 'base.html' %}
{% block title %}Admin — Module Exercises{% endblock %}
{% block content %}
<div class="container py-4">
  <h2>{{ module.name }} — Exercises</h2>
  <a href="{{ url_for('admin_modules', course_id=module.course_id) }}" class="btn btn-outline-secondary btn-sm mb-3">← Modules</a>

  <div class="card p-3 mb-4">
    <form method="post">
      <div class="row g-2 mb-2">
        <div class="col-md-4">
          <label class="form-label fw-semibold">Name</label>
          <input name="name" class="form-control" placeholder="e.g. Basic Melodic Dictation" required>
        </div>
        <div class="col-md-3">
          <label class="form-label fw-semibold">Type</label>
          <select name="exercise_type" class="form-select" id="ex-type" required>
            <option value="">Choose…</option>
            <option value="melody">Melodic</option>
            <option value="rhythm">Rhythmic</option>
            <option value="harmonic">Harmonic</option>
            <option value="holistic">Holistic</option>
          </select>
        </div>
        <div class="col-md-2">
          <label class="form-label fw-semibold">Order</label>
          <input name="order" type="number" class="form-control" value="0">
        </div>
        <div class="col-md-3">
          <label class="form-label fw-semibold">Completion</label>
          <input name="completion_criterion" class="form-control" value='{"attempts":1}'
                 placeholder='{"attempts":3} or {"passing":3,"min_score":70}'>
        </div>
      </div>

      <!-- Filter fields (melody / rhythm / harmonic) -->
      <div id="filter-fields" class="border rounded p-3 mb-2 d-none">
        <p class="fw-semibold mb-2">Filters <span class="text-muted fw-normal small">(leave blank = no filter)</span></p>
        <div class="row g-2">
          <div class="col-md-4">
            <label class="form-label">Difficulty</label>
            <div class="d-flex gap-2 flex-wrap">
              {% for d in [1,2,3,4,5] %}
              <div class="form-check">
                <input class="form-check-input" type="checkbox" name="difficulty" value="{{ d }}" id="diff{{ d }}">
                <label class="form-check-label" for="diff{{ d }}">{{ d }}</label>
              </div>
              {% endfor %}
            </div>
          </div>
          <div class="col-md-3">
            <label class="form-label">Time Signature</label>
            <select name="time_signature" class="form-select form-select-sm">
              <option value="">Any</option>
              <option value="4/4">4/4</option>
              <option value="3/4">3/4</option>
              <option value="6/8">6/8</option>
              <option value="2/4">2/4</option>
            </select>
          </div>
          <div class="col-md-3" id="key-sig-field">
            <label class="form-label">Key Signature <span class="text-muted small">(harmonic only)</span></label>
            <input name="key_signature" class="form-control form-control-sm" placeholder="e.g. C, G, Bb">
          </div>
          <div class="col-12">
            <label class="form-label">Tags <span class="text-muted small">(comma-separated)</span></label>
            <input name="tags" class="form-control form-control-sm" placeholder="e.g. diatonic, minor">
          </div>
        </div>
      </div>

      <!-- Holistic: pick specific exercise -->
      <div id="holistic-field" class="mb-2 d-none">
        <label class="form-label fw-semibold">Exercise</label>
        <select name="exercise_id" class="form-select">
          <option value="">Choose a holistic exercise…</option>
          {% for ex in holistics %}
          <option value="{{ ex.id }}">{{ ex.name }}</option>
          {% endfor %}
        </select>
      </div>

      <button class="btn btn-primary mt-2">Add Exercise</button>
    </form>
  </div>

  <table class="table table-sm">
    <thead><tr><th>#</th><th>Name</th><th>Type</th><th>Filters / Exercise</th><th>Criterion</th><th></th></tr></thead>
    <tbody>
    {% for ex in exercises %}
    <tr>
      <td>{{ ex.order }}</td>
      <td>{{ ex.name }}</td>
      <td><span class="badge bg-secondary">{{ ex.exercise_type }}</span></td>
      <td>
        {% if ex.params_json %}
          <code class="small">{{ ex.params_json }}</code>
        {% elif ex.exercise_type == 'holistic' %}
          {% set hol = holistics | selectattr('id', 'equalto', ex.exercise_id) | first %}
          {{ hol.name if hol else 'ID ' ~ ex.exercise_id }}
        {% else %}—{% endif %}
      </td>
      <td><code class="small">{{ ex.completion_criterion_json }}</code></td>
      <td>
        <form method="post" action="{{ url_for('admin_delete_module_exercise', me_id=ex.id) }}"
              onsubmit="return confirm('Remove this exercise from the module?')">
          <button class="btn btn-sm btn-outline-danger">Remove</button>
        </form>
      </td>
    </tr>
    {% else %}
    <tr><td colspan="6" class="text-muted">No exercises yet.</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}

{% block scripts %}
<script>
const typeSelect = document.getElementById('ex-type');
const filterFields = document.getElementById('filter-fields');
const holisticField = document.getElementById('holistic-field');
const keySigField = document.getElementById('key-sig-field');

typeSelect.addEventListener('change', () => {
  const t = typeSelect.value;
  filterFields.classList.toggle('d-none', t === '' || t === 'holistic');
  holisticField.classList.toggle('d-none', t !== 'holistic');
  keySigField.classList.toggle('d-none', t !== 'harmonic');
});
</script>
{% endblock %}
```

- [ ] **Step 3: Verify app starts and admin route loads**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
.venv/bin/python -c "from app import app; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
git add app.py templates/admin/module_exercises.html
git commit -m "feat: admin module exercise form with type-specific filter presets"
```

---

## Task F: start_module_exercise Route + Updated _handle_module_completion

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add `import random` at top of app.py**

Find the imports section of app.py and add `import random` if not already present.

- [ ] **Step 2: Add `_apply_exercise_filters` helper to app.py**

Add after the existing `_visible_exercise_filter` helper:

```python
def _apply_exercise_filters(query, model, params):
    """Apply params_json filter dict to a SQLAlchemy query for melody/rhythm/harmonic."""
    if params.get('difficulty'):
        query = query.filter(model.difficulty.in_(params['difficulty']))
    if params.get('time_signature'):
        query = query.filter(model.time_signature == params['time_signature'])
    if params.get('key_signature') and hasattr(model, 'key_signature'):
        query = query.filter(model.key_signature == params['key_signature'])
    if params.get('tags'):
        for tag_name in params['tags']:
            query = query.filter(model.tags.any(Tag.name == tag_name))
    return query
```

- [ ] **Step 3: Add `start_module_exercise` route to app.py**

Add after the `class_module_detail` route (around line 1230):

```python
@app.route('/class/<int:class_id>/module_exercise/<int:me_id>/start')
@login_required
def start_module_exercise(class_id, me_id):
    klass = Class.query.get_or_404(class_id)
    is_member = current_user in klass.members
    is_own_teacher = klass.teacher_id == current_user.id
    if not is_member and not is_own_teacher and current_user.role != 'admin':
        abort(403)

    me = ModuleExercise.query.get_or_404(me_id)
    if me.module.course_id != klass.course_id:
        abort(404)

    params = me.params
    type_map = {
        'melody':   (Melody,           'exercise',          'melody_id'),
        'rhythm':   (Rhythm,           'rhythm_exercise',   'rhythm_id'),
        'harmonic': (ChordProgression, 'harmonic_exercise', 'progression_id'),
    }

    if me.exercise_type == 'holistic':
        return redirect(url_for('holistic_exercise',
                                exercise_id=me.exercise_id,
                                class_id=class_id, me_id=me_id, cme_id=''))

    model_class, route_name, param_name = type_map[me.exercise_type]
    q = model_class.query.filter(_visible_exercise_filter(model_class))
    q = _apply_exercise_filters(q, model_class, params)
    candidates = q.all()

    if not candidates:
        flash('No exercises match the filters for this module exercise. Ask your teacher to adjust the filters.', 'warning')
        return redirect(url_for('class_module_detail',
                                class_id=class_id, module_id=me.module_id))

    chosen = random.choice(candidates)
    return redirect(url_for(route_name,
                            **{param_name: chosen.id},
                            class_id=class_id, me_id=me_id, cme_id=''))
```

- [ ] **Step 4: Update `_handle_module_completion` in app.py to use `record_attempt`**

Find `_handle_module_completion` (near the top of app.py, before routes). Replace it entirely:

```python
def _handle_module_completion(class_id, me_id, cme_id, score):
    """
    Called after a drill submission when the student came from a module.
    Records the attempt, checks criterion, returns nav context dict or None.
    """
    if not class_id:
        return None
    try:
        class_id_int = int(class_id)
        klass = Class.query.get(class_id_int)
        if not klass:
            return None
    except (ValueError, TypeError):
        return None

    is_member = current_user in klass.members
    is_own_teacher = klass.teacher_id == current_user.id
    if not is_member and not is_own_teacher and current_user.role != 'admin':
        return None

    me_id_int  = int(me_id)  if me_id  else None
    cme_id_int = int(cme_id) if cme_id else None

    me = ModuleExercise.query.get(me_id_int) if me_id_int else None
    criterion = me.completion_criterion if me else {'attempts': 1}

    mc, just_completed = cur.record_attempt(
        current_user.id, class_id_int, me_id_int, cme_id_int, score, criterion
    )

    progress = cur.get_progress(
        current_user.id, class_id_int, me_id_int, cme_id_int, criterion
    )

    module = me.module if me else None
    if not module and cme_id_int:
        cme = ClassModuleExercise.query.get(cme_id_int)
        if cme:
            module = Module.query.get(cme.module_id)

    if not module:
        return {
            'next_url': url_for('class_home', class_id=class_id_int),
            'module_done': False,
            'complete': mc.is_complete,
            'progress': progress,
            'class_id': class_id_int,
        }

    if mc.is_complete:
        next_ex = cur.next_incomplete(current_user.id, class_id_int, klass, module)
        if next_ex:
            # Next exercise in module
            if next_ex['module_exercise_id']:
                next_url = url_for('start_module_exercise',
                                   class_id=class_id_int,
                                   me_id=next_ex['module_exercise_id'])
            else:
                # class-only add (holistic path)
                next_url = url_for('class_module_detail',
                                   class_id=class_id_int, module_id=module.id)
            return {
                'next_url': next_url,
                'module_done': False,
                'complete': True,
                'progress': progress,
                'class_id': class_id_int,
                'module_id': module.id,
            }
        else:
            return {
                'next_url': url_for('class_module_detail',
                                    class_id=class_id_int, module_id=module.id),
                'module_done': True,
                'complete': True,
                'progress': progress,
                'class_id': class_id_int,
                'module_id': module.id,
            }
    else:
        # Not yet complete — go back to /start to get another exercise
        start_url = url_for('start_module_exercise',
                            class_id=class_id_int, me_id=me_id_int) if me_id_int else \
                    url_for('class_module_detail', class_id=class_id_int, module_id=module.id)
        return {
            'next_url': start_url,
            'module_done': False,
            'complete': False,
            'progress': progress,
            'class_id': class_id_int,
            'module_id': module.id,
        }
```

- [ ] **Step 5: Verify app starts**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
.venv/bin/python -c "from app import app; print('OK')"
```

- [ ] **Step 6: Commit**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
git add app.py
git commit -m "feat: start_module_exercise route picks random filtered exercise, updated _handle_module_completion with count tracking"
```

---

## Task G: Student Module Detail — Block View

**Files:**
- Modify: `app.py` (class_module_detail route)
- Modify: `templates/student/module_detail.html`

- [ ] **Step 1: Update class_module_detail route to pass start URLs**

Find the `class_module_detail` route. After building `ex_with_status`, replace the name-lookup loop with one that also computes `start_url`:

```python
for ex in ex_with_status:
    # Name lookup
    if ex['exercise_type'] == 'melody':
        obj = Melody.query.get(ex['exercise_id']) if ex['exercise_id'] else None
    elif ex['exercise_type'] == 'rhythm':
        obj = Rhythm.query.get(ex['exercise_id']) if ex['exercise_id'] else None
    elif ex['exercise_type'] == 'harmonic':
        obj = ChordProgression.query.get(ex['exercise_id']) if ex['exercise_id'] else None
    elif ex['exercise_type'] == 'holistic':
        obj = HolisticExercise.query.get(ex['exercise_id']) if ex['exercise_id'] else None
    else:
        obj = None

    # Get the ModuleExercise to read its name
    me_obj = ModuleExercise.query.get(ex['module_exercise_id']) if ex['module_exercise_id'] else None
    ex['name'] = (me_obj.name if me_obj and me_obj.name else None) or \
                 (obj.name if obj else f"Exercise #{ex['exercise_id']}")

    # Start URL
    if ex['module_exercise_id']:
        ex['start_url'] = url_for('start_module_exercise',
                                  class_id=class_id,
                                  me_id=ex['module_exercise_id'])
    else:
        # class-only add — link directly to exercise
        type_to_route = {
            'melody':   ('exercise',          'melody_id'),
            'rhythm':   ('rhythm_exercise',   'rhythm_id'),
            'harmonic': ('harmonic_exercise', 'progression_id'),
            'holistic': ('holistic_exercise', 'exercise_id'),
        }
        route_name, param_name = type_to_route.get(ex['exercise_type'], ('class_home', 'class_id'))
        ex['start_url'] = url_for(route_name,
                                  **{param_name: ex['exercise_id']},
                                  class_id=class_id,
                                  me_id='', cme_id=ex['class_exercise_id'] or '')

    # Progress toward completion criterion
    me_obj2 = ModuleExercise.query.get(ex['module_exercise_id']) if ex['module_exercise_id'] else None
    criterion = me_obj2.completion_criterion if me_obj2 else {'attempts': 1}
    ex['progress'] = cur.get_progress(
        current_user.id, class_id,
        ex['module_exercise_id'], ex['class_exercise_id'],
        criterion
    )
```

- [ ] **Step 2: Replace templates/student/module_detail.html with block view**

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
  <h2 class="mb-4">{{ module.name }}</h2>

  {% if not exercises %}
  <p class="text-muted">No exercises in this module yet.</p>
  {% else %}
  <div class="row g-3">
  {% for ex in exercises %}
    {% set prog = ex.progress %}
    <div class="col-sm-6 col-md-4">
      <a href="{{ ex.start_url }}" class="card h-100 text-decoration-none
        {% if ex.completed %} border-success{% endif %}">
        <div class="card-body d-flex flex-column">
          <div class="d-flex justify-content-between align-items-start mb-2">
            <span class="badge bg-secondary">
              {% if ex.exercise_type == 'melody' %}Melodic
              {% elif ex.exercise_type == 'rhythm' %}Rhythmic
              {% elif ex.exercise_type == 'harmonic' %}Harmonic
              {% elif ex.exercise_type == 'holistic' %}Holistic
              {% endif %}
            </span>
            {% if ex.completed %}
              <span class="badge bg-success">
                ✓{% if ex.best_score is not none %} {{ ex.best_score | int }}%{% endif %}
              </span>
            {% endif %}
          </div>
          <h5 class="card-title mb-1">{{ ex.name }}</h5>
          <div class="mt-auto pt-2">
            {% if prog.required > 1 %}
            <div class="d-flex justify-content-between small text-muted mb-1">
              <span>Progress</span>
              <span>{{ prog.count }}/{{ prog.required }}</span>
            </div>
            <div class="progress" style="height:4px">
              <div class="progress-bar {% if ex.completed %}bg-success{% endif %}"
                   style="width:{{ [prog.count / prog.required * 100, 100] | min | int }}%"></div>
            </div>
            {% elif not ex.completed %}
            <span class="text-muted small">Not started</span>
            {% endif %}
          </div>
        </div>
      </a>
    </div>
  {% endfor %}
  </div>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 3: Verify app starts**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
.venv/bin/python -c "from app import app; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
git add app.py templates/student/module_detail.html
git commit -m "feat: module detail block-card view with progress bars and start URLs"
```

---

## Task H: Results Templates — Progress Counter

All four results templates need an updated `module_ctx` banner that shows progress count.

**Files:**
- Modify: `templates/results.html`
- Modify: `templates/rhythm_results.html`
- Modify: `templates/harmonic_results.html`
- Modify: `templates/holistic_results.html`

- [ ] **Step 1: Read each results template to find the existing `module_ctx` banner**

In each template, find the block that looks like:
```html
{% if module_ctx %}
<div class="alert alert-info ...">
  {% if module_ctx.module_done %}
  ...
```

- [ ] **Step 2: Replace the module_ctx banner in all four templates**

Replace the existing banner with this version (identical in all four files):

```html
{% if module_ctx %}
<div class="alert {% if module_ctx.complete %}alert-success{% else %}alert-info{% endif %} mt-3">
  <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
    <div>
      {% set prog = module_ctx.progress %}
      {% if module_ctx.module_done %}
        <strong>Module complete!</strong> All exercises in this module are done.
      {% elif module_ctx.complete %}
        <strong>Exercise complete!</strong> Ready for the next one.
        {% if prog.required > 1 %}
        <span class="text-muted small ms-2">({{ prog.count }}/{{ prog.required }} done)</span>
        {% endif %}
      {% else %}
        Keep going —
        {% if prog.required > 1 %}
        <strong>{{ prog.count }}/{{ prog.required }}</strong> done toward completion.
        {% else %}
        almost there!
        {% endif %}
      {% endif %}
    </div>
    <a href="{{ module_ctx.next_url }}" class="btn btn-sm {% if module_ctx.complete %}btn-success{% else %}btn-primary{% endif %}">
      {% if module_ctx.module_done %}Back to Module
      {% elif module_ctx.complete %}Next Exercise →
      {% else %}Next →
      {% endif %}
    </a>
  </div>
  {% if module_ctx.progress.required > 1 and not module_ctx.module_done %}
  <div class="progress mt-2" style="height:4px">
    {% set pct = [module_ctx.progress.count / module_ctx.progress.required * 100, 100] | min | int %}
    <div class="progress-bar {% if module_ctx.complete %}bg-success{% endif %}"
         style="width:{{ pct }}%"></div>
  </div>
  {% endif %}
</div>
{% endif %}
```

- [ ] **Step 3: Verify app starts**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
.venv/bin/python -c "from app import app; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
git add templates/results.html templates/rhythm_results.html templates/harmonic_results.html templates/holistic_results.html
git commit -m "feat: results progress counter banner with count/required and progress bar"
```

---

## Self-Review

### Spec Coverage

| Requirement | Task |
|---|---|
| Can't delete classes | Fixed before plan (hotfix commit) |
| Class creation prompts for course | Task D |
| Classes listed under course in admin | Task D |
| Module exercises are filter presets (melody/rhythm/harmonic) | Tasks A, B, E |
| Holistic module exercises still pick specific exercise | Task E |
| Completion criterion: N attempts or N passing with min score | Tasks A, B, C |
| Student module detail is block-card view | Task G |
| Clicking block → drills with filters applied | Task F (start_module_exercise) |
| Progress counter on results page | Task H |
| When count reached: prompted to continue or move on | Task F (_handle_module_completion) |

### Notes

- `exercise_id = 0` is used as a sentinel for filter-based exercises since SQLite can't ALTER COLUMN to nullable. The `start_module_exercise` route never uses `exercise_id` for non-holistic types.
- The existing `mark_complete` calls in `curriculum.py` are replaced by `record_attempt`. Any code in app.py that previously called `cur.mark_complete` must be updated — `_handle_module_completion` is the only caller, and it's replaced in Task F.
- `min` filter in Jinja2: `[a, b] | min` works in Jinja2 (it's a built-in filter).
