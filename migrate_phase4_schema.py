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
