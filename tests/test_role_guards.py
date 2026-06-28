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


@pytest.fixture
def admin_teacher_user():
    u = User(
        email='admin_teacher@test.com',
        password_hash='x',
        role='admin_teacher',
    )
    db.session.add(u)
    db.session.commit()
    return u


def test_admin_teacher_can_access_teacher_dashboard(admin_teacher_user):
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['_user_id'] = str(admin_teacher_user.id)
            sess['_fresh'] = True
        resp = c.get('/teacher', follow_redirects=False)
        assert resp.status_code == 200


def test_plain_teacher_role_cannot_access_teacher_dashboard():
    u = User(
        email='old_teacher@test.com',
        password_hash='x',
        role='teacher',
    )
    db.session.add(u)
    db.session.commit()
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['_user_id'] = str(u.id)
            sess['_fresh'] = True
        resp = c.get('/teacher', follow_redirects=False)
        assert resp.status_code == 403
