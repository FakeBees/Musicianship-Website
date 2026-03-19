"""
migrate.py
==========
Idempotent schema migration — safe to run on every deploy.

  1. db.create_all()  — creates any tables that don't exist yet (new models).
  2. ADD COLUMN IF NOT EXISTS — adds any columns that were added to existing
     tables since the database was first created.

This is intentionally simple (no Alembic/Flask-Migrate).  Each migration is
a plain ALTER TABLE statement guarded by IF NOT EXISTS so re-running is safe.

Usage (run once before the app starts):
    python migrate.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import db

# Each entry: (table_name, column_name, column_definition)
# Use PostgreSQL syntax; SQLite is only used locally and doesn't run this.
MIGRATIONS = [
    # ── melody ───────────────────────────────────────────────────────────────
    ('melody',            'description', 'VARCHAR(300)'),
    ('melody',            'source_key',  'VARCHAR(100)'),

    # ── rhythm ───────────────────────────────────────────────────────────────
    ('rhythm',            'description', 'VARCHAR(300)'),
    ('rhythm',            'source_key',  'VARCHAR(100)'),
    ('rhythm',            'difficulty',  'INTEGER DEFAULT 1'),

    # ── chord_progression ────────────────────────────────────────────────────
    ('chord_progression', 'description', 'VARCHAR(300)'),
    ('chord_progression', 'source_key',  'VARCHAR(100)'),

    # ── holistic_exercise ────────────────────────────────────────────────────
    # (entire table is created by db.create_all if it doesn't exist;
    #  list individual columns here only if added after initial table creation)
    ('holistic_exercise', 'description', 'VARCHAR(300)'),
    ('holistic_exercise', 'source_key',  'VARCHAR(100)'),
]


def run():
    with app.app_context():
        # Step 1 — create any tables that are entirely new
        db.create_all()
        print('✓ db.create_all() complete')

        # Step 2 — add any missing columns to existing tables
        with db.engine.connect() as conn:
            for table, column, definition in MIGRATIONS:
                sql = (f'ALTER TABLE {table} '
                       f'ADD COLUMN IF NOT EXISTS {column} {definition}')
                try:
                    conn.execute(db.text(sql))
                    print(f'  ✓ {table}.{column}')
                except Exception as e:
                    # Shouldn't happen with IF NOT EXISTS, but log and continue
                    print(f'  WARNING: {table}.{column}: {e}')
            conn.commit()

        print('Migration complete.')


if __name__ == '__main__':
    run()
