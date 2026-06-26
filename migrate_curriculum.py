"""
migrate_curriculum.py — adds all new curriculum tables and columns.
Run once: .venv/bin/python migrate_curriculum.py
"""
from app import app
from models import db

with app.app_context():
    db.create_all()  # creates all new tables

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

        try:
            conn.execute(db.text(
                "ALTER TABLE class ADD COLUMN course_id INTEGER REFERENCES course(id)"
            ))
            print("  Added course_id to class")
        except Exception as e:
            print(f"  Skipped course_id on class: {e}")

        conn.commit()

    print("Migration complete.")
