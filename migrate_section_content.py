"""
Section content migration
==========================
Lets a section own modules and module exercises of its own, alongside the ones
its course provides. Adds a nullable `class_id` column to `module` and to
`module_exercise`:

    NULL      -> course content, shared by every section following the course
    <section> -> belongs to that one section only

The physical column is named `class_id`, following the rest of the schema; the
Python attribute is `section_id`. See docs/NAMING.md.

Purely additive: existing rows are untouched (they read as NULL, i.e. course
content), and code that doesn't know about the column ignores it.

Run once: .venv/bin/python migrate_section_content.py   (safe to re-run)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from app import app
from models import db


def col_exists(cur, table, col):
    return any(r[1] == col for r in cur.execute(f"PRAGMA table_info({table})").fetchall())


with app.app_context():
    conn = db.engine.raw_connection()
    cur = conn.cursor()
    for table in ('module', 'module_exercise'):
        if col_exists(cur, table, 'class_id'):
            print(f'{table}.class_id already exists — skipped.')
            continue
        cur.execute(f'ALTER TABLE {table} ADD COLUMN class_id INTEGER REFERENCES class(id)')
        print(f'{table}.class_id added.')
    conn.commit()
    conn.close()
