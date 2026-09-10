# School System — Schema & Role Changes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `School.join_code`, `SchoolMembership` table, `Class.assigned_teacher_id` FK, and rename the `teacher` role to `admin_teacher` (adding a new `class_teacher` role), so the UI plans that follow can build on a stable data foundation.

**Architecture:** Raw-SQL idempotent migration script (same pattern as `migrate_phase3a.py`). Model changes in `models.py`. All existing `@role_required('teacher', 'admin')` guards broadened to also accept `'admin_teacher'` so the site keeps working while the rename rolls out.

**Tech Stack:** Flask-SQLAlchemy, SQLite, Python 3

## Global Constraints

- Never edit files under `templates/admin/` that touch the Phase 3 CMS (melodies, harmonics, rhythms, holistic, gen_progressions, melody_generator). Those stay `@role_required('admin')` only.
- Migration script must be idempotent (safe to run twice).
- Do NOT use Alembic — raw `db.engine.execute` / `sqlite3` pattern only, matching existing scripts.
- `join_code` on School is a plaintext random 8-char alphanumeric string for now (noted as temporary; will be made more secure later).

---

### Task 1: Model changes in `models.py`

**Files:**
- Modify: `models.py` (lines 362–410 — User, class_members, Class, School)

**Interfaces:**
- Produces: `User.role` values `'student' | 'admin_teacher' | 'class_teacher' | 'admin'` (documented in model docstring)
- Produces: `SchoolMembership` ORM class with columns `(id, school_id, user_id, role)`
- Produces: `School.join_code: str` column, `School.memberships` relationship
- Produces: `Class.assigned_teacher_id: int|None` FK, `Class.assigned_teacher` relationship

- [ ] **Step 1: Write the failing test**

```python
# tests/test_school_schema.py
import pytest
from app import app
from models import db, User, School, SchoolMembership, Class

@pytest.fixture(autouse=True)
def ctx():
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()

def test_school_has_join_code():
    s = School(name='Test School', join_code='ABC12345')
    db.session.add(s)
    db.session.commit()
    assert School.query.first().join_code == 'ABC12345'

def test_school_membership_model():
    s = School(name='S', join_code='XY123456')
    u = User(email='a@b.com', password_hash='x', role='student')
    db.session.add_all([s, u])
    db.session.flush()
    m = SchoolMembership(school_id=s.id, user_id=u.id, role='student')
    db.session.add(m)
    db.session.commit()
    assert SchoolMembership.query.first().role == 'student'

def test_class_assigned_teacher():
    s = School(name='S2', join_code='ZZ999999')
    t = User(email='t@b.com', password_hash='x', role='class_teacher')
    db.session.add_all([s, t])
    db.session.flush()
    c = Class(name='C', join_code='AAA111', teacher_id=t.id)
    c.assigned_teacher_id = t.id
    db.session.add(c)
    db.session.commit()
    assert Class.query.first().assigned_teacher.email == 't@b.com'
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /Users/jareddamron/PycharmProjects/Musicianship
python -m pytest tests/test_school_schema.py -v
```

Expected: FAIL — `SchoolMembership` not defined, `School` has no `join_code`, etc.

- [ ] **Step 3: Apply model changes**

In `models.py`, after the existing `School` class definition, add the `SchoolMembership` model. Also add `join_code` to `School` and `assigned_teacher_id` to `Class`. Replace the block from line 362 to ~410 with:

```python
class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name  = db.Column(db.String(100))
    # role values: 'student' | 'admin_teacher' | 'class_teacher' | 'admin'
    role          = db.Column(db.String(20), nullable=False, default='student')
    created_at    = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f'<User {self.email} role={self.role}>'


class_members = db.Table(
    'class_members',
    db.Column('class_id', db.Integer, db.ForeignKey('class.id'), primary_key=True),
    db.Column('user_id',  db.Integer, db.ForeignKey('user.id'),  primary_key=True),
)


class Class(db.Model):
    __tablename__ = 'class'
    id                   = db.Column(db.Integer, primary_key=True)
    name                 = db.Column(db.String(120), nullable=False)
    join_code            = db.Column(db.String(12), unique=True, nullable=False)
    teacher_id           = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assigned_teacher_id  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at           = db.Column(db.DateTime, server_default=db.func.now())

    course_id  = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)
    course     = db.relationship('Course', backref='classes')

    teacher          = db.relationship('User', foreign_keys=[teacher_id],
                                       backref='classes_taught')
    assigned_teacher = db.relationship('User', foreign_keys=[assigned_teacher_id],
                                       backref='classes_assigned')
    members = db.relationship('User', secondary=class_members, backref='classes')

    def __repr__(self):
        return f'<Class {self.name}>'


class School(db.Model):
    __tablename__ = 'school'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False, unique=True)
    join_code  = db.Column(db.String(12), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    courses     = db.relationship('Course', backref='school', lazy='dynamic')
    memberships = db.relationship('SchoolMembership', backref='school', lazy='dynamic')

    def __repr__(self):
        return f'<School {self.name}>'


class SchoolMembership(db.Model):
    __tablename__ = 'school_membership'
    id        = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=False)
    user_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # role values: 'student' | 'admin_teacher' | 'class_teacher'
    role      = db.Column(db.String(20), nullable=False, default='student')
    joined_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship('User', backref='school_memberships')

    __table_args__ = (db.UniqueConstraint('school_id', 'user_id'),)

    def __repr__(self):
        return f'<SchoolMembership school={self.school_id} user={self.user_id} role={self.role}>'
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python -m pytest tests/test_school_schema.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add models.py tests/test_school_schema.py
git commit -m "feat: add SchoolMembership, School.join_code, Class.assigned_teacher_id, class_teacher role"
```

---

### Task 2: Migration script

**Files:**
- Create: `migrate_phase4_schema.py`

**Interfaces:**
- Consumes: existing SQLite DB at `instance/app.db`
- Produces: `school.join_code` column; `school_membership` table; `class.assigned_teacher_id` column; `user.role` values 'teacher' → 'admin_teacher'

- [ ] **Step 1: Write the migration script**

```python
# migrate_phase4_schema.py
"""
Phase 4 schema migration
========================
  - Adds school.join_code column (TEXT, nullable)
  - Creates school_membership table
  - Adds class.assigned_teacher_id column (INTEGER FK, nullable)
  - Renames user.role value 'teacher' -> 'admin_teacher' for all existing rows

Run once: python3 migrate_phase4_schema.py
"""
import sys, os, secrets, string
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from app import app
from models import db

ALPHA = string.ascii_uppercase + string.digits

def random_code(length=8):
    return ''.join(secrets.choice(ALPHA) for _ in range(length))

def col_exists(conn, table, col):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == col for r in rows)

def table_exists(conn, table):
    r = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return r is not None

with app.app_context():
    conn = db.engine.raw_connection()
    cur  = conn.cursor()

    # 1. school.join_code
    if not col_exists(cur, 'school', 'join_code'):
        cur.execute("ALTER TABLE school ADD COLUMN join_code TEXT")
        # backfill existing schools with unique codes
        schools = cur.execute("SELECT id FROM school").fetchall()
        used = set()
        for (sid,) in schools:
            code = random_code()
            while code in used:
                code = random_code()
            used.add(code)
            cur.execute("UPDATE school SET join_code=? WHERE id=?", (code, sid))
        print("Added school.join_code and backfilled.")
    else:
        print("school.join_code already exists — skipped.")

    # 2. school_membership table
    if not table_exists(cur, 'school_membership'):
        cur.execute("""
            CREATE TABLE school_membership (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                school_id INTEGER NOT NULL REFERENCES school(id),
                user_id   INTEGER NOT NULL REFERENCES user(id),
                role      TEXT NOT NULL DEFAULT 'student',
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(school_id, user_id)
            )
        """)
        print("Created school_membership table.")
    else:
        print("school_membership already exists — skipped.")

    # 3. class.assigned_teacher_id
    if not col_exists(cur, 'class', 'assigned_teacher_id'):
        cur.execute("ALTER TABLE class ADD COLUMN assigned_teacher_id INTEGER REFERENCES user(id)")
        print("Added class.assigned_teacher_id.")
    else:
        print("class.assigned_teacher_id already exists — skipped.")

    # 4. rename role 'teacher' -> 'admin_teacher'
    count = cur.execute(
        "SELECT COUNT(*) FROM user WHERE role='teacher'"
    ).fetchone()[0]
    if count > 0:
        cur.execute("UPDATE user SET role='admin_teacher' WHERE role='teacher'")
        print(f"Renamed {count} 'teacher' user(s) to 'admin_teacher'.")
    else:
        print("No 'teacher' roles to rename — skipped.")

    conn.commit()
    conn.close()
    print("Migration complete.")
```

- [ ] **Step 2: Run the migration**

```bash
python3 migrate_phase4_schema.py
```

Expected output (first run):
```
Added school.join_code and backfilled.
Created school_membership table.
Added class.assigned_teacher_id.
Renamed N 'teacher' user(s) to 'admin_teacher'.
Migration complete.
```

- [ ] **Step 3: Verify the migration is idempotent (run twice)**

```bash
python3 migrate_phase4_schema.py
```

Expected: all four lines say "already exists — skipped" or "No 'teacher' roles to rename — skipped".

- [ ] **Step 4: Commit**

```bash
git add migrate_phase4_schema.py
git commit -m "feat: phase 4 migration — join_code, school_membership, assigned_teacher_id, rename teacher role"
```

---

### Task 3: Update `role_required` guards in `app.py`

**Files:**
- Modify: `app.py`

**Context:** After the migration, existing teacher accounts have role `'admin_teacher'`. All routes that previously used `@role_required('teacher', 'admin')` must now also accept `'admin_teacher'`. The `'class_teacher'` role gets its own routes in the UI plan — do NOT add it to admin_teacher routes here.

**Interfaces:**
- Consumes: Task 2 (role rename)
- Produces: all existing teacher/admin routes accept `'admin_teacher'` in addition to (or instead of) the now-gone `'teacher'` string

- [ ] **Step 1: Write a test verifying the guard**

```python
# tests/test_role_guards.py
import pytest
from app import app
from models import db, User
from werkzeug.security import generate_password_hash

@pytest.fixture(autouse=True)
def ctx():
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()

def _make_user(role):
    u = User(email=f'{role}@test.com',
             password_hash=generate_password_hash('pw'),
             role=role)
    db.session.add(u)
    db.session.commit()
    return u

def test_admin_teacher_can_access_teacher_dashboard(client):
    with app.test_client() as c:
        with app.app_context():
            db.create_all()
            u = _make_user('admin_teacher')
        with c.session_transaction() as sess:
            sess['_user_id'] = str(u.id)
            sess['_fresh'] = True
        resp = c.get('/teacher', follow_redirects=False)
        assert resp.status_code == 200
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest tests/test_role_guards.py -v
```

Expected: FAIL (403 because 'admin_teacher' not in current guard)

- [ ] **Step 3: Update all teacher-level role guards**

In `app.py`, do a global find-replace:

Change every occurrence of:
```python
@role_required('teacher', 'admin')
```
to:
```python
@role_required('admin_teacher', 'admin')
```

Also change the join_class and leave_class routes (which use `@login_required` only — leave those alone, they are student-accessible).

Affected route functions (search for `role_required('teacher'`):
- `teacher_delete_class`
- `teacher_kick_student`
- `teacher_dashboard`
- `teacher_edit_class`
- `teacher_new_class`
- `teacher_class_detail`
- `teacher_set_course`
- `teacher_add_override`
- `teacher_delete_override`

Also update the nav check in `base.html` (line 45):
```html
{% if current_user.role in ('admin_teacher', 'admin') %}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python -m pytest tests/test_role_guards.py tests/test_school_schema.py -v
```

Expected: all PASS

- [ ] **Step 5: Smoke-test the app manually**

```bash
python app.py
```

Log in as an existing teacher account (now `admin_teacher`). Confirm `/teacher` loads without 403.

- [ ] **Step 6: Commit**

```bash
git add app.py templates/base.html tests/test_role_guards.py
git commit -m "fix: update role_required guards and nav check from 'teacher' to 'admin_teacher'"
```
