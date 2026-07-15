"""
Holistic lines migration
=========================
Converts each HolisticExercise's melody_notes_json / harmony_chords_json /
extra_lines_json into HolisticLine rows, then drops those columns plus
melody_clef from holistic_exercise.

Run once: python3 migrate_holistic_lines.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from app import app
from models import db, HolisticExercise, HolisticLine


def col_exists(conn, table, col):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == col for r in rows)


with app.app_context():
    conn = db.engine.raw_connection()
    cur = conn.cursor()

    # 1. Create holistic_line table if it doesn't exist yet.
    db.create_all()

    # 2. Skip entirely if already migrated (old columns already gone).
    if not col_exists(cur, 'holistic_exercise', 'melody_notes_json'):
        print("holistic_exercise already migrated — skipped.")
    else:
        exercises = cur.execute(
            "SELECT id, folder, melody_clef, melody_notes_json, harmony_chords_json, extra_lines_json "
            "FROM holistic_exercise"
        ).fetchall()

        for ex_id, folder, melody_clef, melody_notes_json, harmony_chords_json, extra_lines_json in exercises:
            order = 0

            # Primary melody line
            slug_mid = os.path.join('static', folder.rstrip('/'), os.path.basename(folder.rstrip('/')) + '.mid')
            midi_filename = ''
            if os.path.isfile(slug_mid):
                midi_filename = folder.rstrip('/') + '/' + os.path.basename(folder.rstrip('/')) + '.mid'
            cur.execute(
                "INSERT INTO holistic_line (holistic_exercise_id, line_type, name, \"order\", clef, midi_filename, content_json) "
                "VALUES (?, 'melody', 'Melody', ?, ?, ?, ?)",
                (ex_id, order, melody_clef or 'treble', midi_filename, melody_notes_json or '[]')
            )
            order += 1

            # Extra lines
            for line in json.loads(extra_lines_json or '[]'):
                cur.execute(
                    "INSERT INTO holistic_line (holistic_exercise_id, line_type, name, \"order\", clef, midi_filename, content_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (ex_id, line['type'], line.get('label', line['type'].capitalize()), order,
                     line.get('clef') if line['type'] == 'melody' else None,
                     line.get('file', ''), json.dumps(line.get('notes', [])))
                )
                order += 1

            # Harmony, if non-trivial
            harmony_chords = json.loads(harmony_chords_json or '[]')
            if harmony_chords:
                cur.execute(
                    "INSERT INTO holistic_line (holistic_exercise_id, line_type, name, \"order\", clef, midi_filename, content_json) "
                    "VALUES (?, 'harmonic', 'Harmony', ?, NULL, '', ?)",
                    (ex_id, order, harmony_chords_json)
                )
                order += 1

        print(f"Migrated {len(exercises)} holistic exercise(s) into holistic_line rows.")

        # 3. Drop old columns via table rebuild (SQLite has no DROP COLUMN before 3.35;
        #    rebuild is the portable approach and matches this repo's other migrations).
        cur.execute("""
            CREATE TABLE holistic_exercise_new (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           VARCHAR(100) NOT NULL,
                description    VARCHAR(300),
                folder         VARCHAR(200) NOT NULL,
                wav_filename   VARCHAR(100) NOT NULL DEFAULT 'audio.wav',
                source_key     VARCHAR(100),
                key_signature  VARCHAR(10) DEFAULT 'C',
                time_signature VARCHAR(10) DEFAULT '4/4',
                tempo          INTEGER DEFAULT 120,
                difficulty     INTEGER DEFAULT 1,
                visibility     VARCHAR(20) NOT NULL DEFAULT 'public',
                school_id      INTEGER,
                is_major       BOOLEAN DEFAULT 1,
                public_id      VARCHAR(12) UNIQUE
            )
        """)
        cur.execute("""
            INSERT INTO holistic_exercise_new
                (id, name, description, folder, wav_filename, source_key, key_signature,
                 time_signature, tempo, difficulty, visibility, school_id, is_major, public_id)
            SELECT id, name, description, folder, wav_filename, source_key, key_signature,
                   time_signature, tempo, difficulty, visibility, school_id, is_major, public_id
            FROM holistic_exercise
        """)
        cur.execute("DROP TABLE holistic_exercise")
        cur.execute("ALTER TABLE holistic_exercise_new RENAME TO holistic_exercise")
        print("Dropped melody_notes_json, harmony_chords_json, extra_lines_json, melody_clef from holistic_exercise.")

    conn.commit()
    conn.close()
    print("Migration complete.")
