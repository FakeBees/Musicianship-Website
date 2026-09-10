from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import json

db = SQLAlchemy()

# Association table for many-to-many Melody <-> Tag
melody_tags = db.Table(
    'melody_tags',
    db.Column('melody_id', db.Integer, db.ForeignKey('melody.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True),
)

# Association table for many-to-many Rhythm <-> Tag
rhythm_tags = db.Table(
    'rhythm_tags',
    db.Column('rhythm_id', db.Integer, db.ForeignKey('rhythm.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True),
)


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))

    def __repr__(self):
        return f'<Tag {self.name}>'


class Melody(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300))
    midi_filename = db.Column(db.String(200), nullable=False)
    source_key = db.Column(db.String(100), nullable=True)
    # JSON array of {key, duration[, dotted]} objects using VexFlow notation
    notes_json = db.Column(db.Text, nullable=False)
    time_signature = db.Column(db.String(10), default='4/4')
    key_signature = db.Column(db.String(10), default='C')
    clef = db.Column(db.String(10), default='treble')
    # Shortest note value used: 'h', 'q', '8', '16'
    min_duration = db.Column(db.String(5), default='q')
    difficulty = db.Column(db.Integer, default=1)  # 1–5
    visibility = db.Column(db.String(20), nullable=False, default='public')
    school_id  = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=True)
    tempo = db.Column(db.Integer, default=120)
    public_id         = db.Column(db.String(12), unique=True, nullable=True, index=True)
    container_id      = db.Column(db.Integer, db.ForeignKey('container.id'), nullable=True)
    generation_params = db.Column(db.Text, nullable=True)
    tags = db.relationship('Tag', secondary=melody_tags, backref='melodies', lazy='subquery')

    @property
    def notes(self):
        return json.loads(self.notes_json)

    @property
    def total_beats(self):
        """Total duration in quarter-note beat units (works for all time signatures)."""
        beat_map = {'w': 4, 'h': 2, 'q': 1, '8': 0.5, '16': 0.25}
        total = 0.0
        for n in self.notes:
            base = beat_map.get(n['duration'].rstrip('r'), 1)
            total += base * 1.5 if n.get('dotted') else base
        return total

    @property
    def num_measures(self):
        """Measure count, correct for both simple and compound meters."""
        numerator   = int(self.time_signature.split('/')[0])
        denominator = int(self.time_signature.split('/')[1])
        beats_per_measure = numerator * (4.0 / denominator)  # in quarter-note units
        return max(1, int(self.total_beats / beats_per_measure + 0.9999))

    def __repr__(self):
        return f'<Melody {self.name}>'


class UserAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    melody_id = db.Column(db.Integer, db.ForeignKey('melody.id'), nullable=False)
    melody = db.relationship('Melody', backref='attempts')
    user_notes_json = db.Column(db.Text, nullable=False, default='[]')
    pitch_accuracy = db.Column(db.Float, default=0.0)
    duration_accuracy = db.Column(db.Float, default=0.0)
    overall_score = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user    = db.relationship('User', backref='melody_attempts')

    @property
    def user_notes(self):
        return json.loads(self.user_notes_json)

    def __repr__(self):
        return f'<UserAttempt melody={self.melody_id} score={self.overall_score:.1f}>'


class Rhythm(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300))
    source_key = db.Column(db.String(100), nullable=True)
    # JSON array of {duration[, dotted]} objects — no pitch
    notes_json = db.Column(db.Text, nullable=False)
    time_signature = db.Column(db.String(10), default='4/4')
    min_duration = db.Column(db.String(5), default='q')
    difficulty = db.Column(db.Integer, default=1)  # 1–5
    visibility = db.Column(db.String(20), nullable=False, default='public')
    school_id  = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=True)
    tempo = db.Column(db.Integer, default=100)
    tags = db.relationship('Tag', secondary=rhythm_tags, backref='rhythms', lazy='subquery')
    public_id = db.Column(db.String(12), unique=True, nullable=True, index=True)

    @property
    def notes(self):
        return json.loads(self.notes_json)

    @property
    def total_beats(self):
        beat_map = {'w': 4, 'h': 2, 'q': 1, '8': 0.5, '16': 0.25}
        total = 0.0
        for n in self.notes:
            base = beat_map.get(n['duration'].rstrip('r'), 1)
            total += base * 1.5 if n.get('dotted') else base
        return total

    @property
    def num_measures(self):
        numerator   = int(self.time_signature.split('/')[0])
        denominator = int(self.time_signature.split('/')[1])
        beats_per_measure = numerator * (4.0 / denominator)
        return max(1, int(self.total_beats / beats_per_measure + 0.9999))

    def __repr__(self):
        return f'<Rhythm {self.name}>'


class RhythmAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rhythm_id = db.Column(db.Integer, db.ForeignKey('rhythm.id'), nullable=False)
    rhythm = db.relationship('Rhythm', backref='attempts')
    user_notes_json = db.Column(db.Text, nullable=False, default='[]')
    duration_accuracy = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user    = db.relationship('User', backref='rhythm_attempts')

    @property
    def user_notes(self):
        return json.loads(self.user_notes_json)

    def __repr__(self):
        return f'<RhythmAttempt rhythm={self.rhythm_id} score={self.duration_accuracy:.1f}>'


# Association table for many-to-many ChordProgression <-> Tag
progression_tags = db.Table(
    'progression_tags',
    db.Column('progression_id', db.Integer, db.ForeignKey('chord_progression.id'), primary_key=True),
    db.Column('tag_id',         db.Integer, db.ForeignKey('tag.id'),               primary_key=True),
)


class ChordProgression(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    description   = db.Column(db.String(300))
    midi_filename = db.Column(db.String(200), nullable=False)
    source_key    = db.Column(db.String(100), nullable=True)
    key_signature = db.Column(db.String(10), default='C')
    tempo         = db.Column(db.Integer, default=80)
    difficulty    = db.Column(db.Integer, default=1)
    visibility = db.Column(db.String(20), nullable=False, default='public')
    school_id  = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=True)
    category      = db.Column(db.String(30), default='diatonic')
    chords_json   = db.Column(db.Text, nullable=False)
    tags          = db.relationship('Tag', secondary=progression_tags,
                                    backref='progressions', lazy='subquery')
    public_id = db.Column(db.String(12), unique=True, nullable=True, index=True)

    @property
    def chords(self):
        return json.loads(self.chords_json)

    def __repr__(self):
        return f'<ChordProgression {self.name}>'


# Association table for many-to-many HolisticExercise <-> Tag
holistic_tags = db.Table(
    'holistic_tags',
    db.Column('exercise_id', db.Integer, db.ForeignKey('holistic_exercise.id'), primary_key=True),
    db.Column('tag_id',      db.Integer, db.ForeignKey('tag.id'),               primary_key=True),
)


class HolisticExercise(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(100), nullable=False)
    description    = db.Column(db.String(300))

    # Path to the exercise folder, relative to static/
    # e.g. "holistic/waltz_c_major/"
    folder         = db.Column(db.String(200), nullable=False)

    # WAV filename within the folder, e.g. "audio.wav"
    wav_filename   = db.Column(db.String(100), nullable=False, default='audio.wav')
    source_key     = db.Column(db.String(100), nullable=True)

    key_signature  = db.Column(db.String(10),  default='C')
    time_signature = db.Column(db.String(10),  default='4/4')
    tempo          = db.Column(db.Integer,     default=120)
    difficulty     = db.Column(db.Integer,     default=1)   # 1-5
    visibility = db.Column(db.String(20), nullable=False, default='public')
    school_id  = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=True)
    is_major       = db.Column(db.Boolean,     default=True)  # True=major, False=minor

    tags = db.relationship('Tag', secondary=holistic_tags,
                           backref='holistic_exercises', lazy='subquery')
    public_id = db.Column(db.String(12), unique=True, nullable=True, index=True)

    @property
    def wav_url_path(self):
        """Relative URL path for the WAV file, suitable for url_for('static', ...)."""
        return self.folder.rstrip('/') + '/' + self.wav_filename

    @property
    def total_beats(self):
        beat_map = {'w': 4, 'h': 2, 'q': 1, '8': 0.5, '16': 0.25}
        max_total = 0.0
        for line in self.lines:
            if line.line_type not in ('melody', 'rhythm'):
                continue
            total = 0.0
            for n in line.content:
                base = beat_map.get(n['duration'].rstrip('r'), 1)
                total += base * 1.5 if n.get('dotted') else base
            max_total = max(max_total, total)
        return max_total

    @property
    def num_measures(self):
        numerator   = int(self.time_signature.split('/')[0])
        denominator = int(self.time_signature.split('/')[1])
        beats_per_measure = numerator * (4.0 / denominator)
        return max(1, int(self.total_beats / beats_per_measure + 0.9999))

    def __repr__(self):
        return '<HolisticExercise {}>'.format(self.name)


class HolisticLine(db.Model):
    id                    = db.Column(db.Integer, primary_key=True)
    holistic_exercise_id  = db.Column(db.Integer, db.ForeignKey('holistic_exercise.id'), nullable=False)
    line_type             = db.Column(db.String(10), nullable=False)   # 'melody' | 'rhythm' | 'harmonic'
    name                  = db.Column(db.String(100), nullable=False)
    order                 = db.Column(db.Integer, nullable=False, default=0)
    clef                  = db.Column(db.String(10), nullable=True)    # melody only
    midi_filename         = db.Column(db.String(200), nullable=False, default='')
    content_json          = db.Column(db.Text, nullable=False, default='[]')

    exercise = db.relationship('HolisticExercise', backref=db.backref(
        'lines', order_by='HolisticLine.order', cascade='all, delete-orphan'))

    @property
    def content(self):
        return json.loads(self.content_json)

    def __repr__(self):
        return '<HolisticLine {} ({})>'.format(self.name, self.line_type)


class HolisticAttempt(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    exercise_id = db.Column(db.Integer, db.ForeignKey('holistic_exercise.id'), nullable=False)
    exercise    = db.relationship('HolisticExercise', backref='attempts')

    # JSON dict keyed by HolisticLine id (as string): {"3": [...notes...], "5": [...chords...], ...}
    user_data_json = db.Column(db.Text, nullable=False, default='{}')

    # JSON dict of individual scores, keyed by line id: {"3_pitch": 85.0, "3_duration": 72.0,
    #   "5_letter": 90.0, "5_quality": 80.0, "4_duration": 70.0}
    scores_json    = db.Column(db.Text, nullable=False, default='{}')

    overall_score  = db.Column(db.Float, default=0.0)
    created_at     = db.Column(db.DateTime, server_default=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user    = db.relationship('User', backref='holistic_attempts')

    @property
    def user_data(self):
        return json.loads(self.user_data_json)

    @property
    def scores(self):
        return json.loads(self.scores_json)

    def __repr__(self):
        return '<HolisticAttempt ex={} score={:.1f}>'.format(self.exercise_id, self.overall_score)


class HarmonicAttempt(db.Model):
    id                     = db.Column(db.Integer, primary_key=True)
    progression_id         = db.Column(db.Integer, db.ForeignKey('chord_progression.id'), nullable=False)
    progression            = db.relationship('ChordProgression', backref='attempts')
    user_chords_json       = db.Column(db.Text, nullable=False, default='[]')
    chord_letter_accuracy  = db.Column(db.Float, default=0.0)
    chord_quality_accuracy = db.Column(db.Float, default=0.0)
    overall_score          = db.Column(db.Float, default=0.0)
    created_at             = db.Column(db.DateTime, server_default=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user    = db.relationship('User', backref='harmonic_attempts')

    @property
    def user_chords(self):
        return json.loads(self.user_chords_json)

    def __repr__(self):
        return f'<HarmonicAttempt prog={self.progression_id} score={self.overall_score:.1f}>'


class Container(db.Model):
    __tablename__ = 'container'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.String(300))
    created_at  = db.Column(db.DateTime, server_default=db.func.now())
    melodies    = db.relationship('Melody', backref='container', lazy='dynamic')

    def __repr__(self):
        return f'<Container {self.name}>'


class GenProgression(db.Model):
    __tablename__ = 'gen_progression'
    id          = db.Column(db.Integer, primary_key=True)
    number      = db.Column(db.Integer, unique=True, nullable=False)
    name        = db.Column(db.String(120))
    length_bars = db.Column(db.Integer, nullable=False, default=4)
    mode        = db.Column(db.String(10), nullable=False, default='major')
    chords_json = db.Column(db.Text, nullable=False)
    difficulty  = db.Column(db.Integer, nullable=False, default=1)

    @property
    def chords(self):
        return json.loads(self.chords_json)

    def __repr__(self):
        return f'<GenProgression #{self.number} {self.name}>'


class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name  = db.Column(db.String(100))
    # role values: 'student' | 'admin_teacher' | 'class_teacher' | 'admin'
    role          = db.Column(db.String(20), nullable=False, default='student')
    created_at    = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f'<User {self.email} role={self.role}>'


# ─────────────────────────────────────────────────────────────────────────────
# NAMING: "Section" in code, "class" in the database
#
# What staff call a Section (and students see as a Classroom) is still stored in
# tables named `class`, `class_members` and `class_module_exercise`, with
# `class_id` foreign keys. The Python layer was renamed to Section; the physical
# schema deliberately was not, so no migration was needed against the existing
# database.
#
# Every place the two diverge is pinned explicitly below via __tablename__ and
# db.Column('class_id', ...) — SQLAlchemy maps the new attribute name onto the
# old column. If you ever migrate the schema for real, the full mapping is
# documented in docs/NAMING.md; renaming the physical columns then means
# deleting these explicit overrides, nothing more.
# ─────────────────────────────────────────────────────────────────────────────

section_members = db.Table(
    'class_members',                                   # DB name kept — see above
    db.Column('class_id', db.Integer, db.ForeignKey('class.id'), primary_key=True),
    db.Column('user_id',  db.Integer, db.ForeignKey('user.id'),  primary_key=True),
)


class Section(db.Model):
    """A group of students taught together. Staff UI calls this a Section;
    student UI calls it a Classroom. Stored in the `class` table."""
    __tablename__ = 'class'                            # DB name kept — see above
    id                   = db.Column(db.Integer, primary_key=True)
    name                 = db.Column(db.String(120), nullable=False)
    join_code            = db.Column(db.String(12), unique=True, nullable=False)
    teacher_id           = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assigned_teacher_id  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at           = db.Column(db.DateTime, server_default=db.func.now())

    course_id  = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)
    course     = db.relationship('Course', backref='sections')

    teacher          = db.relationship('User', foreign_keys=[teacher_id],
                                       backref='sections_taught')
    assigned_teacher = db.relationship('User', foreign_keys=[assigned_teacher_id],
                                       backref='sections_assigned')
    members = db.relationship('User', secondary=section_members, backref='sections')

    def __repr__(self):
        return f'<Section {self.name}>'


class School(db.Model):
    __tablename__ = 'school'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False, unique=True)
    join_code  = db.Column(db.String(12), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    courses     = db.relationship('Course', backref='school', lazy='dynamic')
    memberships = db.relationship('SchoolMembership', backref='school', lazy='dynamic')

    def __repr__(self):
        return f'<School {self.name}>'


class SchoolMembership(db.Model):
    __tablename__ = 'school_membership'
    id        = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=False)
    user_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # role values: 'student' | 'admin_teacher' | 'class_teacher'
    role      = db.Column(db.String(20), nullable=False, default='student')
    joined_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship('User', backref='school_memberships')

    __table_args__ = (db.UniqueConstraint('school_id', 'user_id'),)

    def __repr__(self):
        return f'<SchoolMembership school={self.school_id} user={self.user_id} role={self.role}>'


class Course(db.Model):
    __tablename__ = 'course'
    id        = db.Column(db.Integer, primary_key=True)
    name      = db.Column(db.String(120), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    modules = db.relationship('Module', backref='course', lazy='dynamic',
                              order_by='Module.order')

    def __repr__(self):
        return f'<Course {self.name}>'


class Module(db.Model):
    __tablename__ = 'module'
    id        = db.Column(db.Integer, primary_key=True)
    name      = db.Column(db.String(120), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    order     = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    exercises = db.relationship('ModuleExercise', backref='module', lazy='dynamic',
                                order_by='ModuleExercise.order')

    def __repr__(self):
        return f'<Module {self.name}>'


class ModuleExercise(db.Model):
    __tablename__ = 'module_exercise'
    id            = db.Column(db.Integer, primary_key=True)
    module_id     = db.Column(db.Integer, db.ForeignKey('module.id'), nullable=False)
    exercise_type = db.Column(db.String(20), nullable=False)
    exercise_id   = db.Column(db.Integer, nullable=False)
    name          = db.Column(db.String(100), nullable=False, default='')
    params_json   = db.Column(db.Text, nullable=True)
    order         = db.Column(db.Integer, nullable=False, default=0)
    completion_criterion_json = db.Column(db.Text, nullable=False, default='{"attempts":1}')

    @property
    def completion_criterion(self):
        return json.loads(self.completion_criterion_json)

    @property
    def params(self):
        return json.loads(self.params_json) if self.params_json else {}

    def __repr__(self):
        return f'<ModuleExercise {self.name or self.exercise_type}>'


class SectionModuleExercise(db.Model):
    """Per-section override of the course curriculum. Stored in
    `class_module_exercise`; `section_id` maps onto the `class_id` column."""
    __tablename__ = 'class_module_exercise'            # DB name kept — see above
    id                 = db.Column(db.Integer, primary_key=True)
    section_id         = db.Column('class_id', db.Integer,      # column name kept
                                   db.ForeignKey('class.id'), nullable=False)
    module_exercise_id = db.Column(db.Integer, db.ForeignKey('module_exercise.id'), nullable=True)
    action             = db.Column(db.String(20), nullable=False, default='add')
    exercise_type      = db.Column(db.String(20), nullable=True)
    exercise_id        = db.Column(db.Integer, nullable=True)
    order              = db.Column(db.Integer, nullable=True)
    completion_criterion_json = db.Column(db.Text, nullable=True)
    module_id          = db.Column(db.Integer, db.ForeignKey('module.id'), nullable=True)

    section         = db.relationship('Section', backref='module_overrides')
    module_exercise = db.relationship('ModuleExercise', backref='section_overrides')

    @property
    def completion_criterion(self):
        return json.loads(self.completion_criterion_json) if self.completion_criterion_json else None

    def __repr__(self):
        return f'<SectionModuleExercise section={self.section_id} action={self.action}>'


class ModuleCompletion(db.Model):
    __tablename__ = 'module_completion'
    id                 = db.Column(db.Integer, primary_key=True)
    user_id            = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    section_id         = db.Column('class_id', db.Integer,      # column name kept
                                   db.ForeignKey('class.id'), nullable=False)
    module_exercise_id = db.Column(db.Integer, db.ForeignKey('module_exercise.id'), nullable=True)
    section_exercise_id = db.Column('class_exercise_id', db.Integer,   # column kept
                                    db.ForeignKey('class_module_exercise.id'), nullable=True)
    best_score         = db.Column(db.Float, nullable=True)
    attempt_count      = db.Column(db.Integer, nullable=False, default=0)
    passing_count      = db.Column(db.Integer, nullable=False, default=0)
    is_complete        = db.Column(db.Boolean, nullable=False, default=False)
    completed_at       = db.Column(db.DateTime, server_default=db.func.now())

    user    = db.relationship('User', backref='module_completions')
    section = db.relationship('Section', backref='module_completions')

    # Constraint args reference physical COLUMN names, which are still class_*.
    __table_args__ = (
        db.UniqueConstraint('user_id', 'class_id', 'module_exercise_id',
                            name='uq_completion_module_exercise'),
        db.UniqueConstraint('user_id', 'class_id', 'class_exercise_id',
                            name='uq_completion_class_exercise'),
    )

    def __repr__(self):
        return f'<ModuleCompletion user={self.user_id} section={self.section_id}>'
