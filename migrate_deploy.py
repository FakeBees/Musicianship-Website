"""
migrate_deploy.py — bring the deployed database up to the current models,
then let the app start.

Why this exists
---------------
The app only calls db.create_all() under `python app.py` or `flask init-db`.
Render starts it with gunicorn, so a deployed database was never created or
updated, and every schema change lived in a hand-run migrate_*.py script
against the local SQLite file. The deployed Postgres therefore drifted behind
the code until logging in failed with `relation "user" does not exist`.

Run this before the web server on every deploy:

    startCommand: python migrate_deploy.py && gunicorn app:app

It is idempotent — on an up-to-date database it changes nothing and exits 0.

What it handles
---------------
* tables in the models but not in the database  -> CREATE TABLE
* columns in the models but not in the database -> ALTER TABLE ADD COLUMN

That covers every schema change this project has made so far, which have all
been additive. Anything it cannot do safely — a new NOT NULL column with no
default, which cannot be backfilled for existing rows — makes it exit non-zero
**before the server starts**, so the deploy fails loudly and the previous
version keeps serving instead of 500ing on every page.

It never drops or alters an existing column, and never deletes data. Columns
in the database that the models no longer mention are reported and left alone.
"""
import os
import sys

import sqlalchemy as sa
from sqlalchemy.schema import CreateColumn


class UnsupportedChange(Exception):
    """A schema change that cannot be applied automatically and safely."""


def column_add_sql(table_name, column, dialect):
    """The ALTER statement that adds `column`, or raise UnsupportedChange.

    A column can be added to a table that already has rows only if existing
    rows can be given a value: either it accepts NULL, or the database can
    fill it from a server-side default. A Python-side default doesn't count —
    it only applies to rows this application inserts later.
    """
    if column.primary_key:
        raise UnsupportedChange(
            f'{table_name}.{column.name} is a primary key; '
            'a primary key cannot be added to an existing table')

    if column.nullable or column.server_default is not None:
        spec = CreateColumn(column).compile(dialect=dialect)
        return f'ALTER TABLE "{table_name}" ADD COLUMN {spec}'

    # NOT NULL with only a Python-side default — the style this project uses
    # (e.g. visibility = Column(String, nullable=False, default='public')).
    # SQLAlchemy applies that default to rows *it* inserts, so it does nothing
    # for rows already in the table. A plain scalar can go straight into the
    # DDL instead, which fills the existing rows as the column is added.
    default = column.default
    if default is not None and getattr(default, 'is_scalar', False):
        literal = sa.literal(default.arg).compile(
            dialect=dialect, compile_kwargs={'literal_binds': True})
        return (f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" '
                f'{column.type.compile(dialect)} NOT NULL DEFAULT {literal}')

    raise UnsupportedChange(
        f'{table_name}.{column.name} is NOT NULL and has no default a database '
        'can apply, so existing rows cannot be filled in')


def main():
    url = os.environ.get('DATABASE_URL', '').strip()
    where = url.rsplit('@', 1)[-1] if url else 'the app default (bundled SQLite)'
    print(f'[migrate] target: {where}')

    from app import app
    from models import db

    with app.app_context():
        engine = db.engine
        inspector = sa.inspect(engine)
        present = set(inspector.get_table_names())

        new_tables = [t.name for t in db.metadata.sorted_tables if t.name not in present]
        if new_tables:
            print(f'[migrate] creating tables: {", ".join(new_tables)}')
        db.create_all()

        # create_all() only ever adds whole tables; columns added to a table
        # that already exists have to be ALTERed in one at a time.
        statements, problems, unknown = [], [], []
        for table in db.metadata.sorted_tables:
            if table.name not in present:
                continue                      # just created, already current
            have = {c['name'] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in have:
                    continue
                try:
                    statements.append(column_add_sql(table.name, column, engine.dialect))
                except UnsupportedChange as exc:
                    problems.append(str(exc))
            unknown += [f'{table.name}.{name}' for name in
                        have - {c.name for c in table.columns}]

        if problems:
            print('[migrate] CANNOT APPLY:', file=sys.stderr)
            for p in problems:
                print(f'  - {p}', file=sys.stderr)
            print('[migrate] Write a migration for these by hand, then redeploy. '
                  'Nothing was changed by this step.', file=sys.stderr)
            sys.exit(1)

        for statement in statements:
            print(f'[migrate] {statement}')
            with engine.begin() as conn:
                conn.execute(sa.text(statement))

        if unknown:
            print(f'[migrate] note: columns in the database that the models no longer '
                  f'mention, left alone: {", ".join(sorted(unknown))}')

        changed = len(new_tables) + len(statements)
        print(f'[migrate] done — {changed} change(s).' if changed
              else '[migrate] database already up to date.')


if __name__ == '__main__':
    main()
