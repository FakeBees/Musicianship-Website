import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Tests must never run against the real dev database (instance/musicianship.db).
# app.py reads DATABASE_URL if set, so point it at an in-memory db before any
# test module does `from app import app`.
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
