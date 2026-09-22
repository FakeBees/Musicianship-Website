"""
seed_postgres.py — bring a deployed Postgres database up to the current schema
and load it with the contents of the local SQLite database.

Why this exists
---------------
The app only calls db.create_all() under `python app.py` or `flask init-db`.
Render starts it with `gunicorn app:app`, so a deployed database is never
created or updated by the app itself, and the seven migrate_*.py scripts have
only ever been run against the local SQLite file. A deployed Postgres therefore
drifts behind the code until something like logging in fails with
`relation "user" does not exist`.

What it does
------------
Creates every table the current models define, then copies the local SQLite
content into it in foreign-key-safe order, preserving ids, and finally sets each
Postgres id sequence past the highest copied id so later inserts don't collide.

Safety
------
* The local SQLite database is opened READ-ONLY and is never modified.
* The target comes from the DATABASE_URL environment variable. It is never
  printed — only its host and database name are shown.
* The default run makes NO changes: it reports what's there and what it'd do.
* Copying refuses to touch a table that already has rows, so it can't silently
  duplicate data. Use --recreate (with --yes) to drop and rebuild instead.

Usage
-----
    # 1. Install the Postgres driver if needed (it's in requirements.txt):
    .venv/bin/pip install psycopg2-binary

    # 2. Look, change nothing. Render → your Postgres → Connect →
    #    "External Database URL" (the internal dpg-…-a host only works
    #    from inside Render).
    DATABASE_URL='postgresql://…' .venv/bin/python seed_postgres.py

    # 3. Create any missing tables and copy the data in:
    DATABASE_URL='postgresql://…' .venv/bin/python seed_postgres.py --migrate

    # 3b. Or, if the target holds an old schema that can't be added to:
    DATABASE_URL='postgresql://…' .venv/bin/python seed_postgres.py --recreate --yes
"""
import argparse
import datetime
import os
import sqlite3
import sys

SOURCE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      'instance', 'musicianship.db')


def masked(url):
    """The target's host and database, never its credentials."""
    tail = url.rsplit('@', 1)[-1]
    return tail or '(unparsed)'


def source_tables(cur):
    return {r[0] for r in cur.execute(
        "select name from sqlite_master where type='table' "
        "and name not like 'sqlite_%'")}


def source_columns(cur, table):
    return [r[1] for r in cur.execute('PRAGMA table_info("%s")' % table)]


def coerce(value, column):
    """SQLite hands back ints for booleans and strings for datetimes; Postgres
    wants the real types."""
    import sqlalchemy as sa
    if value is None:
        return None
    if isinstance(column.type, sa.Boolean):
        return bool(value)
    if isinstance(column.type, (sa.DateTime, sa.Date)) and isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                parsed = datetime.datetime.strptime(text, fmt)
                return parsed.date() if isinstance(column.type, sa.Date) \
                    and not isinstance(column.type, sa.DateTime) else parsed
            except ValueError:
                continue
        return None
    return value


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--migrate', action='store_true',
                    help='create missing tables and copy data into empty ones')
    ap.add_argument('--recreate', action='store_true',
                    help='DROP every table in the target, recreate, then copy')
    ap.add_argument('--yes', action='store_true',
                    help='required alongside --recreate')
    args = ap.parse_args()

    url = os.environ.get('DATABASE_URL', '').strip()
    if not url:
        sys.exit('DATABASE_URL is not set. See the usage notes at the top of this file.')
    if url.startswith('sqlite') and os.path.abspath(url.split('///')[-1]) == SOURCE:
        sys.exit('Refusing to run: the target is the local source database.')
    if not os.path.exists(SOURCE):
        sys.exit(f'Local database not found at {SOURCE}')

    # Import the app with the target URL already in the environment, so its
    # models bind to the target rather than to the local SQLite file.
    from app import app                      # noqa: E402
    from models import db                    # noqa: E402
    import sqlalchemy as sa                  # noqa: E402

    if app.config['SQLALCHEMY_DATABASE_URI'] != url:
        sys.exit('The app did not pick up DATABASE_URL — set it in the same command.')

    print(f'target : {masked(url)}')
    print(f'source : {SOURCE} (read-only)')

    src = sqlite3.connect('file:%s?mode=ro' % SOURCE, uri=True)
    src.row_factory = sqlite3.Row
    cur = src.cursor()
    have = source_tables(cur)

    with app.app_context():
        engine = db.engine
        tables = list(db.metadata.sorted_tables)          # foreign-key-safe order
        inspector = sa.inspect(engine)
        existing = set(inspector.get_table_names())

        print(f'\nmodels define {len(tables)} tables; target currently has {len(existing)}')
        missing = [t.name for t in tables if t.name not in existing]
        if missing:
            print(f'  missing from target : {", ".join(missing)}')

        # Tables that exist but lack columns the models need can't be fixed by
        # create_all() — that only ever adds whole tables.
        stale = {}
        for t in tables:
            if t.name in existing:
                target_cols = {c['name'] for c in inspector.get_columns(t.name)}
                gap = [c.name for c in t.columns if c.name not in target_cols]
                if gap:
                    stale[t.name] = gap
        if stale:
            print('  tables with missing columns (create_all cannot fix these):')
            for name, gap in stale.items():
                print(f'    {name}: {", ".join(gap)}')

        if not args.migrate and not args.recreate:
            print('\nNo changes made (inspection only).')
            if stale:
                print('Because some existing tables are out of date, use:')
                print('  … seed_postgres.py --recreate --yes     (drops and rebuilds everything)')
            else:
                print('Run again with --migrate to create the missing tables and copy the data.')
            return

        if args.recreate:
            if not args.yes:
                sys.exit('--recreate also needs --yes. It DROPS every table in the target first.')
            counts = {}
            for name in existing:
                try:
                    counts[name] = engine.connect().execute(
                        sa.text('select count(*) from "%s"' % name)).scalar()
                except Exception:
                    counts[name] = '?'
            non_empty = {k: v for k, v in counts.items() if v not in (0, '?')}
            if non_empty:
                print('\nAbout to DROP these non-empty target tables:')
                for k, v in sorted(non_empty.items()):
                    print(f'    {k}: {v} rows')
            print('\ndropping and recreating…')
            db.drop_all()
            db.create_all()
        else:
            # Check before creating anything, so a refused run leaves the
            # target exactly as it was rather than half-built.
            if stale:
                sys.exit('Some existing tables are missing columns; create_all() cannot add them, '
                         'so nothing was changed.\n'
                         'Re-run with --recreate --yes to rebuild the target from scratch.')
            print('\ncreating missing tables…')
            db.create_all()

        # ── copy ────────────────────────────────────────────────────────────
        copied = {}
        with engine.begin() as conn:
            for table in tables:
                if table.name not in have:
                    continue
                already = conn.execute(
                    sa.select(sa.func.count()).select_from(table)).scalar()
                if already:
                    sys.exit(f'Refusing to copy into "{table.name}": it already has '
                             f'{already} rows. Re-run with --recreate --yes to rebuild.')
                shared = [c for c in table.columns
                          if c.name in source_columns(cur, table.name)]
                rows = cur.execute(
                    'select %s from "%s"' % (
                        ', '.join('"%s"' % c.name for c in shared), table.name)
                ).fetchall()
                if not rows:
                    continue
                conn.execute(table.insert(), [
                    {c.name: coerce(r[c.name], c) for c in shared} for r in rows])
                copied[table.name] = len(rows)

            # Explicit ids don't advance Postgres sequences; the next insert
            # would collide without this.
            if engine.dialect.name == 'postgresql':
                for table in tables:
                    if 'id' in table.columns:
                        conn.execute(sa.text(
                            'select setval(pg_get_serial_sequence(\'"%s"\', \'id\'), '
                            'greatest(coalesce((select max(id) from "%s"), 0), 1))'
                            % (table.name, table.name)))

        print(f'\ncopied {sum(copied.values())} rows into {len(copied)} tables')
        for name in sorted(copied):
            print(f'    {name}: {copied[name]}')

        # ── verify ──────────────────────────────────────────────────────────
        problems = []
        with engine.connect() as conn:
            for table in tables:
                if table.name not in have:
                    continue
                want = cur.execute('select count(*) from "%s"' % table.name).fetchone()[0]
                got = conn.execute(sa.select(sa.func.count()).select_from(table)).scalar()
                if want != got:
                    problems.append(f'{table.name}: source {want}, target {got}')
        if problems:
            print('\nROW COUNTS DO NOT MATCH:')
            for p in problems:
                print('   ', p)
            sys.exit(1)
        print('\nEvery table matches the source. The deployed site should work now.')


if __name__ == '__main__':
    main()
