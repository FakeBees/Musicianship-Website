"""
delete_exercise.py
==================
Permanently removes an exercise from the database and deletes any associated
static files.  Works for all four exercise types.

Usage:
    python3 delete_exercise.py <type> <source_key> [--dry-run]
    python3 delete_exercise.py <type> --id <id>    [--dry-run]

    <type>       one of: melodic | rhythmic | harmonic | holistic
    <source_key> the folder name used when the exercise was imported
                 (e.g.  ode_to_joy,  human_test_2)
    --id         look up by numeric DB id instead of source_key
    --dry-run    preview what would be deleted without making any changes

Examples:
    python3 delete_exercise.py melodic human_test_2
    python3 delete_exercise.py melodic human_test_2 --dry-run
    python3 delete_exercise.py holistic waltz_c_major
    python3 delete_exercise.py rhythmic human_test --id 3

What gets deleted
-----------------
  melodic   → UserAttempt rows, melody_tags rows, Melody row,
               static/melodic/<source_key>/
  rhythmic  → RhythmAttempt rows, rhythm_tags rows, Rhythm row
               (no static files — rhythm MIDIs are not stored on the server)
  harmonic  → HarmonicAttempt rows, progression_tags rows,
               ChordProgression row, static/harmonic/<source_key>/
  holistic  → HolisticAttempt rows, holistic_tags rows,
               HolisticExercise row, static/holistic/<source_key>/
"""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(__file__))

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

VALID_TYPES = ('melodic', 'rhythmic', 'harmonic', 'holistic')


# ---------------------------------------------------------------------------
# Per-type deletion logic
# ---------------------------------------------------------------------------

def _delete_melodic(record, dry_run):
    from models import db, UserAttempt

    attempts = UserAttempt.query.filter_by(melody_id=record.id).all()
    print(f'  Attempts   : {len(attempts)} UserAttempt row(s)')

    static_dir = os.path.join(STATIC_DIR, 'melodic', record.source_key) \
                 if record.source_key else None
    if static_dir and os.path.isdir(static_dir):
        print(f'  Static dir : {static_dir}')
    else:
        print(f'  Static dir : (not found — skipping)')
        static_dir = None

    if dry_run:
        return

    for a in attempts:
        db.session.delete(a)
    record.tags.clear()        # clears melody_tags association rows
    db.session.delete(record)
    db.session.commit()

    if static_dir:
        shutil.rmtree(static_dir)
        print(f'  ✓ Deleted  {static_dir}')


def _delete_rhythmic(record, dry_run):
    from models import db, RhythmAttempt

    attempts = RhythmAttempt.query.filter_by(rhythm_id=record.id).all()
    print(f'  Attempts   : {len(attempts)} RhythmAttempt row(s)')
    print(f'  Static dir : none (rhythm MIDIs are not stored on the server)')

    if dry_run:
        return

    for a in attempts:
        db.session.delete(a)
    record.tags.clear()
    db.session.delete(record)
    db.session.commit()


def _delete_harmonic(record, dry_run):
    from models import db, HarmonicAttempt

    attempts = HarmonicAttempt.query.filter_by(progression_id=record.id).all()
    print(f'  Attempts   : {len(attempts)} HarmonicAttempt row(s)')

    static_dir = os.path.join(STATIC_DIR, 'harmonic', record.source_key) \
                 if record.source_key else None
    if static_dir and os.path.isdir(static_dir):
        print(f'  Static dir : {static_dir}')
    else:
        print(f'  Static dir : (not found — skipping)')
        static_dir = None

    if dry_run:
        return

    for a in attempts:
        db.session.delete(a)
    record.tags.clear()
    db.session.delete(record)
    db.session.commit()

    if static_dir:
        shutil.rmtree(static_dir)
        print(f'  ✓ Deleted  {static_dir}')


def _delete_holistic(record, dry_run):
    from models import db, HolisticAttempt

    attempts = HolisticAttempt.query.filter_by(exercise_id=record.id).all()
    print(f'  Attempts   : {len(attempts)} HolisticAttempt row(s)')

    # folder is stored as e.g. "holistic/waltz_c_major/"
    static_dir = os.path.join(STATIC_DIR, record.folder.strip('/')) \
                 if record.folder else None
    if static_dir and os.path.isdir(static_dir):
        print(f'  Static dir : {static_dir}')
    else:
        print(f'  Static dir : (not found — skipping)')
        static_dir = None

    if dry_run:
        return

    for a in attempts:
        db.session.delete(a)
    record.tags.clear()
    db.session.delete(record)
    db.session.commit()

    if static_dir:
        shutil.rmtree(static_dir)
        print(f'  ✓ Deleted  {static_dir}')


# ---------------------------------------------------------------------------
# Public API — importable by other scripts
# ---------------------------------------------------------------------------

def delete_exercise(ex_type, source_key=None, ex_id=None, dry_run=False):
    """
    Delete a single exercise by source_key or numeric id.

    Parameters
    ----------
    ex_type    : 'melodic' | 'rhythmic' | 'harmonic' | 'holistic'
    source_key : folder name used at import time (mutually exclusive with ex_id)
    ex_id      : integer DB primary key       (mutually exclusive with source_key)
    dry_run    : if True, print what would be deleted but change nothing

    Raises ValueError for unknown type or record-not-found.
    """
    if ex_type not in VALID_TYPES:
        raise ValueError(f'Unknown exercise type "{ex_type}". '
                         f'Choose from: {", ".join(VALID_TYPES)}')
    if source_key is None and ex_id is None:
        raise ValueError('Provide either source_key or ex_id.')

    from models import db, Melody, Rhythm, ChordProgression, HolisticExercise

    model_map = {
        'melodic':  Melody,
        'rhythmic': Rhythm,
        'harmonic': ChordProgression,
        'holistic': HolisticExercise,
    }
    deleter_map = {
        'melodic':  _delete_melodic,
        'rhythmic': _delete_rhythmic,
        'harmonic': _delete_harmonic,
        'holistic': _delete_holistic,
    }

    model = model_map[ex_type]
    if ex_id is not None:
        record = model.query.get(ex_id)
        if record is None:
            raise ValueError(f'No {ex_type} exercise with id={ex_id}.')
    else:
        record = model.query.filter_by(source_key=source_key).first()
        if record is None:
            raise ValueError(f'No {ex_type} exercise with source_key="{source_key}".')

    label = 'DRY RUN — ' if dry_run else ''
    print(f'\n{label}Deleting {ex_type} exercise: "{record.name}" '
          f'(id={record.id}, source_key={record.source_key})')

    deleter_map[ex_type](record, dry_run)

    if not dry_run:
        print(f'  ✓ DB record deleted')
    else:
        print(f'  (dry run — nothing was changed)')


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    args     = sys.argv[1:]
    dry_run  = '--dry-run' in args
    if dry_run:
        args.remove('--dry-run')

    ex_id = None
    if '--id' in args:
        idx   = args.index('--id')
        ex_id = int(args[idx + 1])
        args  = args[:idx] + args[idx + 2:]

    if len(args) < 1:
        print(__doc__)
        sys.exit(0)

    ex_type    = args[0]
    source_key = args[1] if len(args) > 1 else None

    if source_key is None and ex_id is None:
        print('ERROR: provide a source_key or --id <id>')
        print(__doc__)
        sys.exit(1)

    from app import app
    with app.app_context():
        try:
            delete_exercise(ex_type, source_key=source_key, ex_id=ex_id,
                            dry_run=dry_run)
        except ValueError as e:
            print(f'ERROR: {e}')
            sys.exit(1)
