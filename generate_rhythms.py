"""
generate_rhythms.py — Seed the database with sample rhythm exercises.

Run once (or any time you want to update/add rhythms):
    python3 generate_rhythms.py

Notes format: list of dicts with 'duration' (e.g. 'q', '8', 'h', 'qr')
and optionally 'dotted': True.  No pitch — all notes are unpitched.
"""

import json
from app import app
from models import db, Rhythm, Tag

# ---------------------------------------------------------------------------
# Rhythm definitions
# Beat counts verified per time signature:
#   4/4 → 4 beats/measure   3/4 → 3   6/8 → 3 (quarter-note units)
# ---------------------------------------------------------------------------
RHYTHMS = [
    # ---- easy ----------------------------------------------------------------
    {
        'name': 'Simple March',
        'description': 'Steady quarter note march pattern',
        'time_signature': '4/4',
        'min_duration': 'q',
        'tempo': 90,
        'tags': ['easy'],
        'notes': [
            # m1: 1+1+1+1 = 4
            {'duration': 'q'}, {'duration': 'q'}, {'duration': 'q'}, {'duration': 'q'},
            # m2: 2+1+1 = 4
            {'duration': 'h'}, {'duration': 'q'}, {'duration': 'q'},
            # m3: 1+1+2 = 4
            {'duration': 'q'}, {'duration': 'q'}, {'duration': 'h'},
            # m4: 4
            {'duration': 'w'},
        ],
    },
    {
        'name': 'Half Note Groove',
        'description': 'Simple half and quarter note pattern',
        'time_signature': '4/4',
        'min_duration': 'q',
        'tempo': 80,
        'tags': ['easy'],
        'notes': [
            # m1: 2+2 = 4
            {'duration': 'h'}, {'duration': 'h'},
            # m2: 1+1+2 = 4
            {'duration': 'q'}, {'duration': 'q'}, {'duration': 'h'},
            # m3: 2+1+1 = 4
            {'duration': 'h'}, {'duration': 'q'}, {'duration': 'q'},
            # m4: 4
            {'duration': 'w'},
        ],
    },

    # ---- waltz ---------------------------------------------------------------
    {
        'name': 'Basic Waltz',
        'description': 'A classic strong-weak-weak waltz feel',
        'time_signature': '3/4',
        'min_duration': 'q',
        'tempo': 120,
        'tags': ['waltz', 'easy'],
        'notes': [
            # m1: 1+1+1 = 3
            {'duration': 'q'}, {'duration': 'q'}, {'duration': 'q'},
            # m2: 3
            {'duration': 'h', 'dotted': True},
            # m3: 3
            {'duration': 'q'}, {'duration': 'q'}, {'duration': 'q'},
            # m4: 3
            {'duration': 'h', 'dotted': True},
        ],
    },
    {
        'name': 'Lilting Waltz',
        'description': 'Waltz with eighth-note movement',
        'time_signature': '3/4',
        'min_duration': '8',
        'tempo': 116,
        'tags': ['waltz'],
        'notes': [
            # m1: 1+0.5+0.5+1 = 3
            {'duration': 'q'}, {'duration': '8'}, {'duration': '8'}, {'duration': 'q'},
            # m2: 2+1 = 3
            {'duration': 'h'}, {'duration': 'q'},
            # m3: 1+0.5+0.5+1 = 3
            {'duration': 'q'}, {'duration': '8'}, {'duration': '8'}, {'duration': 'q'},
            # m4: 3
            {'duration': 'h', 'dotted': True},
        ],
    },

    # ---- intermediate --------------------------------------------------------
    {
        'name': 'Eighth Note Mix',
        'description': 'Mix of quarter and eighth notes with a rest',
        'time_signature': '4/4',
        'min_duration': '8',
        'tempo': 100,
        'tags': ['intermediate'],
        'notes': [
            # m1: 1+0.5+0.5+1+1 = 4
            {'duration': 'q'}, {'duration': '8'}, {'duration': '8'}, {'duration': 'q'}, {'duration': 'q'},
            # m2: 0.5+0.5+0.5+0.5+2 = 4
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'}, {'duration': '8'}, {'duration': 'h'},
            # m3: 1+1+0.5+0.5+1 = 4
            {'duration': 'q'}, {'duration': 'q'}, {'duration': '8'}, {'duration': '8'}, {'duration': 'q'},
            # m4: 2+1+1 = 4
            {'duration': 'h'}, {'duration': 'q'}, {'duration': 'qr'},
        ],
    },
    {
        'name': 'Syncopated Groove',
        'description': 'Off-beat accents and syncopation',
        'time_signature': '4/4',
        'min_duration': '8',
        'tempo': 96,
        'tags': ['intermediate'],
        'notes': [
            # m1: 1.5+0.5+2 = 4
            {'duration': 'q', 'dotted': True}, {'duration': '8'}, {'duration': 'h'},
            # m2: 0.5+0.5+1+0.5+0.5+1 = 4
            {'duration': '8'}, {'duration': '8'}, {'duration': 'q'}, {'duration': '8'}, {'duration': '8'}, {'duration': 'q'},
            # m3: 1.5+0.5+1+1 = 4
            {'duration': 'q', 'dotted': True}, {'duration': '8'}, {'duration': 'q'}, {'duration': 'q'},
            # m4: 2+2 = 4
            {'duration': 'h'}, {'duration': 'h'},
        ],
    },
    {
        'name': 'Dotted Rhythm',
        'description': 'Swinging dotted eighth–sixteenth pattern',
        'time_signature': '4/4',
        'min_duration': '16',
        'tempo': 92,
        'tags': ['intermediate'],
        'notes': [
            # m1: 0.75+0.25+0.75+0.25+2 = 4
            {'duration': '8', 'dotted': True}, {'duration': '16'},
            {'duration': '8', 'dotted': True}, {'duration': '16'},
            {'duration': 'h'},
            # m2: 0.75+0.25+1+1+1 = 4
            {'duration': '8', 'dotted': True}, {'duration': '16'},
            {'duration': 'q'}, {'duration': 'q'}, {'duration': 'q'},
            # m3: 0.75+0.25+0.75+0.25+1+1 = 4
            {'duration': '8', 'dotted': True}, {'duration': '16'},
            {'duration': '8', 'dotted': True}, {'duration': '16'},
            {'duration': 'q'}, {'duration': 'q'},
            # m4: 4
            {'duration': 'w'},
        ],
    },

    # ---- fast ----------------------------------------------------------------
    {
        'name': '16th Note Burst',
        'description': 'Fast runs of sixteenth notes',
        'time_signature': '4/4',
        'min_duration': '16',
        'tempo': 108,
        'tags': ['fast'],
        'notes': [
            # m1: 0.25×16 = 4
            {'duration': '16'}, {'duration': '16'}, {'duration': '16'}, {'duration': '16'},
            {'duration': '16'}, {'duration': '16'}, {'duration': '16'}, {'duration': '16'},
            {'duration': '16'}, {'duration': '16'}, {'duration': '16'}, {'duration': '16'},
            {'duration': '16'}, {'duration': '16'}, {'duration': '16'}, {'duration': '16'},
            # m2: 1+0.25×4+2 = 4
            {'duration': 'q'},
            {'duration': '16'}, {'duration': '16'}, {'duration': '16'}, {'duration': '16'},
            {'duration': 'h'},
            # m3: 0.25×2+0.5+0.25×2+0.5+2 = 4
            {'duration': '16'}, {'duration': '16'}, {'duration': '8'},
            {'duration': '16'}, {'duration': '16'}, {'duration': '8'},
            {'duration': 'h'},
        ],
    },
    {
        'name': 'Fast Mixed',
        'description': 'Quick patterns mixing sixteenth and eighth notes',
        'time_signature': '4/4',
        'min_duration': '16',
        'tempo': 116,
        'tags': ['fast'],
        'notes': [
            # m1: 0.5+0.25×2+0.5+0.25×2+2 = 4
            {'duration': '8'}, {'duration': '16'}, {'duration': '16'},
            {'duration': '8'}, {'duration': '16'}, {'duration': '16'},
            {'duration': 'h'},
            # m2: 0.25×4+1+1+1 = 4
            {'duration': '16'}, {'duration': '16'}, {'duration': '16'}, {'duration': '16'},
            {'duration': 'q'}, {'duration': 'q'}, {'duration': 'q'},
            # m3: 0.5+0.25×2+0.5+0.5+1+1 = 4
            {'duration': '8'}, {'duration': '16'}, {'duration': '16'},
            {'duration': '8'}, {'duration': '8'},
            {'duration': 'q'}, {'duration': 'q'},
            # m4: 4
            {'duration': 'w'},
        ],
    },

    # ---- polyrhythm ----------------------------------------------------------
    {
        'name': 'Compound Groove',
        'description': 'Rhythmic pattern in compound meter (6/8)',
        'time_signature': '6/8',
        'min_duration': '8',
        'tempo': 100,
        'tags': ['intermediate', 'polyrhythm'],
        'notes': [
            # m1: beat1=0.5×3, beat2=0.5×3 → 3 q-beats total
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            # m2: 1.5+0.5×3 = 3
            {'duration': 'q', 'dotted': True},
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            # m3: 1.5+1.5 = 3
            {'duration': 'q', 'dotted': True}, {'duration': 'q', 'dotted': True},
        ],
    },
    {
        'name': 'Hemiola',
        'description': '3-against-2 feel — three half-note pulses across two 3/4 measures',
        'time_signature': '3/4',
        'min_duration': 'q',
        'tempo': 104,
        'tags': ['polyrhythm', 'waltz'],
        'notes': [
            # m1: 2+1 = 3
            {'duration': 'h'}, {'duration': 'q'},
            # m2: 1+2 = 3
            {'duration': 'q'}, {'duration': 'h'},
            # m3: 2+1 = 3
            {'duration': 'h'}, {'duration': 'q'},
            # m4: 3
            {'duration': 'h', 'dotted': True},
        ],
    },
    {
        'name': 'Cross-Rhythm',
        'description': 'Dotted-half groupings imply a 3/4 feel within 4/4',
        'time_signature': '4/4',
        'min_duration': 'q',
        'tempo': 100,
        'tags': ['polyrhythm'],
        'notes': [
            # m1: 3+1 = 4
            {'duration': 'h', 'dotted': True}, {'duration': 'q'},
            # m2: 3+1 = 4
            {'duration': 'h', 'dotted': True}, {'duration': 'q'},
            # m3: 2+2 = 4
            {'duration': 'h'}, {'duration': 'h'},
            # m4: 4
            {'duration': 'w'},
        ],
    },

    # ---- more easy -----------------------------------------------------------
    {
        'name': 'Quarter Rest Groove',
        'description': 'Quarter note pattern with strategic rests',
        'time_signature': '4/4',
        'min_duration': 'q',
        'tempo': 88,
        'tags': ['easy'],
        'notes': [
            # m1: 1+1+1+1 = 4
            {'duration': 'q'}, {'duration': 'qr'}, {'duration': 'q'}, {'duration': 'q'},
            # m2: 2+1+1 = 4
            {'duration': 'h'}, {'duration': 'qr'}, {'duration': 'q'},
            # m3: 1+1+1+1 = 4
            {'duration': 'q'}, {'duration': 'qr'}, {'duration': 'h'},
            # m4: 4
            {'duration': 'w'},
        ],
    },
    {
        'name': 'Two-Four March',
        'description': 'Crisp march in cut-time feel',
        'time_signature': '2/4',
        'min_duration': 'q',
        'tempo': 96,
        'tags': ['easy'],
        'notes': [
            # m1–m8, each 2 q-beats
            {'duration': 'q'}, {'duration': 'q'},       # m1: 2
            {'duration': '8'}, {'duration': '8'}, {'duration': 'q'},  # m2: 2
            {'duration': 'q'}, {'duration': 'q'},       # m3: 2
            {'duration': 'h'},                          # m4: 2
            {'duration': 'q'}, {'duration': 'q'},       # m5: 2
            {'duration': 'q', 'dotted': True}, {'duration': '8'},     # m6: 2
            {'duration': 'q'}, {'duration': 'q'},       # m7: 2
            {'duration': 'h'},                          # m8: 2
        ],
    },

    # ---- more intermediate ---------------------------------------------------
    {
        'name': 'Syncopated 2/4',
        'description': 'Off-beat accents in a two-beat groove',
        'time_signature': '2/4',
        'min_duration': '8',
        'tempo': 100,
        'tags': ['intermediate'],
        'notes': [
            # m1: 0.5×4 = 2
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            # m2: 1.5+0.5 = 2
            {'duration': 'q', 'dotted': True}, {'duration': '8'},
            # m3: 0.5+1+0.5 = 2
            {'duration': '8'}, {'duration': 'q'}, {'duration': '8'},
            # m4: 2
            {'duration': 'h'},
            # m5: 0.5×4 = 2
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            # m6: 1.5+0.5 = 2
            {'duration': 'q', 'dotted': True}, {'duration': '8'},
            # m7: 0.5+0.5+1 = 2
            {'duration': '8'}, {'duration': '8'}, {'duration': 'q'},
            # m8: 2
            {'duration': 'h'},
        ],
    },
    {
        'name': 'Bossa Feel',
        'description': 'Syncopated dotted-note pattern with a bossa-nova inflection',
        'time_signature': '4/4',
        'min_duration': '8',
        'tempo': 104,
        'tags': ['intermediate'],
        'notes': [
            # m1: 1.5+0.5+1+1 = 4
            {'duration': 'q', 'dotted': True}, {'duration': '8'}, {'duration': 'q'}, {'duration': 'q'},
            # m2: 0.5+0.5+1.5+0.5+1 = 4
            {'duration': '8'}, {'duration': '8'}, {'duration': 'q', 'dotted': True}, {'duration': '8'}, {'duration': 'q'},
            # m3: 1.5+0.5+1+1 = 4
            {'duration': 'q', 'dotted': True}, {'duration': '8'}, {'duration': 'q'}, {'duration': 'q'},
            # m4: 4
            {'duration': 'w'},
        ],
    },
    {
        'name': 'Pastoral 12/8',
        'description': 'Flowing compound quadruple meter',
        'time_signature': '12/8',
        'min_duration': '8',
        'tempo': 92,
        'tags': ['intermediate'],
        'notes': [
            # beatsPerMeasure = 12*(4/8) = 6 q-beats
            # m1: q.×4 = 1.5×4 = 6
            {'duration': 'q', 'dotted': True}, {'duration': 'q', 'dotted': True},
            {'duration': 'q', 'dotted': True}, {'duration': 'q', 'dotted': True},
            # m2: 8×12 = 6
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            # m3: (q.+8+8+8)×2 = (1.5+1.5)×2 = 6
            {'duration': 'q', 'dotted': True}, {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            {'duration': 'q', 'dotted': True}, {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            # m4: h.+h. = 3+3 = 6
            {'duration': 'h', 'dotted': True}, {'duration': 'h', 'dotted': True},
        ],
    },
    {
        'name': 'Compound Waltz',
        'description': 'Three flowing beats in 9/8',
        'time_signature': '9/8',
        'min_duration': '8',
        'tempo': 108,
        'tags': ['waltz', 'intermediate'],
        'notes': [
            # beatsPerMeasure = 9*(4/8) = 4.5 q-beats
            # m1: q.×3 = 1.5×3 = 4.5
            {'duration': 'q', 'dotted': True}, {'duration': 'q', 'dotted': True}, {'duration': 'q', 'dotted': True},
            # m2: 8×3 + 8×3 + q. = 1.5+1.5+1.5 = 4.5
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            {'duration': 'q', 'dotted': True},
            # m3: q.×3 = 4.5
            {'duration': 'q', 'dotted': True}, {'duration': 'q', 'dotted': True}, {'duration': 'q', 'dotted': True},
            # m4: h. + q. = 3 + 1.5 = 4.5
            {'duration': 'h', 'dotted': True}, {'duration': 'q', 'dotted': True},
        ],
    },

    # ---- tied notes ----------------------------------------------------------
    {
        'name': 'Across the Barline',
        'description': 'Half note tied across the bar — sounds like a whole note spanning two measures',
        'time_signature': '4/4',
        'min_duration': 'q',
        'tempo': 76,
        'tags': ['tied notes', 'intermediate'],
        'notes': [
            # m1: q + q + h(tieStart) = 1+1+2 = 4
            {'duration': 'q'},
            {'duration': 'q'},
            {'duration': 'h', 'dotted': False, 'tieStart': True},
            # m2: h(tieEnd) + q + q = 2+1+1 = 4
            {'duration': 'h', 'dotted': False, 'tieEnd': True},
            {'duration': 'q'},
            {'duration': 'q'},
        ],
    },
    {
        'name': 'Barline Syncopation',
        'description': 'Quarter note tied across the barline creates a syncopated two-beat accent',
        'time_signature': '3/4',
        'min_duration': 'q',
        'tempo': 88,
        'tags': ['tied notes', 'waltz', 'intermediate'],
        'notes': [
            # m1: q + q + q(tieStart) = 1+1+1 = 3
            {'duration': 'q'},
            {'duration': 'q'},
            {'duration': 'q', 'dotted': False, 'tieStart': True},
            # m2: q(tieEnd) + q + q = 1+1+1 = 3
            {'duration': 'q', 'dotted': False, 'tieEnd': True},
            {'duration': 'q'},
            {'duration': 'q'},
        ],
    },

    # ---- more fast -----------------------------------------------------------
    {
        'name': 'Tarantella',
        'description': 'Spinning Italian dance in fast 6/8',
        'time_signature': '6/8',
        'min_duration': '16',
        'tempo': 132,
        'tags': ['fast'],
        'notes': [
            # beatsPerMeasure = 6*(4/8) = 3 q-beats
            # m1: 8×6 = 3
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            # m2: 16×6 + 8×3 = 1.5+1.5 = 3
            {'duration': '16'}, {'duration': '16'}, {'duration': '16'},
            {'duration': '16'}, {'duration': '16'}, {'duration': '16'},
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            # m3: 8×6 = 3
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            # m4: q.+q. = 3
            {'duration': 'q', 'dotted': True}, {'duration': 'q', 'dotted': True},
        ],
    },
    {
        'name': 'Fast Waltz',
        'description': 'Rapid waltz with sixteenth-note fills',
        'time_signature': '3/4',
        'min_duration': '16',
        'tempo': 160,
        'tags': ['fast', 'waltz'],
        'notes': [
            # m1: 1 + 0.25×4 + 1 = 3
            {'duration': 'q'}, {'duration': '16'}, {'duration': '16'}, {'duration': '16'}, {'duration': '16'}, {'duration': 'q'},
            # m2: 0.5×6 = 3
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            {'duration': '8'}, {'duration': '8'}, {'duration': '8'},
            # m3: 1 + 0.25×4 + 1 = 3
            {'duration': 'q'}, {'duration': '16'}, {'duration': '16'}, {'duration': '16'}, {'duration': '16'}, {'duration': 'q'},
            # m4: 3
            {'duration': 'h', 'dotted': True},
        ],
    },
]


def seed_rhythms():
    with app.app_context():
        db.create_all()

        for r in RHYTHMS:
            # Get or create each tag
            tags = []
            for tag_name in r['tags']:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name, description=f'{tag_name} rhythm style')
                    db.session.add(tag)
                    db.session.flush()
                tags.append(tag)

            notes_json = json.dumps(r['notes'])

            existing = Rhythm.query.filter_by(name=r['name']).first()
            if existing:
                existing.description    = r.get('description', '')
                existing.time_signature = r['time_signature']
                existing.min_duration   = r.get('min_duration', 'q')
                existing.tempo          = r.get('tempo', 100)
                existing.notes_json     = notes_json
                existing.tags           = tags
                print(f'  Updated: {r["name"]}')
            else:
                rhythm = Rhythm(
                    name=r['name'],
                    description=r.get('description', ''),
                    time_signature=r['time_signature'],
                    min_duration=r.get('min_duration', 'q'),
                    tempo=r.get('tempo', 100),
                    notes_json=notes_json,
                    tags=tags,
                )
                db.session.add(rhythm)
                print(f'  Created: {r["name"]}')

        db.session.commit()
        print('Done — rhythm seed complete.')


if __name__ == '__main__':
    seed_rhythms()
