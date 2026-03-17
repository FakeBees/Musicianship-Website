"""
generate_midi.py
================
Run once to create starter MIDI files and seed the database.

Usage:
    python generate_midi.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from midiutil import MIDIFile

MIDI_DIR = os.path.join(os.path.dirname(__file__), 'static', 'midi')
os.makedirs(MIDI_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Duration helpers
# ---------------------------------------------------------------------------

DURATION_BEATS = {
    'w': 4, 'h': 2, 'q': 1, '8': 0.5, '16': 0.25,
}

# MIDI note numbers (middle C = C4 = 60)
NOTE_TO_MIDI = {
    'c/2': 36, 'c#/2': 37, 'db/2': 37,
    'd/2': 38, 'd#/2': 39, 'eb/2': 39,
    'e/2': 40,
    'f/2': 41, 'f#/2': 42, 'gb/2': 42,
    'g/2': 43, 'g#/2': 44, 'ab/2': 44,
    'a/2': 45, 'a#/2': 46, 'bb/2': 46,
    'b/2': 47,
    'c/3': 48, 'c#/3': 49, 'db/3': 49,
    'd/3': 50, 'd#/3': 51, 'eb/3': 51,
    'e/3': 52,
    'f/3': 53, 'f#/3': 54, 'gb/3': 54,
    'g/3': 55, 'g#/3': 56, 'ab/3': 56,
    'a/3': 57, 'a#/3': 58, 'bb/3': 58,
    'b/3': 59,
    'c/4': 60, 'c#/4': 61, 'db/4': 61,
    'd/4': 62, 'd#/4': 63, 'eb/4': 63,
    'e/4': 64,
    'f/4': 65, 'f#/4': 66, 'gb/4': 66,
    'g/4': 67, 'g#/4': 68, 'ab/4': 68,
    'a/4': 69, 'a#/4': 70, 'bb/4': 70,
    'b/4': 71,
    'c/5': 72, 'c#/5': 73, 'db/5': 73,
    'd/5': 74, 'd#/5': 75, 'eb/5': 75,
    'e/5': 76,
    'f/5': 77, 'f#/5': 78, 'gb/5': 78,
    'g/5': 79, 'g#/5': 80, 'ab/5': 80,
    'a/5': 81, 'a#/5': 82, 'bb/5': 82,
    'b/5': 83,
}


def write_midi(filename, notes, tempo=100):
    """
    notes: list of (key, duration) or (key, duration, dotted).
    Creates a single-track MIDI file.  Rests are encoded with 'r' suffix
    on duration (e.g. 'qr') and are written as silence.
    """
    midi = MIDIFile(1)
    midi.addTempo(0, 0, tempo)
    time = 0
    i = 0
    while i < len(notes):
        note = notes[i]
        if isinstance(note, dict):
            key       = note['key']
            dur       = note['duration']
            dotted    = note.get('dotted', False)
            tie_start = note.get('tieStart', False)
            tie_end   = note.get('tieEnd', False)
        else:
            key       = note[0]
            dur       = note[1]
            dotted    = len(note) > 2 and note[2]
            tie_start = False
            tie_end   = False

        base_dur = dur.rstrip('r')
        beats = DURATION_BEATS.get(base_dur, 1) * (1.5 if dotted else 1)

        if tie_end:
            # Silent continuation — no new MIDI note, just advance the clock
            time += beats
            i += 1
            continue

        # For a tieStart, accumulate duration across all following tieEnd notes
        # so the MIDI event represents the full held pitch.
        midi_beats = beats
        if tie_start:
            j = i + 1
            while j < len(notes):
                tn = notes[j]
                if isinstance(tn, dict) and tn.get('tieEnd'):
                    td = tn['duration'].rstrip('r')
                    midi_beats += DURATION_BEATS.get(td, 1) * (1.5 if tn.get('dotted') else 1)
                    j += 1
                else:
                    break

        if not dur.endswith('r'):
            midi_note = NOTE_TO_MIDI.get(key.lower())
            if midi_note is None:
                print(f'  WARNING: unknown key "{key}", skipping note')
            else:
                midi.addNote(0, 0, midi_note, time, midi_beats * 0.9, 90)

        time += beats
        i += 1

    path = os.path.join(MIDI_DIR, filename)
    with open(path, 'wb') as f:
        midi.writeFile(f)
    print(f'  Written: {path}')


def notes_to_json(raw_notes):
    result = []
    for note in raw_notes:
        if isinstance(note, dict):
            # Dict format — pass through as-is (preserves tieStart/tieEnd etc.)
            result.append(note)
        else:
            # Tuple format: (key, duration[, dotted])
            key    = note[0]
            dur    = note[1]
            dotted = len(note) > 2 and note[2]
            entry  = {'key': key, 'duration': dur}
            if dotted:
                entry['dotted'] = True
            result.append(entry)
    return json.dumps(result)


# ---------------------------------------------------------------------------
# Melody definitions
# ---------------------------------------------------------------------------

MELODIES = [

    # -----------------------------------------------------------------------
    # 4/4  –  quarter-note minimum
    # -----------------------------------------------------------------------
    {
        'name': 'C Major Scale (Ascending)',
        'description': 'Eight quarter notes ascending the C major scale.',
        'filename': 'c_major_ascending.mid',
        'tempo': 90,
        'time_signature': '4/4',
        'key_signature': 'C',
        'min_duration': 'q',
        'difficulty': 1,
        'tags': ['major-scale', 'stepwise-motion', 'simple'],
        'notes': [
            ('c/4', 'q'), ('d/4', 'q'), ('e/4', 'q'), ('f/4', 'q'),
            ('g/4', 'q'), ('a/4', 'q'), ('b/4', 'q'), ('c/5', 'q'),
        ],
    },
    {
        'name': 'G Major Scale (Descending)',
        'description': 'Eight quarter notes descending the G major scale.',
        'filename': 'g_major_descending.mid',
        'tempo': 90,
        'time_signature': '4/4',
        'key_signature': 'G',
        'min_duration': 'q',
        'difficulty': 2,
        'tags': ['major-scale', 'stepwise-motion', 'simple'],
        'notes': [
            ('g/5', 'q'), ('f#/5', 'q'), ('e/5', 'q'), ('d/5', 'q'),
            ('c/5', 'q'), ('b/4', 'q'), ('a/4', 'q'), ('g/4', 'q'),
        ],
    },
    {
        'name': 'A Natural Minor Scale (Ascending)',
        'description': 'Eight quarter notes ascending the A natural minor scale.',
        'filename': 'a_natural_minor.mid',
        'tempo': 90,
        'time_signature': '4/4',
        'key_signature': 'Am',
        'min_duration': 'q',
        'difficulty': 2,
        'tags': ['minor-scale', 'natural-minor', 'stepwise-motion', 'simple'],
        'notes': [
            ('a/4', 'q'), ('b/4', 'q'), ('c/5', 'q'), ('d/5', 'q'),
            ('e/5', 'q'), ('f/5', 'q'), ('g/5', 'q'), ('a/5', 'q'),
        ],
    },
    {
        'name': 'Simple Melody in C Major',
        'description': 'A two-measure melody using stepwise motion and a leap, in C major.',
        'filename': 'simple_c_major_melody.mid',
        'tempo': 100,
        'time_signature': '4/4',
        'key_signature': 'C',
        'min_duration': 'q',
        'difficulty': 3,
        'tags': ['major-scale', 'stepwise-motion', 'leap-motion'],
        'notes': [
            ('e/4', 'q'), ('d/4', 'q'), ('c/4', 'q'), ('e/4', 'q'),
            ('g/4', 'h'), ('e/4', 'h'),
        ],
    },
    {
        'name': 'Melody with Neapolitan ♭2 (in C)',
        'description': 'A melody in C major that includes the Neapolitan flat-2 (D♭), '
                       'creating a characteristic chromatic tension.',
        'filename': 'neapolitan_melody.mid',
        'tempo': 92,
        'time_signature': '4/4',
        'key_signature': 'C',
        'min_duration': 'q',
        'difficulty': 4,
        'tags': ['major-scale', 'neapolitan-b2', 'chromatic'],
        'notes': [
            ('e/4', 'q'), ('f/4', 'q'), ('db/4', 'q'), ('c/4', 'q'),
            ('g/4', 'h'), ('c/4', 'h'),
        ],
    },
    {
        'name': 'Eb Major Scale (Ascending)',
        'description': 'Eight quarter notes ascending the Eb major scale.',
        'filename': 'eb_major_ascending.mid',
        'tempo': 90,
        'time_signature': '4/4',
        'key_signature': 'Eb',
        'min_duration': 'q',
        'difficulty': 2,
        'tags': ['major-scale', 'stepwise-motion'],
        'notes': [
            ('eb/4', 'q'), ('f/4', 'q'), ('g/4', 'q'), ('ab/4', 'q'),
            ('bb/4', 'q'), ('c/5', 'q'), ('d/5', 'q'), ('eb/5', 'q'),
        ],
    },
    {
        'name': 'Melody in Eb Major with Chromatic',
        'description': 'A two-measure melody in Eb major featuring A natural (♮4) — '
                       'a raised ♭4 that falls outside the key signature.',
        'filename': 'eb_major_melody_chromatic.mid',
        'tempo': 88,
        'time_signature': '4/4',
        'key_signature': 'Eb',
        'min_duration': 'q',
        'difficulty': 3,
        'tags': ['major-scale', 'chromatic', 'stepwise-motion'],
        'notes': [
            ('eb/4', 'q'), ('f/4', 'q'), ('g/4', 'q'), ('ab/4', 'q'),
            ('a/4', 'q'), ('bb/4', 'q'), ('eb/5', 'h'),
        ],
    },

    # -----------------------------------------------------------------------
    # 4/4  –  eighth-note minimum
    # -----------------------------------------------------------------------
    {
        'name': 'Melody in C with Eighth Notes',
        'description': 'A lively two-measure melody in C major mixing quarter and eighth notes.',
        'filename': 'c_major_eighth_notes.mid',
        'tempo': 100,
        'time_signature': '4/4',
        'key_signature': 'C',
        'min_duration': '8',
        'difficulty': 3,
        'tags': ['major-scale', 'stepwise-motion', 'eighth-notes'],
        'notes': [
            ('e/4', 'q'), ('d/4', '8'), ('e/4', '8'), ('g/4', 'q'), ('a/4', 'q'),
            ('g/4', 'h'), ('e/4', 'q'), ('c/4', 'q'),
        ],
    },
    {
        'name': 'Melody in G with Eighth Notes',
        'description': 'A two-measure melody in G major with quarter and eighth notes and a leap.',
        'filename': 'g_major_eighth_notes.mid',
        'tempo': 104,
        'time_signature': '4/4',
        'key_signature': 'G',
        'min_duration': '8',
        'difficulty': 3,
        'tags': ['major-scale', 'stepwise-motion', 'leap-motion', 'eighth-notes'],
        'notes': [
            ('d/5', 'q'), ('b/4', '8'), ('c/5', '8'), ('d/5', 'q'), ('g/4', 'q'),
            ('a/4', 'q'), ('b/4', '8'), ('a/4', '8'), ('g/4', 'h'),
        ],
    },

    # -----------------------------------------------------------------------
    # 4/4  –  sixteenth-note minimum
    # -----------------------------------------------------------------------
    {
        'name': 'Melody in G with Sixteenth Notes',
        'description': 'A two-measure melody in G major featuring a sixteenth-note run.',
        'filename': 'g_major_sixteenth_notes.mid',
        'tempo': 92,
        'time_signature': '4/4',
        'key_signature': 'G',
        'min_duration': '16',
        'difficulty': 4,
        'tags': ['major-scale', 'stepwise-motion', 'sixteenth-notes'],
        'notes': [
            ('g/4', 'q'), ('a/4', '16'), ('b/4', '16'), ('a/4', '16'), ('g/4', '16'),
            ('b/4', 'q'), ('d/5', 'q'),
            ('d/5', 'q', True), ('c/5', '8'), ('b/4', 'q'), ('g/4', 'q'),
        ],
    },
    {
        'name': 'Melody in C with Sixteenth Notes',
        'description': 'A two-measure melody in C major with an ornamental sixteenth-note descent.',
        'filename': 'c_major_sixteenth_notes.mid',
        'tempo': 88,
        'time_signature': '4/4',
        'key_signature': 'C',
        'min_duration': '16',
        'difficulty': 4,
        'tags': ['major-scale', 'stepwise-motion', 'sixteenth-notes'],
        'notes': [
            ('c/5', 'q'), ('b/4', '16'), ('a/4', '16'), ('g/4', '16'), ('f/4', '16'),
            ('e/4', 'q'), ('d/4', 'q'),
            ('e/4', 'q', True), ('d/4', '8'), ('c/4', 'h'),
        ],
    },

    # -----------------------------------------------------------------------
    # 3/4  –  quarter-note minimum
    # -----------------------------------------------------------------------
    {
        'name': 'Waltz in C Major',
        'description': 'A four-measure waltz in 3/4 time using quarter and half notes.',
        'filename': 'waltz_c_major.mid',
        'tempo': 126,
        'time_signature': '3/4',
        'key_signature': 'C',
        'min_duration': 'q',
        'difficulty': 2,
        'tags': ['major-scale', 'stepwise-motion', 'waltz'],
        'notes': [
            ('c/4', 'q'), ('e/4', 'q'), ('g/4', 'q'),
            ('a/4', 'q'), ('g/4', 'q'), ('f/4', 'q'),
            ('e/4', 'h'), ('d/4', 'q'),
            ('c/4', 'h', True),
        ],
    },
    {
        'name': 'Waltz in G Major',
        'description': 'A four-measure waltz in 3/4 time in G major with a dotted-half conclusion.',
        'filename': 'waltz_g_major.mid',
        'tempo': 120,
        'time_signature': '3/4',
        'key_signature': 'G',
        'min_duration': 'q',
        'difficulty': 2,
        'tags': ['major-scale', 'leap-motion', 'waltz'],
        'notes': [
            ('g/4', 'q'), ('b/4', 'q'), ('d/5', 'q'),
            ('e/5', 'q'), ('d/5', 'q'), ('b/4', 'q'),
            ('c/5', 'h'), ('b/4', 'q'),
            ('g/4', 'h', True),
        ],
    },
    {
        'name': 'Minor Waltz in A Minor',
        'description': 'A four-measure waltz in 3/4 time in A minor with expressive leaps.',
        'filename': 'waltz_a_minor.mid',
        'tempo': 116,
        'time_signature': '3/4',
        'key_signature': 'Am',
        'min_duration': 'q',
        'difficulty': 3,
        'tags': ['minor-scale', 'natural-minor', 'leap-motion', 'waltz'],
        'notes': [
            ('a/4', 'q'), ('c/5', 'q'), ('e/5', 'q'),
            ('f/5', 'q'), ('e/5', 'q'), ('d/5', 'q'),
            ('c/5', 'h'), ('b/4', 'q'),
            ('a/4', 'h', True),
        ],
    },

    # -----------------------------------------------------------------------
    # 3/4  –  eighth-note minimum
    # -----------------------------------------------------------------------
    {
        'name': 'Waltz in G with Eighth Notes',
        'description': 'A four-measure waltz in 3/4 time with eighth-note decorations.',
        'filename': 'waltz_g_eighth.mid',
        'tempo': 120,
        'time_signature': '3/4',
        'key_signature': 'G',
        'min_duration': '8',
        'difficulty': 3,
        'tags': ['major-scale', 'stepwise-motion', 'waltz', 'eighth-notes'],
        'notes': [
            ('g/4', 'q'), ('a/4', '8'), ('b/4', '8'), ('g/4', 'q'),
            ('d/5', 'q', True), ('c/5', '8'), ('b/4', 'q'),
            ('a/4', '8'), ('b/4', '8'), ('c/5', '8'), ('b/4', '8'), ('a/4', 'q'),
            ('g/4', 'h', True),
        ],
    },
    {
        'name': 'Minor Waltz in D Minor with Eighths',
        'description': 'A four-measure waltz in 3/4 time in D minor with flowing eighth-note motion.',
        'filename': 'waltz_d_minor_eighth.mid',
        'tempo': 112,
        'time_signature': '3/4',
        'key_signature': 'Dm',
        'min_duration': '8',
        'difficulty': 4,
        'tags': ['minor-scale', 'natural-minor', 'stepwise-motion', 'waltz', 'eighth-notes'],
        'notes': [
            ('d/4', 'q'), ('e/4', '8'), ('f/4', '8'), ('a/4', 'q'),
            ('bb/4', 'q', True), ('a/4', '8'), ('g/4', 'q'),
            ('f/4', '8'), ('g/4', '8'), ('a/4', '8'), ('g/4', '8'), ('f/4', 'q'),
            ('d/4', 'h', True),
        ],
    },

    # -----------------------------------------------------------------------
    # 2/4  –  quarter-note minimum
    # -----------------------------------------------------------------------
    {
        'name': 'March in C Major',
        'description': 'A four-measure march in 2/4 time using quarter and half notes.',
        'filename': 'march_c_major.mid',
        'tempo': 108,
        'time_signature': '2/4',
        'key_signature': 'C',
        'min_duration': 'q',
        'difficulty': 2,
        'tags': ['major-scale', 'stepwise-motion', 'march'],
        'notes': [
            ('c/4', 'q'), ('e/4', 'q'),
            ('g/4', 'q'), ('e/4', 'q'),
            ('f/4', 'q'), ('d/4', 'q'),
            ('c/4', 'h'),
        ],
    },
    {
        'name': 'March in G Major',
        'description': 'A four-measure march in 2/4 time in G major with a leap to the fifth.',
        'filename': 'march_g_major.mid',
        'tempo': 112,
        'time_signature': '2/4',
        'key_signature': 'G',
        'min_duration': 'q',
        'difficulty': 2,
        'tags': ['major-scale', 'leap-motion', 'march'],
        'notes': [
            ('g/4', 'q'), ('d/5', 'q'),
            ('e/5', 'q'), ('b/4', 'q'),
            ('c/5', 'q'), ('a/4', 'q'),
            ('g/4', 'h'),
        ],
    },

    # -----------------------------------------------------------------------
    # 2/4  –  eighth-note minimum
    # -----------------------------------------------------------------------
    {
        'name': 'March in D Major with Eighth Notes',
        'description': 'A four-measure march in 2/4 time in D major with brisk eighth-note runs.',
        'filename': 'march_d_major_eighth.mid',
        'tempo': 108,
        'time_signature': '2/4',
        'key_signature': 'D',
        'min_duration': '8',
        'difficulty': 3,
        'tags': ['major-scale', 'stepwise-motion', 'march', 'eighth-notes'],
        'notes': [
            ('d/4', 'q'), ('e/4', '8'), ('f#/4', '8'),
            ('g/4', 'q'), ('f#/4', '8'), ('e/4', '8'),
            ('d/4', '8'), ('e/4', '8'), ('f#/4', '8'), ('g/4', '8'),
            ('a/4', 'h'),
        ],
    },
    {
        'name': 'March in C with Eighth Notes',
        'description': 'A four-measure march in 2/4 time in C major featuring lively eighth-note patterns.',
        'filename': 'march_c_eighth.mid',
        'tempo': 112,
        'time_signature': '2/4',
        'key_signature': 'C',
        'min_duration': '8',
        'difficulty': 3,
        'tags': ['major-scale', 'stepwise-motion', 'march', 'eighth-notes'],
        'notes': [
            ('c/5', 'q'), ('b/4', '8'), ('a/4', '8'),
            ('g/4', 'q'), ('a/4', '8'), ('b/4', '8'),
            ('c/5', '8'), ('b/4', '8'), ('a/4', '8'), ('g/4', '8'),
            ('c/4', 'h'),
        ],
    },

    # -----------------------------------------------------------------------
    # 6/8  –  eighth-note minimum
    # -----------------------------------------------------------------------
    {
        'name': 'Pastorale in C Major (6/8)',
        'description': 'A flowing four-measure pastorale in 6/8 compound duple time.',
        'filename': 'pastorale_c_major_6_8.mid',
        'tempo': 72,
        'time_signature': '6/8',
        'key_signature': 'C',
        'min_duration': '8',
        'difficulty': 3,
        'tags': ['major-scale', 'stepwise-motion', 'eighth-notes', 'compound-meter'],
        'notes': [
            # m1: dotted-q + three eighths  = 1.5 + 0.5+0.5+0.5 = 3 beats
            ('e/4', 'q', True), ('g/4', '8'), ('e/4', '8'), ('c/4', '8'),
            # m2
            ('d/4', 'q', True), ('f/4', '8'), ('d/4', '8'), ('b/3', '8'),
            # m3: two dotted quarters
            ('c/4', 'q', True), ('e/4', 'q', True),
            # m4
            ('g/4', 'q', True), ('c/4', 'q', True),
        ],
    },
    {
        'name': 'Barcarolle in G Major (6/8)',
        'description': 'A lilting four-measure barcarolle in 6/8 time in G major.',
        'filename': 'barcarolle_g_major_6_8.mid',
        'tempo': 66,
        'time_signature': '6/8',
        'key_signature': 'G',
        'min_duration': '8',
        'difficulty': 3,
        'tags': ['major-scale', 'leap-motion', 'eighth-notes', 'compound-meter'],
        'notes': [
            # m1: dotted-q + three eighths
            ('g/4', 'q', True), ('b/4', '8'), ('d/5', '8'), ('b/4', '8'),
            # m2: two dotted quarters
            ('a/4', 'q', True), ('f#/4', 'q', True),
            # m3: six eighths
            ('g/4', '8'), ('a/4', '8'), ('b/4', '8'), ('c/5', '8'), ('b/4', '8'), ('a/4', '8'),
            # m4: dotted half
            ('g/4', 'h', True),
        ],
    },
    {
        'name': 'Minor Pastorale in A Minor (6/8)',
        'description': 'A gentle four-measure melody in 6/8 time in A minor.',
        'filename': 'pastorale_a_minor_6_8.mid',
        'tempo': 63,
        'time_signature': '6/8',
        'key_signature': 'Am',
        'min_duration': '8',
        'difficulty': 3,
        'tags': ['minor-scale', 'natural-minor', 'eighth-notes', 'compound-meter'],
        'notes': [
            # m1
            ('a/4', 'q', True), ('c/5', '8'), ('b/4', '8'), ('a/4', '8'),
            # m2
            ('g/4', 'q', True), ('e/4', 'q', True),
            # m3: six eighths
            ('f/4', '8'), ('e/4', '8'), ('d/4', '8'), ('e/4', '8'), ('f/4', '8'), ('g/4', '8'),
            # m4
            ('a/4', 'h', True),
        ],
    },

    # -----------------------------------------------------------------------
    # 9/8  –  eighth-note minimum
    # -----------------------------------------------------------------------
    {
        'name': 'Compound Triple in C Major (9/8)',
        'description': 'A four-measure melody in 9/8 compound triple time in C major.',
        'filename': 'compound_triple_c_9_8.mid',
        'tempo': 60,
        'time_signature': '9/8',
        'key_signature': 'C',
        'min_duration': '8',
        'difficulty': 4,
        'tags': ['major-scale', 'stepwise-motion', 'eighth-notes', 'compound-meter'],
        'notes': [
            # m1: dotted-q + 2 eighths + dotted-q + 1 eighth  = 1.5+0.5+0.5+1.5+0.5 = 4.5 beats
            ('c/5', 'q', True), ('b/4', '8'), ('a/4', '8'), ('g/4', 'q', True), ('e/4', '8'),
            # m2: three dotted quarters = 4.5
            ('f/4', 'q', True), ('a/4', 'q', True), ('c/5', 'q', True),
            # m3
            ('e/5', 'q', True), ('d/5', '8'), ('c/5', '8'), ('b/4', 'q', True), ('a/4', '8'),
            # m4
            ('g/4', 'q', True), ('e/4', 'q', True), ('c/4', 'q', True),
        ],
    },
    {
        'name': 'Lyric Melody in F Major (9/8)',
        'description': 'A four-measure lyrical melody in 9/8 time in F major.',
        'filename': 'lyric_f_major_9_8.mid',
        'tempo': 58,
        'time_signature': '9/8',
        'key_signature': 'F',
        'min_duration': '8',
        'difficulty': 4,
        'tags': ['major-scale', 'stepwise-motion', 'eighth-notes', 'compound-meter'],
        'notes': [
            # m1: 1.5+0.5+0.5+1.5+0.5 = 4.5
            ('f/4', 'q', True), ('g/4', '8'), ('a/4', '8'), ('bb/4', 'q', True), ('c/5', '8'),
            # m2: three dotted quarters
            ('bb/4', 'q', True), ('a/4', 'q', True), ('g/4', 'q', True),
            # m3: nine eighths
            ('a/4', '8'), ('g/4', '8'), ('f/4', '8'), ('g/4', '8'), ('a/4', '8'),
            ('bb/4', '8'), ('c/5', '8'), ('bb/4', '8'), ('a/4', '8'),
            # m4: three dotted quarters
            ('f/4', 'q', True), ('a/4', 'q', True), ('f/4', 'q', True),
        ],
    },

    # -----------------------------------------------------------------------
    # 12/8  –  eighth-note minimum
    # -----------------------------------------------------------------------
    {
        'name': 'Compound Quadruple in C Major (12/8)',
        'description': 'A four-measure melody in 12/8 compound quadruple time in C major.',
        'filename': 'compound_quad_c_12_8.mid',
        'tempo': 54,
        'time_signature': '12/8',
        'key_signature': 'C',
        'min_duration': '8',
        'difficulty': 4,
        'tags': ['major-scale', 'stepwise-motion', 'eighth-notes', 'compound-meter'],
        'notes': [
            # m1: four dotted quarters = 6 beats
            ('c/4', 'q', True), ('e/4', 'q', True), ('g/4', 'q', True), ('e/4', 'q', True),
            # m2: twelve eighths
            ('f/4', '8'), ('g/4', '8'), ('a/4', '8'), ('e/4', '8'), ('f/4', '8'), ('g/4', '8'),
            ('a/4', '8'), ('b/4', '8'), ('c/5', '8'), ('b/4', '8'), ('a/4', '8'), ('g/4', '8'),
            # m3: four dotted quarters
            ('g/4', 'q', True), ('f/4', 'q', True), ('e/4', 'q', True), ('c/4', 'q', True),
            # m4: two dotted halves = 3+3 = 6
            ('g/4', 'h', True), ('c/4', 'h', True),
        ],
    },
    {
        'name': 'Lyric Melody in A Minor (12/8)',
        'description': 'A flowing four-measure melody in 12/8 time in A minor.',
        'filename': 'lyric_a_minor_12_8.mid',
        'tempo': 50,
        'time_signature': '12/8',
        'key_signature': 'Am',
        'min_duration': '8',
        'difficulty': 4,
        'tags': ['minor-scale', 'natural-minor', 'stepwise-motion', 'eighth-notes', 'compound-meter'],
        'notes': [
            # m1: four dotted quarters
            ('a/4', 'q', True), ('c/5', 'q', True), ('e/5', 'q', True), ('d/5', 'q', True),
            # m2: twelve eighths descending
            ('c/5', '8'), ('b/4', '8'), ('a/4', '8'), ('g/4', '8'), ('f/4', '8'), ('e/4', '8'),
            ('d/4', '8'), ('e/4', '8'), ('f/4', '8'), ('g/4', '8'), ('a/4', '8'), ('b/4', '8'),
            # m3: four dotted quarters
            ('c/5', 'q', True), ('a/4', 'q', True), ('g/4', 'q', True), ('e/4', 'q', True),
            # m4: two dotted halves
            ('e/4', 'h', True), ('a/4', 'h', True),
        ],
    },

    # -----------------------------------------------------------------------
    # Tied-note melody
    # -----------------------------------------------------------------------
    {
        'name': 'Crossing the Bar (C Major)',
        'description': 'A simple two-measure melody in C major where G4 is held across the barline — '
                       'the held note sounds like a dotted half but spans two measures.',
        'filename': 'tied_c_major.mid',
        'tempo': 84,
        'time_signature': '4/4',
        'key_signature': 'C',
        'clef': 'treble',
        'min_duration': 'q',
        'difficulty': 2,
        'tags': ['major-scale', 'stepwise-motion', 'tied-notes'],
        # Dict format: tieStart/tieEnd flags are preserved in notes_json
        # and the MIDI writer merges tied pairs into a single sustained note.
        'notes': [
            # m1: c/4(q) + e/4(q) + g/4(h, tieStart)  = 1+1+2 = 4 beats
            {'key': 'c/4', 'duration': 'q'},
            {'key': 'e/4', 'duration': 'q'},
            {'key': 'g/4', 'duration': 'h', 'tieStart': True},
            # m2: g/4(q, tieEnd) + f/4(q) + e/4(q) + d/4(q)  = 1+1+1+1 = 4 beats
            # The tied g/4 sounds for 3 beats total (half + quarter) before releasing.
            {'key': 'g/4', 'duration': 'q', 'tieEnd': True},
            {'key': 'f/4', 'duration': 'q'},
            {'key': 'e/4', 'duration': 'q'},
            {'key': 'd/4', 'duration': 'q'},
        ],
    },

    # -----------------------------------------------------------------------
    # Bass clef melodies
    # -----------------------------------------------------------------------
    {
        'name': 'C Major Scale in Bass Clef',
        'description': 'Eight quarter notes ascending the C major scale in bass clef.',
        'filename': 'bass_c_major_scale.mid',
        'tempo': 90,
        'time_signature': '4/4',
        'key_signature': 'C',
        'clef': 'bass',
        'min_duration': 'q',
        'difficulty': 1,
        'tags': ['major-scale', 'stepwise-motion', 'simple'],
        'notes': [
            ('c/3', 'q'), ('d/3', 'q'), ('e/3', 'q'), ('f/3', 'q'),
            ('g/3', 'q'), ('a/3', 'q'), ('b/3', 'q'), ('c/4', 'q'),
        ],
    },
    {
        'name': 'Simple Melody in G Major (Bass Clef)',
        'description': 'A two-measure melody in G major for bass clef with quarter and eighth notes.',
        'filename': 'bass_g_major_melody.mid',
        'tempo': 96,
        'time_signature': '4/4',
        'key_signature': 'G',
        'clef': 'bass',
        'min_duration': '8',
        'difficulty': 3,
        'tags': ['major-scale', 'stepwise-motion', 'leap-motion', 'eighth-notes'],
        'notes': [
            ('g/2', 'q'), ('b/2', 'q'), ('d/3', 'q'), ('g/3', 'q'),
            ('f#/3', 'q'), ('e/3', '8'), ('d/3', '8'), ('c/3', 'h'),
        ],
    },
    {
        'name': 'Waltz in F Major (Bass Clef)',
        'description': 'A four-measure waltz in 3/4 time in F major for bass clef.',
        'filename': 'bass_f_major_waltz.mid',
        'tempo': 120,
        'time_signature': '3/4',
        'key_signature': 'F',
        'clef': 'bass',
        'min_duration': 'q',
        'difficulty': 2,
        'tags': ['major-scale', 'leap-motion', 'waltz'],
        'notes': [
            ('f/2', 'q'), ('a/2', 'q'), ('c/3', 'q'),
            ('d/3', 'q'), ('c/3', 'q'), ('bb/2', 'q'),
            ('a/2', 'h'), ('g/2', 'q'),
            ('f/2', 'h', True),
        ],
    },

    # -----------------------------------------------------------------------
    # Tenor clef melody
    # -----------------------------------------------------------------------
    {
        'name': 'Melody in C Major (Tenor Clef)',
        'description': 'A two-measure melody in C major written in tenor clef.',
        'filename': 'tenor_c_major_melody.mid',
        'tempo': 92,
        'time_signature': '4/4',
        'key_signature': 'C',
        'clef': 'tenor',
        'min_duration': 'q',
        'difficulty': 3,
        'tags': ['major-scale', 'stepwise-motion', 'leap-motion'],
        'notes': [
            ('e/3', 'q'), ('g/3', 'q'), ('c/4', 'q'), ('b/3', 'q'),
            ('a/3', 'h'), ('g/3', 'q'), ('e/3', 'q'),
        ],
    },
]

# ---------------------------------------------------------------------------
# Tags to create (superset of all melody tags)
# ---------------------------------------------------------------------------

ALL_TAGS = {
    'major-scale':      'Uses the major (Ionian) scale exclusively.',
    'minor-scale':      'Uses a minor scale.',
    'natural-minor':    'Uses the natural minor (Aeolian) scale.',
    'harmonic-minor':   'Uses the harmonic minor scale (raised 7th).',
    'melodic-minor':    'Uses the melodic minor scale.',
    'stepwise-motion':  'Melody moves primarily by step (2nds).',
    'leap-motion':      'Melody contains intervals larger than a 2nd.',
    'neapolitan-b2':    'Features the Neapolitan chord / flat-2 scale degree.',
    'chromatic':        'Contains chromatic (non-diatonic) notes.',
    'simple':           'Entry-level melody suitable for beginners.',
    'intermediate':     'Intermediate-level melody.',
    'eighth-notes':     'Contains eighth notes as the shortest rhythmic value.',
    'sixteenth-notes':  'Contains sixteenth notes as the shortest rhythmic value.',
    'compound-meter':   'Uses compound meter (6/8, 9/8, or 12/8).',
    'waltz':            'Three-beat waltz feel in 3/4 time.',
    'march':            'Two-beat march feel in 2/4 time.',
    'tied-notes':       'Contains notes tied across a barline.',
}


# ---------------------------------------------------------------------------
# Seed the database
# ---------------------------------------------------------------------------

def seed():
    from app import app
    from models import db, Tag, Melody

    with app.app_context():
        db.create_all()

        # Create / update tags
        tag_objects = {}
        for name, desc in ALL_TAGS.items():
            tag = Tag.query.filter_by(name=name).first()
            if tag is None:
                tag = Tag(name=name, description=desc)
                db.session.add(tag)
            else:
                tag.description = desc
            tag_objects[name] = tag
        db.session.flush()

        # Create / update melodies
        for m in MELODIES:
            existing = Melody.query.filter_by(name=m['name']).first()

            notes_json    = notes_to_json(m['notes'])
            time_sig      = m.get('time_signature', '4/4')
            min_dur       = m.get('min_duration', 'q')
            key_sig       = m.get('key_signature', 'C')
            clef          = m.get('clef', 'treble')
            difficulty    = m.get('difficulty', 1)
            tempo         = m.get('tempo', 100)
            # Set skip_midi=True when you supply your own MIDI file (e.g. from Logic Pro)
            # so generate_midi.py won't overwrite it.
            skip_midi     = m.get('skip_midi', False)

            if existing:
                print(f'  Updating: {m["name"]}')
                existing.notes_json      = notes_json
                existing.time_signature  = time_sig
                existing.min_duration    = min_dur
                existing.key_signature   = key_sig
                existing.clef            = clef
                existing.difficulty      = difficulty
                existing.tempo           = tempo
                existing.description     = m['description']
                existing.midi_filename   = m['filename']
                existing.tags            = [tag_objects[t] for t in m['tags']]
                if not skip_midi:
                    write_midi(m['filename'], m['notes'], tempo=tempo)
                else:
                    print(f'    (skipping MIDI write — using existing file)')
            else:
                print(f'  Creating: {m["name"]}')
                if not skip_midi:
                    write_midi(m['filename'], m['notes'], tempo=tempo)
                else:
                    midi_path = os.path.join(MIDI_DIR, m['filename'])
                    if not os.path.exists(midi_path):
                        print(f'    WARNING: skip_midi=True but {midi_path} not found!')
                    else:
                        print(f'    (using existing MIDI file)')
                melody = Melody(
                    name            = m['name'],
                    description     = m['description'],
                    midi_filename   = m['filename'],
                    notes_json      = notes_json,
                    time_signature  = time_sig,
                    key_signature   = key_sig,
                    clef            = clef,
                    min_duration    = min_dur,
                    difficulty      = difficulty,
                    tempo           = tempo,
                )
                melody.tags = [tag_objects[t] for t in m['tags']]
                db.session.add(melody)

        db.session.commit()
        print('Done.')


if __name__ == '__main__':
    seed()
