"""School-scoped authority.

Two rules under test:

  * Course/module editing is open to admin_teachers, but only for schools they
    actually administer. Before require_school_role() existed, any admin_teacher
    could rename or duplicate any school's course.
  * Membership changes follow "strictly below your own role" — which is what
    keeps 'only a site admin seats an admin_teacher' true, and what the removal
    rule is built on.
"""
import pytest

from app import app
from models import db, User, School, SchoolMembership, Course, Module, Section


@pytest.fixture(autouse=True)
def ctx():
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def user(role, email):
    u = User(email=email, password_hash='x', role=role)
    db.session.add(u)
    db.session.commit()
    return u


def school(name):
    s = School(name=name, join_code=name[:6].upper())
    db.session.add(s)
    db.session.commit()
    return s


def member(school, user, role):
    m = SchoolMembership(school_id=school.id, user_id=user.id, role=role)
    db.session.add(m)
    db.session.commit()
    return m


def course(school, name='C1'):
    c = Course(name=name, school_id=school.id)
    db.session.add(c)
    db.session.commit()
    return c


def client_for(u):
    app.config['TESTING'] = True
    c = app.test_client()
    with c.session_transaction() as s:
        s['_user_id'] = str(u.id)
        s['_fresh'] = True
    return c


# ── Requirement 2b: course editing, scoped to your own school ────────────────

def test_admin_teacher_can_manage_courses_in_their_own_school():
    s = school('Mine')
    at = user('admin_teacher', 'at@x.com')
    member(s, at, 'admin_teacher')
    c = client_for(at)
    assert c.get(f'/admin/schools/{s.id}/courses').status_code == 200
    assert c.post(f'/admin/schools/{s.id}/courses',
                  data={'name': 'New Course'}).status_code == 302
    assert Course.query.filter_by(name='New Course').first() is not None


def test_admin_teacher_cannot_touch_another_schools_courses():
    """This was an open privilege hole before require_school_role()."""
    mine, theirs = school('Mine'), school('Theirs')
    at = user('admin_teacher', 'at@x.com')
    member(mine, at, 'admin_teacher')
    other_course = course(theirs, 'Not Yours')
    c = client_for(at)

    assert c.get(f'/admin/schools/{theirs.id}/courses').status_code == 403
    assert c.post(f'/admin/courses/{other_course.id}/rename',
                  data={'name': 'Hijacked'}).status_code == 403
    assert c.post(f'/admin/courses/{other_course.id}/duplicate').status_code == 403
    assert c.post(f'/admin/courses/{other_course.id}/delete').status_code == 403
    assert c.get(f'/admin/courses/{other_course.id}/sections').status_code == 403
    db.session.refresh(other_course)
    assert other_course.name == 'Not Yours'


def test_module_editing_is_school_scoped_too():
    mine, theirs = school('Mine'), school('Theirs')
    at = user('admin_teacher', 'at@x.com')
    member(mine, at, 'admin_teacher')
    ok = course(mine)
    bad = course(theirs)
    c = client_for(at)
    assert c.get(f'/admin/courses/{ok.id}/modules').status_code == 200
    assert c.get(f'/admin/courses/{bad.id}/modules').status_code == 403


def test_site_admin_still_reaches_every_school():
    a = user('admin', 'a@x.com')
    s = school('Any')
    c = client_for(a)
    assert c.get(f'/admin/schools/{s.id}/courses').status_code == 200


# ── BUG-003: the admin_teacher nav link ──────────────────────────────────────

def test_admin_teacher_nav_link_no_longer_dead_ends_in_a_403():
    s = school('Mine')
    at = user('admin_teacher', 'at@x.com')
    member(s, at, 'admin_teacher')
    c = client_for(at)
    r = c.get('/admin/my-school')
    assert r.status_code == 302
    assert c.get(r.headers['Location'], follow_redirects=True).status_code == 200


# ── Requirement 1: only a site admin seats an admin_teacher ──────────────────

def test_admin_teacher_cannot_create_another_admin_teacher():
    s = school('Mine')
    at = user('admin_teacher', 'at@x.com')
    member(s, at, 'admin_teacher')
    target = user('student', 'new@x.com')
    c = client_for(at)
    c.post(f'/admin/schools/{s.id}/add-member',
           data={'email': 'new@x.com', 'role': 'admin_teacher'})
    assert SchoolMembership.query.filter_by(user_id=target.id).first() is None


def test_admin_teacher_can_seat_a_class_teacher():
    s = school('Mine')
    at = user('admin_teacher', 'at@x.com')
    member(s, at, 'admin_teacher')
    target = user('student', 'new@x.com')
    c = client_for(at)
    c.post(f'/admin/schools/{s.id}/add-member',
           data={'email': 'new@x.com', 'role': 'class_teacher'})
    mem = SchoolMembership.query.filter_by(user_id=target.id).first()
    assert mem is not None and mem.role == 'class_teacher'
    db.session.refresh(target)
    assert target.role == 'class_teacher'      # global role kept in step


def test_site_admin_can_seat_an_admin_teacher():
    s = school('Mine')
    a = user('admin', 'a@x.com')
    target = user('student', 'new@x.com')
    c = client_for(a)
    c.post(f'/admin/schools/{s.id}/add-member',
           data={'email': 'new@x.com', 'role': 'admin_teacher'})
    mem = SchoolMembership.query.filter_by(user_id=target.id).first()
    assert mem is not None and mem.role == 'admin_teacher'


def test_peer_cannot_re_role_a_peer():
    s = school('Mine')
    a1 = user('admin_teacher', 'a1@x.com'); member(s, a1, 'admin_teacher')
    a2 = user('admin_teacher', 'a2@x.com'); m2 = member(s, a2, 'admin_teacher')
    c = client_for(a1)
    c.post(f'/admin/schools/{s.id}/set-member-role',
           data={'user_id': a2.id, 'role': 'student'})
    db.session.refresh(m2)
    assert m2.role == 'admin_teacher'


# ── Removal: strictly below your own role ────────────────────────────────────

def test_class_teacher_can_remove_a_student():
    s = school('Mine')
    ct = user('class_teacher', 'ct@x.com'); member(s, ct, 'class_teacher')
    stu = user('student', 'stu@x.com');     member(s, stu, 'student')
    c = client_for(ct)
    c.post(f'/admin/schools/{s.id}/remove-member', data={'user_id': stu.id})
    assert SchoolMembership.query.filter_by(user_id=stu.id).first() is None


def test_class_teacher_cannot_remove_an_admin_teacher():
    s = school('Mine')
    ct = user('class_teacher', 'ct@x.com'); member(s, ct, 'class_teacher')
    at = user('admin_teacher', 'at@x.com'); member(s, at, 'admin_teacher')
    c = client_for(ct)
    c.post(f'/admin/schools/{s.id}/remove-member', data={'user_id': at.id})
    assert SchoolMembership.query.filter_by(user_id=at.id).first() is not None


def test_a_student_can_remove_nobody():
    s = school('Mine')
    stu1 = user('student', 's1@x.com'); member(s, stu1, 'student')
    stu2 = user('student', 's2@x.com'); member(s, stu2, 'student')
    c = client_for(stu1)
    r = c.post(f'/admin/schools/{s.id}/remove-member', data={'user_id': stu2.id})
    assert r.status_code == 403
    assert SchoolMembership.query.filter_by(user_id=stu2.id).first() is not None


def test_removal_also_drops_the_person_from_that_schools_sections():
    s = school('Mine')
    crs = course(s)
    at = user('admin_teacher', 'at@x.com'); member(s, at, 'admin_teacher')
    stu = user('student', 'stu@x.com');     member(s, stu, 'student')
    sec = Section(name='S1', join_code='S1CODE', teacher_id=at.id, course_id=crs.id)
    sec.members.append(stu)
    db.session.add(sec)
    db.session.commit()

    client_for(at).post(f'/admin/schools/{s.id}/remove-member', data={'user_id': stu.id})
    db.session.refresh(sec)
    assert stu not in sec.members


def test_removal_refuses_when_the_person_still_owns_sections():
    """A section's teacher_id is not nullable — refuse rather than cascade."""
    s = school('Mine')
    crs = course(s)
    a = user('admin', 'a@x.com')
    at = user('admin_teacher', 'at@x.com'); member(s, at, 'admin_teacher')
    sec = Section(name='Owned', join_code='OWNED1', teacher_id=at.id, course_id=crs.id)
    db.session.add(sec)
    db.session.commit()

    client_for(a).post(f'/admin/schools/{s.id}/remove-member', data={'user_id': at.id})
    assert SchoolMembership.query.filter_by(user_id=at.id).first() is not None


def test_removing_last_staff_membership_demotes_the_global_role():
    s = school('Mine')
    a = user('admin', 'a@x.com')
    ct = user('class_teacher', 'ct@x.com'); member(s, ct, 'class_teacher')
    client_for(a).post(f'/admin/schools/{s.id}/remove-member', data={'user_id': ct.id})
    db.session.refresh(ct)
    assert ct.role == 'student'


def test_a_site_admin_is_never_demoted_by_school_changes():
    s = school('Mine')
    a = user('admin', 'a@x.com')
    other = user('admin', 'a2@x.com'); member(s, other, 'student')
    client_for(a).post(f'/admin/schools/{s.id}/remove-member', data={'user_id': other.id})
    db.session.refresh(other)
    assert other.role == 'admin'


# ── Requirement 2a: assigning section teachers ───────────────────────────────

def test_school_admin_can_assign_a_teacher_to_a_section_they_do_not_own():
    """The old check was `section.teacher_id != current_user.id`, so a school
    admin could not assign teachers to sections owned by someone else."""
    s = school('Mine')
    crs = course(s)
    owner = user('admin_teacher', 'owner@x.com');  member(s, owner, 'admin_teacher')
    boss  = user('admin_teacher', 'boss@x.com');   member(s, boss, 'admin_teacher')
    ct    = user('class_teacher', 'ct@x.com');     member(s, ct, 'class_teacher')
    sec = Section(name='S1', join_code='S1CODE', teacher_id=owner.id, course_id=crs.id)
    db.session.add(sec)
    db.session.commit()

    client_for(boss).post(f'/teacher/sections/{sec.id}/assign-teacher',
                          data={'email': ct.email})
    db.session.refresh(sec)
    assert sec.assigned_teacher_id == ct.id


def test_cannot_assign_a_teacher_from_another_school():
    mine, theirs = school('Mine'), school('Theirs')
    crs = course(mine)
    at = user('admin_teacher', 'at@x.com'); member(mine, at, 'admin_teacher')
    outsider = user('class_teacher', 'out@x.com'); member(theirs, outsider, 'class_teacher')
    sec = Section(name='S1', join_code='S1CODE', teacher_id=at.id, course_id=crs.id)
    db.session.add(sec)
    db.session.commit()

    client_for(at).post(f'/teacher/sections/{sec.id}/assign-teacher',
                        data={'email': outsider.email})
    db.session.refresh(sec)
    assert sec.assigned_teacher_id is None


def test_an_admin_teacher_may_be_assigned_as_a_section_teacher():
    """"Teacher or higher" — an admin_teacher is a valid assignee."""
    s = school('Mine')
    crs = course(s)
    at    = user('admin_teacher', 'at@x.com');   member(s, at, 'admin_teacher')
    other = user('admin_teacher', 'at2@x.com');  member(s, other, 'admin_teacher')
    sec = Section(name='S1', join_code='S1CODE', teacher_id=at.id, course_id=crs.id)
    db.session.add(sec)
    db.session.commit()

    client_for(at).post(f'/teacher/sections/{sec.id}/assign-teacher',
                        data={'email': other.email})
    db.session.refresh(sec)
    assert sec.assigned_teacher_id == other.id


# ── Assigning by email ───────────────────────────────────────────────────────

def _school_with_section():
    s = school('Mine')
    crs = course(s)
    at = user('admin_teacher', 'at@x.com'); member(s, at, 'admin_teacher')
    sec = Section(name='S1', join_code='S1CODE', teacher_id=at.id, course_id=crs.id)
    db.session.add(sec)
    db.session.commit()
    return s, sec, at


def test_assign_by_email_is_case_and_space_insensitive():
    s, sec, at = _school_with_section()
    ct = user('class_teacher', 'Mixed.Case@X.com'); member(s, ct, 'class_teacher')
    client_for(at).post(f'/teacher/sections/{sec.id}/assign-teacher',
                        data={'email': '  mixed.case@x.COM  '})
    db.session.refresh(sec)
    assert sec.assigned_teacher_id == ct.id


def test_assign_rejects_an_unknown_email():
    s, sec, at = _school_with_section()
    r = client_for(at).post(f'/teacher/sections/{sec.id}/assign-teacher',
                            data={'email': 'nobody@x.com'}, follow_redirects=True)
    assert b'No account found' in r.data
    db.session.refresh(sec)
    assert sec.assigned_teacher_id is None


def test_assign_says_so_when_the_person_is_not_in_the_school():
    s, sec, at = _school_with_section()
    outsider = user('class_teacher', 'out@x.com')      # no membership anywhere
    r = client_for(at).post(f'/teacher/sections/{sec.id}/assign-teacher',
                            data={'email': outsider.email}, follow_redirects=True)
    assert b'not a member of' in r.data


def test_assign_says_so_when_the_member_is_only_a_student():
    s, sec, at = _school_with_section()
    stu = user('student', 'stu@x.com'); member(s, stu, 'student')
    r = client_for(at).post(f'/teacher/sections/{sec.id}/assign-teacher',
                            data={'email': stu.email}, follow_redirects=True)
    assert b'not a teacher' in r.data
    db.session.refresh(sec)
    assert sec.assigned_teacher_id is None


def test_assign_can_be_cleared():
    s, sec, at = _school_with_section()
    ct = user('class_teacher', 'ct@x.com'); member(s, ct, 'class_teacher')
    c = client_for(at)
    c.post(f'/teacher/sections/{sec.id}/assign-teacher', data={'email': ct.email})
    db.session.refresh(sec)
    assert sec.assigned_teacher_id == ct.id
    c.post(f'/teacher/sections/{sec.id}/assign-teacher', data={'clear': '1'})
    db.session.refresh(sec)
    assert sec.assigned_teacher_id is None


# ── Appointing a school administrator by email ───────────────────────────────

def test_site_admin_appoints_a_school_admin_by_email_for_a_non_member():
    s = school('Mine')
    a = user('admin', 'a@x.com')
    target = user('student', 'new@x.com')
    client_for(a).post(f'/admin/schools/{s.id}/set-admin',
                       data={'email': 'NEW@x.com'})
    mem = SchoolMembership.query.filter_by(school_id=s.id, user_id=target.id).first()
    assert mem is not None and mem.role == 'admin_teacher'
    db.session.refresh(target)
    assert target.role == 'admin_teacher'


def test_site_admin_promotes_an_existing_member_to_school_admin():
    s = school('Mine')
    a = user('admin', 'a@x.com')
    ct = user('class_teacher', 'ct@x.com'); m = member(s, ct, 'class_teacher')
    client_for(a).post(f'/admin/schools/{s.id}/set-admin', data={'email': ct.email})
    db.session.refresh(m)
    assert m.role == 'admin_teacher'


def test_an_admin_teacher_cannot_appoint_another_school_admin():
    s = school('Mine')
    at = user('admin_teacher', 'at@x.com'); member(s, at, 'admin_teacher')
    target = user('student', 'new@x.com')
    r = client_for(at).post(f'/admin/schools/{s.id}/set-admin',
                            data={'email': target.email}, follow_redirects=True)
    assert b'Only a site admin' in r.data
    assert SchoolMembership.query.filter_by(user_id=target.id).first() is None


def test_appointing_an_unknown_email_reports_it():
    s = school('Mine')
    a = user('admin', 'a@x.com')
    r = client_for(a).post(f'/admin/schools/{s.id}/set-admin',
                           data={'email': 'ghost@x.com'}, follow_redirects=True)
    assert b'No account found' in r.data


def test_school_page_lists_current_administrative_teachers():
    s = school('Mine')
    a = user('admin', 'a@x.com')
    at = user('admin_teacher', 'at@x.com'); member(s, at, 'admin_teacher')
    body = client_for(a).get(f'/admin/schools/{s.id}/detail').get_data(as_text=True)
    assert 'Administrative teachers' in body
    assert 'at@x.com' in body


# ── Requirement 2c: section creation scoped to your own courses ──────────────

def test_cannot_create_a_section_against_another_schools_course():
    mine, theirs = school('Mine'), school('Theirs')
    at = user('admin_teacher', 'at@x.com'); member(mine, at, 'admin_teacher')
    foreign = course(theirs, 'Foreign')
    client_for(at).post('/teacher/section/new',
                        data={'name': 'S1', 'course_id': foreign.id})
    assert Section.query.filter_by(name='S1').first() is None


def test_admin_teacher_with_no_school_cannot_create_a_section():
    """@role_required only asks "an admin_teacher anywhere?". Without a school
    to put it in, the section would answer to nobody but its creator."""
    rogue = user('admin_teacher', 'rogue@x.com')   # no SchoolMembership at all
    c = client_for(rogue)
    assert c.get('/teacher/section/new').status_code == 302
    c.post('/teacher/section/new', data={'name': 'Ghost'})
    assert Section.query.filter_by(name='Ghost').first() is None


def test_that_also_holds_when_no_course_is_submitted():
    """The course check only fired when a course_id was present, so an empty
    submission slipped past it entirely."""
    s = school('Mine')
    rogue = user('admin_teacher', 'rogue@x.com')
    member(s, rogue, 'class_teacher')      # a member, but not an ADMIN of it
    c = client_for(rogue)
    c.post('/teacher/section/new', data={'name': 'Ghost', 'course_id': ''})
    assert Section.query.filter_by(name='Ghost').first() is None


def test_new_section_button_hidden_when_you_administer_nothing():
    rogue = user('admin_teacher', 'rogue@x.com')
    body = client_for(rogue).get('/teacher').get_data(as_text=True)
    assert '/teacher/section/new' not in body


# ── Everyone can reach the join / enrolled view ──────────────────────────────

@pytest.mark.parametrize('role', ['student', 'class_teacher', 'admin_teacher', 'admin'])
def test_every_role_can_open_my_sections_and_join(role):
    u = user(role, f'{role}@x.com')
    c = client_for(u)
    page = c.get('/my-sections')
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert 'Join a school' in body
    assert '/section/join' in body


@pytest.mark.parametrize('role', ['class_teacher', 'admin_teacher', 'admin'])
def test_staff_nav_links_to_my_sections_as_well_as_the_teaching_dashboard(role):
    u = user(role, f'{role}@x.com')
    body = client_for(u).get('/').get_data(as_text=True)
    assert '/my-sections' in body
    assert 'I Teach' in body


def test_enrolled_sections_actually_render():
    """The template read `classes` while the route passed `sections`, so this
    list silently showed the empty state for everyone."""
    s = school('Mine')
    crs = course(s)
    owner = user('admin_teacher', 'o@x.com')
    stu = user('student', 'stu@x.com')
    sec = Section(name='Enrolled Here', join_code='ENR1', teacher_id=owner.id,
                  course_id=crs.id)
    sec.members.append(stu)
    db.session.add(sec)
    db.session.commit()
    body = client_for(stu).get('/my-sections').get_data(as_text=True)
    assert 'Enrolled Here' in body
    assert 'not enrolled in any' not in body


def test_a_teacher_can_join_a_school_by_code():
    s = school('Mine')
    t = user('class_teacher', 't@x.com')
    c = client_for(t)
    c.post('/join-school', data={'school_code': s.join_code})
    mem = SchoolMembership.query.filter_by(user_id=t.id, school_id=s.id).first()
    assert mem is not None and mem.role == 'student'
    db.session.refresh(t)
    assert t.role == 'class_teacher'   # joining by code must not demote them


def test_can_create_a_section_against_your_own_course():
    s = school('Mine')
    at = user('admin_teacher', 'at@x.com'); member(s, at, 'admin_teacher')
    crs = course(s)
    client_for(at).post('/teacher/section/new',
                        data={'name': 'S1', 'course_id': crs.id})
    sec = Section.query.filter_by(name='S1').first()
    assert sec is not None and sec.course_id == crs.id


# ── The shared-curriculum bug ────────────────────────────────────────────────

def test_adding_an_exercise_affects_only_this_section():
    """It used to write a ModuleExercise onto the shared course module, which
    changed the curriculum for every other section using that course."""
    from models import ModuleExercise, SectionModuleExercise
    s = school('Mine')
    crs = course(s)
    mod = Module(name='M1', course_id=crs.id, order=0)
    db.session.add(mod)
    db.session.commit()
    at = user('admin_teacher', 'at@x.com'); member(s, at, 'admin_teacher')
    sec = Section(name='S1', join_code='S1CODE', teacher_id=at.id, course_id=crs.id)
    db.session.add(sec)
    db.session.commit()

    before = ModuleExercise.query.count()
    client_for(at).post(f'/teacher/sections/{sec.id}/module_exercises/add',
                        data={'module_id': mod.id, 'exercise_type': 'melody',
                              'exercise_id': 1, 'name': 'X'})
    assert ModuleExercise.query.count() == before          # course untouched
    override = SectionModuleExercise.query.filter_by(section_id=sec.id).first()
    assert override is not None and override.action == 'add'


# ── Requirement 3: join codes ────────────────────────────────────────────────

def test_section_teacher_sees_both_join_codes_but_cannot_regenerate():
    """D27, superseding the old 'but not the school's' behaviour this test
    used to assert: a Section Teacher needs the school code too, since new
    students use it before the section code. Regenerate stays out of reach —
    that's still School-Admin-and-above.

    NOTE (task-1, D27): this test previously asserted the opposite —
    `s.join_code.encode() not in page.data` — which was the literal bug D27
    fixes. The two are mutually exclusive, so fixing D27 required updating
    this one assertion; see task-1-report.md for the full justification.
    Every other test in this file is untouched.
    """
    s = school('Mine')
    crs = course(s)
    at = user('admin_teacher', 'at@x.com'); member(s, at, 'admin_teacher')
    ct = user('class_teacher', 'ct@x.com'); member(s, ct, 'class_teacher')
    sec = Section(name='S1', join_code='SECCODE', teacher_id=at.id,
                  assigned_teacher_id=ct.id, course_id=crs.id)
    db.session.add(sec)
    db.session.commit()

    c = client_for(ct)
    assert b'SECCODE' in c.get(f'/teacher/section/{sec.id}').data
    # They can reach the school page (to remove students) and now also see
    # its join code — but may not regenerate it.
    page = c.get(f'/admin/schools/{s.id}/detail')
    assert page.status_code == 200
    assert s.join_code.encode() in page.data
    assert b'Regenerate' not in page.data


def test_school_admin_sees_the_school_join_code():
    s = school('Mine')
    at = user('admin_teacher', 'at@x.com'); member(s, at, 'admin_teacher')
    page = client_for(at).get(f'/admin/schools/{s.id}/detail')
    assert s.join_code.encode() in page.data


# ── D11: school-admin authority over sections they do not own ───────────────

def test_school_admin_can_open_a_section_they_do_not_own():
    """D11: a school admin could delete a section but not view its roster.

    teacher_delete_section already used require_manage_section (school-aware)
    while teacher_section_detail used require_section_role (section-only), so
    destructive power was granted where read access was denied.
    """
    s = school('Mine')
    crs = course(s)
    owner = user('admin_teacher', 'owner@x.com'); member(s, owner, 'admin_teacher')
    boss  = user('admin_teacher', 'boss@x.com');  member(s, boss,  'admin_teacher')
    sec = Section(name='S1', join_code='SEC1', teacher_id=owner.id, course_id=crs.id)
    db.session.add(sec); db.session.commit()

    c = client_for(boss)                      # administers the school, owns nothing
    assert c.get(f'/teacher/section/{sec.id}').status_code == 200


def test_assigned_class_teacher_keeps_section_access():
    """Guard against the obvious wrong fix: swapping to require_manage_section
    would demand admin_teacher-level and lock this person out."""
    s = school('Mine')
    crs = course(s)
    at = user('admin_teacher', 'at2@x.com'); member(s, at, 'admin_teacher')
    ct = user('class_teacher', 'ct2@x.com'); member(s, ct, 'class_teacher')
    sec = Section(name='S2', join_code='SEC2', teacher_id=at.id,
                  assigned_teacher_id=ct.id, course_id=crs.id)
    db.session.add(sec); db.session.commit()

    assert client_for(ct).get(f'/teacher/section/{sec.id}').status_code == 200


def test_school_admin_of_another_school_still_cannot_open_the_section():
    """The new authority is scoped to the section's own school."""
    mine, theirs = school('Mine'), school('Theirs')
    crs = course(mine)
    owner    = user('admin_teacher', 'owner2@x.com'); member(mine,   owner,    'admin_teacher')
    outsider = user('admin_teacher', 'out@x.com');    member(theirs, outsider, 'admin_teacher')
    sec = Section(name='S3', join_code='SEC3', teacher_id=owner.id, course_id=crs.id)
    db.session.add(sec); db.session.commit()

    assert client_for(outsider).get(f'/teacher/section/{sec.id}').status_code == 403


# ── D11: school-admin authority extends to the other swapped routes too ─────
#
# Only teacher_section_detail got direct coverage above. These three cover
# three more of the six other routes that switched from require_section_role
# to require_section_authority, proving each one's school branch is actually
# wired up and not just present in section_authority() unused.

def test_school_admin_can_edit_a_section_they_do_not_own():
    s = school('Mine')
    crs = course(s)
    owner = user('admin_teacher', 'owner6@x.com'); member(s, owner, 'admin_teacher')
    boss  = user('admin_teacher', 'boss6@x.com');  member(s, boss,  'admin_teacher')
    sec = Section(name='S6', join_code='SEC6', teacher_id=owner.id, course_id=crs.id)
    db.session.add(sec); db.session.commit()

    c = client_for(boss)                      # administers the school, owns nothing
    assert c.get(f'/teacher/section/{sec.id}/edit').status_code != 403


def test_school_admin_can_hide_a_module_on_a_section_they_do_not_own():
    s = school('Mine')
    crs = course(s)
    mod = Module(name='M1', course_id=crs.id, order=0)
    db.session.add(mod); db.session.commit()
    owner = user('admin_teacher', 'owner7@x.com'); member(s, owner, 'admin_teacher')
    boss  = user('admin_teacher', 'boss7@x.com');  member(s, boss,  'admin_teacher')
    sec = Section(name='S7', join_code='SEC7', teacher_id=owner.id, course_id=crs.id)
    db.session.add(sec); db.session.commit()

    c = client_for(boss)
    assert c.post(f'/teacher/sections/{sec.id}/modules/{mod.id}/hide').status_code != 403


def test_school_admin_can_restore_a_module_on_a_section_they_do_not_own():
    s = school('Mine')
    crs = course(s)
    owner = user('admin_teacher', 'owner8@x.com'); member(s, owner, 'admin_teacher')
    boss  = user('admin_teacher', 'boss8@x.com');  member(s, boss,  'admin_teacher')
    sec = Section(name='S8', join_code='SEC8', teacher_id=owner.id, course_id=crs.id)
    db.session.add(sec); db.session.commit()

    c = client_for(boss)
    assert c.post(f'/teacher/sections/{sec.id}/modules/999/restore').status_code != 403


# ── D14: a non-manager saving Section Settings must not wipe the course ─────

def test_section_teacher_saving_settings_does_not_wipe_the_course():
    """Only a manager (owner or School Admin of the section's school) may
    change course_id. A Section Teacher's POST must leave it exactly as it
    was, no matter what the form sends."""
    s = school('Mine')
    crs = course(s)
    at = user('admin_teacher', 'at9@x.com'); member(s, at, 'admin_teacher')
    ct = user('class_teacher', 'ct9@x.com'); member(s, ct, 'class_teacher')
    sec = Section(name='Orig Name', join_code='SEC9A', teacher_id=at.id,
                  assigned_teacher_id=ct.id, course_id=crs.id)
    db.session.add(sec)
    db.session.commit()

    client_for(ct).post(f'/teacher/section/{sec.id}/edit',
                        data={'name': 'Renamed', 'course_id': ''})
    db.session.refresh(sec)
    assert sec.name == 'Renamed'
    assert sec.course_id == crs.id, \
        'a Section Teacher (non-manager) must not be able to clear the course'


def test_manager_can_still_change_and_clear_the_course():
    s = school('Mine')
    crs1 = course(s, 'C1')
    crs2 = course(s, 'C2')
    at = user('admin_teacher', 'at9b@x.com'); member(s, at, 'admin_teacher')
    sec = Section(name='Orig', join_code='SEC9B', teacher_id=at.id, course_id=crs1.id)
    db.session.add(sec)
    db.session.commit()

    c = client_for(at)
    c.post(f'/teacher/section/{sec.id}/edit', data={'name': 'Orig', 'course_id': crs2.id})
    db.session.refresh(sec)
    assert sec.course_id == crs2.id, 'a manager must still be able to change the course'

    c.post(f'/teacher/section/{sec.id}/edit', data={'name': 'Orig', 'course_id': ''})
    db.session.refresh(sec)
    assert sec.course_id is None, 'a manager must still be able to clear the course'


# ── D26: a newly created school gets a join code ─────────────────────────────

def test_new_school_gets_a_non_empty_join_code():
    a = user('admin', 'a10@x.com')
    client_for(a).post('/admin/schools', data={'name': 'Brand New School'})
    s = School.query.filter_by(name='Brand New School').first()
    assert s is not None
    assert s.join_code, 'a newly created school must have a join code'


# ── D27: the school join code also appears on a section's roster page ───────

def test_roster_page_shows_the_school_code_next_to_the_section_code():
    s = school('Mine')
    crs = course(s)
    at = user('admin_teacher', 'at11@x.com'); member(s, at, 'admin_teacher')
    ct = user('class_teacher', 'ct11@x.com'); member(s, ct, 'class_teacher')
    sec = Section(name='S11', join_code='SEC11', teacher_id=at.id,
                  assigned_teacher_id=ct.id, course_id=crs.id)
    db.session.add(sec)
    db.session.commit()

    page = client_for(ct).get(f'/teacher/section/{sec.id}')
    assert page.status_code == 200
    assert b'SEC11' in page.data
    assert s.join_code.encode() in page.data, \
        'the roster page must also show the school join code (D27)'


def test_roster_page_has_no_school_code_when_the_section_has_no_course():
    """'Belongs to a school' means the section has a course — a section
    reaches its school only through its course (resolved ambiguity #2)."""
    at = user('admin_teacher', 'at11b@x.com')
    sec = Section(name='NoSchool', join_code='NOSCH11', teacher_id=at.id)
    db.session.add(sec)
    db.session.commit()

    page = client_for(at).get(f'/teacher/section/{sec.id}')
    assert page.status_code == 200
    assert b'NOSCH11' in page.data
