import pytest
from app import app
from models import db, User


@pytest.fixture(autouse=True)
def ctx():
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def _make_user(role):
    u = User(email=f'{role}@test.com',
             password_hash='x',
             role=role)
    db.session.add(u)
    db.session.commit()
    return u


def test_admin_teacher_can_access_teacher_dashboard():
    with app.test_client() as c:
        u = _make_user('admin_teacher')
        with c.session_transaction() as sess:
            sess['_user_id'] = str(u.id)
            sess['_fresh'] = True
        resp = c.get('/teacher', follow_redirects=False)
        assert resp.status_code == 200
