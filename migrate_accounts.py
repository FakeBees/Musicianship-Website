"""
migrate_accounts.py
One-off migration: create user/class tables, add user_id to attempt tables,
seed the admin account.

Run once: python migrate_accounts.py
"""
import os
from werkzeug.security import generate_password_hash
from app import app, db
from models import User

ADMIN_EMAIL    = 'jaredamron45@gmail.com'
ADMIN_PASSWORD = os.environ.get('MUSICIANSHIP_ADMIN_PASSWORD') or input('Admin password: ')
ADMIN_NAME     = 'Jared'


def run():
    with app.app_context():
        # 1. Create all new tables (User, Class, class_members)
        db.create_all()
        print('Tables created.')

        # 2. Add user_id columns to attempt tables (SQLite ADD COLUMN)
        conn = db.engine.raw_connection()
        cur  = conn.cursor()
        migrations = [
            'ALTER TABLE user_attempt     ADD COLUMN user_id INTEGER REFERENCES "user"(id)',
            'ALTER TABLE rhythm_attempt   ADD COLUMN user_id INTEGER REFERENCES "user"(id)',
            'ALTER TABLE harmonic_attempt ADD COLUMN user_id INTEGER REFERENCES "user"(id)',
            'ALTER TABLE holistic_attempt ADD COLUMN user_id INTEGER REFERENCES "user"(id)',
        ]
        for sql in migrations:
            try:
                cur.execute(sql)
                print(f'  OK: {sql[:70]}')
            except Exception as e:
                print(f'  SKIP (already exists?): {e}')
        conn.commit()
        conn.close()

        # 3. Seed admin user (idempotent)
        if not User.query.filter_by(email=ADMIN_EMAIL).first():
            admin = User(
                email         = ADMIN_EMAIL,
                password_hash = generate_password_hash(ADMIN_PASSWORD, method='pbkdf2:sha256'),
                display_name  = ADMIN_NAME,
                role          = 'admin',
            )
            db.session.add(admin)
            db.session.commit()
            print(f'Admin user created: {ADMIN_EMAIL}')
        else:
            print(f'Admin user already exists: {ADMIN_EMAIL}')

        print('Migration complete.')


if __name__ == '__main__':
    run()
