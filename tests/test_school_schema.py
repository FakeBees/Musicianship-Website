import pytest
from app import app
from models import db, User, School, SchoolMembership, Class

@pytest.fixture(autouse=True)
def ctx():
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()

def test_school_has_join_code():
    s = School(name='Test School', join_code='ABC12345')
    db.session.add(s)
    db.session.commit()
    assert School.query.first().join_code == 'ABC12345'

def test_school_membership_model():
    s = School(name='S', join_code='XY123456')
    u = User(email='a@b.com', password_hash='x', role='student')
    db.session.add_all([s, u])
    db.session.flush()
    m = SchoolMembership(school_id=s.id, user_id=u.id, role='student')
    db.session.add(m)
    db.session.commit()
    assert SchoolMembership.query.first().role == 'student'

def test_class_assigned_teacher():
    s = School(name='S2', join_code='ZZ999999')
    t = User(email='t@b.com', password_hash='x', role='class_teacher')
    db.session.add_all([s, t])
    db.session.flush()
    c = Class(name='C', join_code='AAA111', teacher_id=t.id)
    c.assigned_teacher_id = t.id
    db.session.add(c)
    db.session.commit()
    assert Class.query.first().assigned_teacher.email == 't@b.com'
