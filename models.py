from flask_sqlalchemy import SQLAlchemy
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
    midi_filename = db.Column(db.String(100), nullable=False)
    # JSON array of {key, duration[, dotted]} objects using VexFlow notation
    notes_json = db.Column(db.Text, nullable=False)
    time_signature = db.Column(db.String(10), default='4/4')
    key_signature = db.Column(db.String(10), default='C')
    clef = db.Column(db.String(10), default='treble')
    # Shortest note value used: 'h', 'q', '8', '16'
    min_duration = db.Column(db.String(5), default='q')
    difficulty = db.Column(db.Integer, default=1)  # 1–5
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

    @property
    def user_notes(self):
        return json.loads(self.user_notes_json)

    def __repr__(self):
        return f'<UserAttempt melody={self.melody_id} score={self.overall_score:.1f}>'


class Rhythm(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300))
    # JSON array of {duration[, dotted]} objects — no pitch
    notes_json = db.Column(db.Text, nullable=False)
    time_signature = db.Column(db.String(10), default='4/4')
    min_duration = db.Column(db.String(5), default='q')
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

    @property
    def user_notes(self):
        return json.loads(self.user_notes_json)

    def __repr__(self):
        return f'<RhythmAttempt rhythm={self.rhythm_id} score={self.duration_accuracy:.1f}>'
