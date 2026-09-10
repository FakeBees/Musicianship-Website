"""
reset_password.py
Set a new password for an existing account.

Run:  python reset_password.py [email]

Defaults to the admin account. Prompts for the password without echoing it, so
it never appears on screen, in your shell history, or in a transcript.
"""
import getpass
import sys

from werkzeug.security import check_password_hash, generate_password_hash

from app import app, db
from models import User

DEFAULT_EMAIL = 'jaredamron45@gmail.com'

# Match the hashes already in the database. Werkzeug's current default is
# scrypt, which this Python build has no support for (hashlib.scrypt is missing
# unless Python was linked against an OpenSSL that provides it), and every
# existing row was written as pbkdf2:sha256:1000000 anyway.
HASH_METHOD = 'pbkdf2:sha256:1000000'


def run(email):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f'No account found for {email}.')
            existing = [u.email for u in User.query.order_by(User.id).all()]
            print('Existing accounts: ' + (', '.join(existing) or '(none)'))
            return 1

        print(f'Resetting password for {user.email} '
              f'({user.display_name or "no display name"}, role={user.role}).')

        pw = getpass.getpass('New password: ')
        if not pw:
            print('Aborted — empty password.')
            return 1
        if pw != getpass.getpass('Confirm password: '):
            print('Aborted — passwords did not match.')
            return 1

        user.password_hash = generate_password_hash(pw, method=HASH_METHOD)
        db.session.commit()

        # Verify the round-trip before declaring success.
        if not check_password_hash(user.password_hash, pw):
            print('ERROR: the new hash does not verify. Password NOT usable.')
            return 1

        print('Password updated and verified. You can log in now.')
        return 0


if __name__ == '__main__':
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EMAIL))
