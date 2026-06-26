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

    # Clef for the primary melody line
    melody_clef    = db.Column(db.String(10),  default='treble')

    # Parsed correct answers (JSON), generated at seed time from MIDI files.
    # Array of {key, duration[, dotted]} objects -- same format as Melody.notes_json
    melody_notes_json  = db.Column(db.Text, nullable=False, default='[]')

    # Parsed chord progression -- same format as ChordProgression.chords_json
    harmony_chords_json = db.Column(db.Text, nullable=False, default='[]')

    # Extra lines metadata + parsed answer data.
    # JSON array. Each element:
    #   For a melody line:
    #     {"type": "melody", "file": "melody_1.mid", "label": "Alto", "clef": "treble",
    #      "notes": [{key, duration[, dotted]}, ...]}
    #   For a rhythm line:
    #     {"type": "rhythm", "file": "rhythm_1.mid", "label": "Kick drum",
    #      "notes": [{duration[, dotted]}, ...]}
    extra_lines_json = db.Column(db.Text, nullable=False, default='[]')

    tags = db.relationship('Tag', secondary=holistic_tags,
                           backref='holistic_exercises', lazy='subquery')

    @property
    def melody_notes(self):
        return json.loads(self.melody_notes_json)

    @property
    def harmony_chords(self):
        return json.loads(self.harmony_chords_json)

    @property
    def extra_lines(self):
        return json.loads(self.extra_lines_json)

    @property
    def wav_url_path(self):
        """Relative URL path for the WAV file, suitable for url_for('static', ...)."""
        return self.folder.rstrip('/') + '/' + self.wav_filename

    @property
    def total_beats(self):
        beat_map = {'w': 4, 'h': 2, 'q': 1, '8': 0.5, '16': 0.25}
        total = 0.0
        for n in self.melody_notes:
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
        return '<HolisticExercise {}>'.format(self.name)


class HolisticAttempt(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    exercise_id = db.Column(db.Integer, db.ForeignKey('holistic_exercise.id'), nullable=False)
    exercise    = db.relationship('HolisticExercise', backref='attempts')

    # JSON dict: {"melody": [...notes...], "harmony": [...chords...],
    #             "melody_1": [...], "rhythm_1": [...], ...}
    user_data_json = db.Column(db.Text, nullable=False, default='{}')

    # JSON dict of individual scores: {"melody_pitch": 85.0, "melody_duration": 72.0,
    #   "harmony_letter": 90.0, "harmony_quality": 80.0,
    #   "melody_1_pitch": 60.0, "melody_1_duration": 50.0,
    #   "rhythm_1_duration": 70.0}
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


class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name  = db.Column(db.String(100))
    role          = db.Column(db.String(20), nullable=False, default='student')
    created_at    = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f'<User {self.email} role={self.role}>'


class_members = db.Table(
    'class_members',
    db.Column('class_id', db.Integer, db.ForeignKey('class.id'), primary_key=True),
    db.Column('user_id',  db.Integer, db.ForeignKey('user.id'),  primary_key=True),
)


class Class(db.Model):
    __tablename__ = 'class'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False)
    join_code  = db.Column(db.String(12), unique=True, nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    course_id  = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)
    course     = db.relationship('Course', backref='classes')

    teacher = db.relationship('User', backref='classes_taught')
    members = db.relationship('User', secondary=class_members, backref='classes')

    def __repr__(self):
        return f'<Class {self.name}>'


class School(db.Model):
    __tablename__ = 'school'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    courses = db.relationship('Course', backref='school', lazy='dynamic')

    def __repr__(self):
        return f'<School {self.name}>'


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
    order         = db.Column(db.Integer, nullable=False, default=0)
    completion_criterion_json = db.Column(db.Text, nullable=False, default='{"attempts":1}')

    @property
    def completion_criterion(self):
        return json.loads(self.completion_criterion_json)

    def __repr__(self):
        return f'<ModuleExercise {self.exercise_type}:{self.exercise_id}>'


class ClassModuleExercise(db.Model):
    __tablename__ = 'class_module_exercise'
    id                 = db.Column(db.Integer, primary_key=True)
    class_id           = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    module_exercise_id = db.Column(db.Integer, db.ForeignKey('module_exercise.id'), nullable=True)
    action             = db.Column(db.String(20), nullable=False, default='add')
    exercise_type      = db.Column(db.String(20), nullable=True)
    exercise_id        = db.Column(db.Integer, nullable=True)
    order              = db.Column(db.Integer, nullable=True)
    completion_criterion_json = db.Column(db.Text, nullable=True)
    module_id          = db.Column(db.Integer, db.ForeignKey('module.id'), nullable=True)

    klass           = db.relationship('Class', backref='module_overrides')
    module_exercise = db.relationship('ModuleExercise', backref='class_overrides')

    @property
    def completion_criterion(self):
        return json.loads(self.completion_criterion_json) if self.completion_criterion_json else None

    def __repr__(self):
        return f'<ClassModuleExercise class={self.class_id} action={self.action}>'


class ModuleCompletion(db.Model):
    __tablename__ = 'module_completion'
    id                 = db.Column(db.Integer, primary_key=True)
    user_id            = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    class_id           = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    module_exercise_id = db.Column(db.Integer, db.ForeignKey('module_exercise.id'), nullable=True)
    class_exercise_id  = db.Column(db.Integer, db.ForeignKey('class_module_exercise.id'), nullable=True)
    best_score         = db.Column(db.Float, nullable=True)
    completed_at       = db.Column(db.DateTime, server_default=db.func.now())

    user  = db.relationship('User', backref='module_completions')
    klass = db.relationship('Class', backref='module_completions')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'class_id', 'module_exercise_id',
                            name='uq_completion_module_exercise'),
        db.UniqueConstraint('user_id', 'class_id', 'class_exercise_id',
                            name='uq_completion_class_exercise'),
    )

    def __repr__(self):
        return f'<ModuleCompletion user={self.user_id} class={self.class_id}>'
