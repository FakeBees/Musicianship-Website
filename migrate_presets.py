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
