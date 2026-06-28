"""
migrate_phase3a.py
==================
Adds Phase 3A schema changes to the existing SQLite DB:
  - Creates 'container' and 'gen_progression' tables
  - Adds public_id, container_id, generation_params columns
  - Backfills public_ids for all existing exercises
  - Seeds starter GenProgressions
  - Creates 'Unsorted' Container

Run once:  python3 migrate_phase3a.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

import json
from app import app
from models import db, Melody, ChordProgression, Rhythm, HolisticExercise, Container, GenProgression

STARTER_PROGRESSIONS = [
    # 2-bar major
    {'number': 1,  'name': 'I–V (2-bar major)',      'length_bars': 2, 'mode': 'major', 'difficulty': 1,
     'chords': [{'degree':'I','quality':'maj','inversion':0,'beats':4},{'degree':'V','quality':'maj','inversion':0,'beats':4}]},
    {'number': 2,  'name': 'I–IV (2-bar major)',     'length_bars': 2, 'mode': 'major', 'difficulty': 1,
     'chords': [{'degree':'I','quality':'maj','inversion':0,'beats':4},{'degree':'IV','quality':'maj','inversion':0,'beats':4}]},
    {'number': 3,  'name': 'I–vi (2-bar major)',     'length_bars': 2, 'mode': 'major', 'difficulty': 1,
     'chords': [{'degree':'I','quality':'maj','inversion':0,'beats':4},{'degree':'vi','quality':'min','inversion':0,'beats':4}]},
    # 2-bar minor
    {'number': 4,  'name': 'i–V (2-bar minor)',      'length_bars': 2, 'mode': 'minor', 'difficulty': 1,
     'chords': [{'degree':'i','quality':'min','inversion':0,'beats':4},{'degree':'V','quality':'maj','inversion':0,'beats':4}]},
    {'number': 5,  'name': 'i–VII (2-bar minor)',    'length_bars': 2, 'mode': 'minor', 'difficulty': 1,
     'chords': [{'degree':'i','quality':'min','inversion':0,'beats':4},{'degree':'VII','quality':'maj','inversion':0,'beats':4}]},
    # 4-bar major
    {'number': 6,  'name': 'I–IV–V–I (4-bar major)',     'length_bars': 4, 'mode': 'major', 'difficulty': 1,
     'chords': [{'degree':'I','quality':'maj','inversion':0,'beats':4},{'degree':'IV','quality':'maj','inversion':0,'beats':4},
                {'degree':'V','quality':'maj','inversion':0,'beats':4},{'degree':'I','quality':'maj','inversion':0,'beats':4}]},
    {'number': 7,  'name': 'I–V–vi–IV (4-bar major)',    'length_bars': 4, 'mode': 'major', 'difficulty': 1,
     'chords': [{'degree':'I','quality':'maj','inversion':0,'beats':4},{'degree':'V','quality':'maj','inversion':0,'beats':4},
                {'degree':'vi','quality':'min','inversion':0,'beats':4},{'degree':'IV','quality':'maj','inversion':0,'beats':4}]},
    {'number': 8,  'name': 'I–vi–IV–V (4-bar major)',    'length_bars': 4, 'mode': 'major', 'difficulty': 1,
     'chords': [{'degree':'I','quality':'maj','inversion':0,'beats':4},{'degree':'vi','quality':'min','inversion':0,'beats':4},
                {'degree':'IV','quality':'maj','inversion':0,'beats':4},{'degree':'V','quality':'maj','inversion':0,'beats':4}]},
    {'number': 9,  'name': 'I–ii–V–I (4-bar major)',     'length_bars': 4, 'mode': 'major', 'difficulty': 2,
     'chords': [{'degree':'I','quality':'maj','inversion':0,'beats':4},{'degree':'ii','quality':'min','inversion':0,'beats':4},
                {'degree':'V','quality':'maj','inversion':0,'beats':4},{'degree':'I','quality':'maj','inversion':0,'beats':4}]},
    {'number': 10, 'name': 'I–IV–ii–V (4-bar major)',    'length_bars': 4, 'mode': 'major', 'difficulty': 2,
     'chords': [{'degree':'I','quality':'maj','inversion':0,'beats':4},{'degree':'IV','quality':'maj','inversion':0,'beats':4},
                {'degree':'ii','quality':'min','inversion':0,'beats':4},{'degree':'V','quality':'maj','inversion':0,'beats':4}]},
    # 4-bar minor
    {'number': 11, 'name': 'i–iv–V–i (4-bar minor)',     'length_bars': 4, 'mode': 'minor', 'difficulty': 1,
     'chords': [{'degree':'i','quality':'min','inversion':0,'beats':4},{'degree':'iv','quality':'min','inversion':0,'beats':4},
                {'degree':'V','quality':'maj','inversion':0,'beats':4},{'degree':'i','quality':'min','inversion':0,'beats':4}]},
    {'number': 12, 'name': 'i–VII–VI–V (4-bar minor)',   'length_bars': 4, 'mode': 'minor', 'difficulty': 2,
     'chords': [{'degree':'i','quality':'min','inversion':0,'beats':4},{'degree':'VII','quality':'maj','inversion':0,'beats':4},
                {'degree':'VI','quality':'maj','inversion':0,'beats':4},{'degree':'V','quality':'maj','inversion':0,'beats':4}]},
    {'number': 13, 'name': 'i–VI–III–VII (4-bar minor)', 'length_bars': 4, 'mode': 'minor', 'difficulty': 2,
     'chords': [{'degree':'i','quality':'min','inversion':0,'beats':4},{'degree':'VI','quality':'maj','inversion':0,'beats':4},
                {'degree':'III','quality':'maj','inversion':0,'beats':4},{'degree':'VII','quality':'maj','inversion':0,'beats':4}]},
    # 8-bar major
    {'number': 14, 'name': 'I–I–IV–V–I–I–IV–V (8-bar)',  'length_bars': 8, 'mode': 'major', 'difficulty': 2,
     'chords': [{'degree':'I','quality':'maj','inversion':0,'beats':4},{'degree':'I','quality':'maj','inversion':0,'beats':4},
                {'degree':'IV','quality':'maj','inversion':0,'beats':4},{'degree':'V','quality':'maj','inversion':0,'beats':4},
                {'degree':'I','quality':'maj','inversion':0,'beats':4},{'degree':'I','quality':'maj','inversion':0,'beats':4},
                {'degree':'IV','quality':'maj','inversion':0,'beats':4},{'degree':'V','quality':'maj','inversion':0,'beats':4}]},
    {'number': 15, 'name': 'I–V–vi–IV×2 (8-bar)',         'length_bars': 8, 'mode': 'major', 'difficulty': 2,
     'chords': [{'degree':'I','quality':'maj','inversion':0,'beats':4},{'degree':'V','quality':'maj','inversion':0,'beats':4},
                {'degree':'vi','quality':'min','inversion':0,'beats':4},{'degree':'IV','quality':'maj','inversion':0,'beats':4},
                {'degree':'I','quality':'maj','inversion':0,'beats':4},{'degree':'V','quality':'maj','inversion':0,'beats':4},
                {'degree':'vi','quality':'min','inversion':0,'beats':4},{'degree':'IV','quality':'maj','inversion':0,'beats':4}]},
]


def run():
    with app.app_context():
        db.create_all()

        # --- Add new columns if missing (SQLite requires ALTER TABLE) ---
        import sqlite3
        db_path = os.path.join(os.path.dirname(__file__), 'instance', 'musicianship.db')
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        ALLOWED_TABLES = {'melody', 'chord_progression', 'rhythm', 'holistic_exercise'}
        ALLOWED_COLS_RE = __import__('re').compile(r'^[a-z_]+$')

        def add_column(table, col, col_type):
            assert table in ALLOWED_TABLES, f"Unexpected table: {table}"
            assert ALLOWED_COLS_RE.match(col), f"Unexpected column: {col}"
            try:
                cur.execute(f"PRAGMA table_info({table})")
                cols = [r[1] for r in cur.fetchall()]
                if col not in cols:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                    print(f"  Added {table}.{col}")
                else:
                    print(f"  {table}.{col} already exists")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    print(f"  {table}.{col} already exists (duplicate column)")
                else:
                    raise

        add_column('melody', 'public_id', 'VARCHAR(12)')
        add_column('melody', 'container_id', 'INTEGER')
        add_column('melody', 'generation_params', 'TEXT')
        add_column('chord_progression', 'public_id', 'VARCHAR(12)')
        add_column('rhythm', 'public_id', 'VARCHAR(12)')
        add_column('holistic_exercise', 'public_id', 'VARCHAR(12)')
        conn.commit()
        conn.close()

        # --- Backfill public_ids ---
        for m in Melody.query.order_by(Melody.id).all():
            if not m.public_id:
                m.public_id = f'MEL-{m.id:04d}'
        for c in ChordProgression.query.order_by(ChordProgression.id).all():
            if not c.public_id:
                c.public_id = f'HRM-{c.id:04d}'
        for r in Rhythm.query.order_by(Rhythm.id).all():
            if not r.public_id:
                r.public_id = f'RHY-{r.id:04d}'
        for h in HolisticExercise.query.order_by(HolisticExercise.id).all():
            if not h.public_id:
                h.public_id = f'HOL-{h.id:04d}'
        db.session.commit()
        print("  Backfilled public_ids")

        # --- Seed Unsorted container ---
        if not Container.query.filter_by(name='Unsorted').first():
            db.session.add(Container(name='Unsorted', description='Default container for uncategorised melodies'))
            db.session.commit()
            print("  Created 'Unsorted' container")

        # --- Seed GenProgressions ---
        for p in STARTER_PROGRESSIONS:
            if not GenProgression.query.filter_by(number=p['number']).first():
                gp = GenProgression(
                    number=p['number'], name=p['name'], length_bars=p['length_bars'],
                    mode=p['mode'], difficulty=p['difficulty'],
                    chords_json=json.dumps(p['chords']),
                )
                db.session.add(gp)
        db.session.commit()
        print(f"  Seeded {len(STARTER_PROGRESSIONS)} GenProgressions")
        print("Done.")


if __name__ == '__main__':
    run()
