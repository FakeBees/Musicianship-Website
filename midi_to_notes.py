"""
midi_to_notes.py
================
Parse a MIDI file (e.g. exported from Logic Pro) and produce the note list
in the format needed by the Musicianship Trainer.

Key-aware note naming
---------------------
Pass the key so that diatonic notes are always spelled correctly (e.g. Eb in
Bb major, not D#) and chromatic/accidental notes follow the resolution
heuristic:
  * sharp  if the next note is higher in pitch  (ascending tendency)
  * flat   if the next note is lower in pitch   (descending tendency)
  * key's accidental tendency as a fallback

Usage:
    python3 midi_to_notes.py path/to/file.mid [track_index] [--key Bb]

    track_index defaults to the first track that contains note events.
    --key defaults to C if omitted.

Requirements:
    pip install mido
"""

import json
import os
import sys

try:
    import mido
except ImportError:
    print("mido is not installed.  Run:  pip install mido")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Key-aware note naming
# ---------------------------------------------------------------------------

# Diatonic pitch-class → VexFlow note name for every supported key.
# Minor keys share the same diatonic set as their relative major.
DIATONIC_PC_MAP = {
    # ── Major keys ──────────────────────────────────────────────────────────
    'C':   {0:'c',  2:'d',  4:'e',  5:'f',  7:'g',  9:'a',  11:'b'},
    'G':   {0:'c',  2:'d',  4:'e',  6:'f#', 7:'g',  9:'a',  11:'b'},
    'D':   {1:'c#', 2:'d',  4:'e',  6:'f#', 7:'g',  9:'a',  11:'b'},
    'A':   {1:'c#', 2:'d',  4:'e',  6:'f#', 8:'g#', 9:'a',  11:'b'},
    'E':   {1:'c#', 3:'d#', 4:'e',  6:'f#', 8:'g#', 9:'a',  11:'b'},
    'B':   {1:'c#', 3:'d#', 4:'e',  6:'f#', 8:'g#', 10:'a#', 11:'b'},
    'F#':  {1:'c#', 3:'d#', 5:'f',  6:'f#', 8:'g#', 10:'a#', 11:'b'},  # E# → F
    'F':   {0:'c',  2:'d',  4:'e',  5:'f',  7:'g',  9:'a',  10:'bb'},
    'Bb':  {0:'c',  2:'d',  3:'eb', 5:'f',  7:'g',  9:'a',  10:'bb'},
    'Eb':  {0:'c',  2:'d',  3:'eb', 5:'f',  7:'g',  8:'ab', 10:'bb'},
    'Ab':  {0:'c',  1:'db', 3:'eb', 5:'f',  7:'g',  8:'ab', 10:'bb'},
    'Db':  {0:'c',  1:'db', 3:'eb', 5:'f',  6:'gb', 8:'ab', 10:'bb'},
    'Gb':  {1:'db', 3:'eb', 5:'f',  6:'gb', 8:'ab', 10:'bb', 11:'b'},  # Cb → B
    # ── Minor keys (natural minor — same diatonic set as relative major) ───
    'Am':  {0:'c',  2:'d',  4:'e',  5:'f',  7:'g',  9:'a',  11:'b'},
    'Em':  {0:'c',  2:'d',  4:'e',  6:'f#', 7:'g',  9:'a',  11:'b'},
    'Bm':  {1:'c#', 2:'d',  4:'e',  6:'f#', 7:'g',  9:'a',  11:'b'},
    'F#m': {1:'c#', 2:'d',  4:'e',  6:'f#', 8:'g#', 9:'a',  11:'b'},
    'C#m': {1:'c#', 3:'d#', 4:'e',  6:'f#', 8:'g#', 9:'a',  11:'b'},
    'G#m': {1:'c#', 3:'d#', 4:'e',  6:'f#', 8:'g#', 10:'a#', 11:'b'},
    'Dm':  {0:'c',  2:'d',  4:'e',  5:'f',  7:'g',  9:'a',  10:'bb'},
    'Gm':  {0:'c',  2:'d',  3:'eb', 5:'f',  7:'g',  9:'a',  10:'bb'},
    'Cm':  {0:'c',  2:'d',  3:'eb', 5:'f',  7:'g',  8:'ab', 10:'bb'},
    'Fm':  {0:'c',  1:'db', 3:'eb', 5:'f',  7:'g',  8:'ab', 10:'bb'},
    'Bbm': {0:'c',  1:'db', 3:'eb', 5:'f',  6:'gb', 8:'ab', 10:'bb'},
    'Ebm': {1:'db', 3:'eb', 5:'f',  6:'gb', 8:'ab', 10:'bb', 11:'b'},
}

SHARP_NAMES = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b']
FLAT_NAMES  = ['c', 'db', 'd', 'eb', 'e', 'f', 'gb', 'g', 'ab', 'a', 'bb', 'b']

# Keys whose accidental tendency is flat (used as fallback for chromatic notes)
FLAT_TENDENCY_KEYS = {'F', 'Bb', 'Eb', 'Ab', 'Db', 'Gb',
                      'Dm', 'Gm', 'Cm', 'Fm', 'Bbm', 'Ebm'}


def note_to_vex(midi_note, next_midi, key='C'):
    """
    Convert a MIDI note number to a VexFlow note string (e.g. 'eb/4').

    Priority:
      1. Diatonic in the key → always use the key's spelling.
      2. Chromatic + next note is higher → spell as sharp (ascending tendency).
      3. Chromatic + next note is lower  → spell as flat  (descending tendency).
      4. Chromatic with no context       → fall back to the key's accidental tendency.
    """
    pc     = midi_note % 12
    octave = (midi_note // 12) - 1
    pc_map = DIATONIC_PC_MAP.get(key, DIATONIC_PC_MAP['C'])

    if pc in pc_map:
        # Diatonic note — always use the key's spelling
        name = pc_map[pc]
    else:
        # Chromatic note — resolution heuristic, then key tendency
        use_flat = key in FLAT_TENDENCY_KEYS
        if next_midi is not None:
            if next_midi > midi_note:
                use_flat = False   # ascending → sharp
            elif next_midi < midi_note:
                use_flat = True    # descending → flat
        name = FLAT_NAMES[pc] if use_flat else SHARP_NAMES[pc]

    return f'{name}/{octave}'


# ---------------------------------------------------------------------------
# Duration snapping
# ---------------------------------------------------------------------------

DURATIONS = [
    (4.0,   'w'),
    (2.0,   'h'),
    (1.0,   'q'),
    (0.5,   '8'),
    (0.25,  '16'),
    # dotted versions (1.5×)
    (3.0,   ('h', True)),   # dotted half
    (1.5,   ('q', True)),   # dotted quarter
    (0.75,  ('8', True)),   # dotted eighth
]

SNAP_TOLERANCE = 0.15   # fraction of a beat; tune if needed

# Minimum raw gap (in beats) before we consider inserting a rest.
# At 120 BPM, 0.1 beat ≈ 50 ms — well above typical DAW timing slop from
# staccato playing or slight lateness, but small enough to catch a real 16th-
# note rest (0.25 beats).
MINIMUM_REST_BEATS = 0.1

# Beat values for each duration string — used to filter out spurious rests
# that snap to something smaller than a 16th note.
DURATION_BEAT_VALUES = {'w': 4.0, 'h': 2.0, 'q': 1.0, '8': 0.5, '16': 0.25}


def snap_duration(beats):
    """Return (dur_string, dotted) snapped to the nearest standard value."""
    best      = None
    best_dist = float('inf')
    for val, dur in DURATIONS:
        dist = abs(beats - val)
        if dist < best_dist:
            best_dist = dist
            best      = dur

    if best_dist > SNAP_TOLERANCE:
        print(f'  WARNING: could not snap {beats:.3f} beats to a standard '
              f'duration (closest: {best}, dist={best_dist:.3f})',
              file=sys.stderr)

    if isinstance(best, tuple):
        return best[0], best[1]
    return best, False


# ---------------------------------------------------------------------------
# MIDI parsing
# ---------------------------------------------------------------------------

def extract_notes(midi_file, track_idx=None):
    """
    Returns a list of dicts:
        { 'type': 'note'|'rest', 'midi': int|None, 'beats': float,
          'dotted': bool, 'dur': str }

    Rests are only inserted when the gap between consecutive notes is both:
      • >= MINIMUM_REST_BEATS (filters out staccato/lateness slop), and
      • snaps to a duration >= a 16th note (filters out sub-16th phantom rests).
    """
    mid = mido.MidiFile(midi_file)
    tpb = mid.ticks_per_beat

    if track_idx is None:
        best_track = 0
        best_count = 0
        for i, track in enumerate(mid.tracks):
            count = sum(1 for msg in track if msg.type in ('note_on', 'note_off'))
            if count > best_count:
                best_count, best_track = count, i
        track_idx = best_track
        print(f'Using track {track_idx}: "{mid.tracks[track_idx].name}"',
              file=sys.stderr)

    track = mid.tracks[track_idx]

    events = []
    abs_tick = 0
    for msg in track:
        abs_tick += msg.time
        if msg.type == 'note_on' and msg.velocity > 0:
            events.append((abs_tick, 'on',  msg.note))
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            events.append((abs_tick, 'off', msg.note))

    if not events:
        print('No note events found in that track.', file=sys.stderr)
        return []

    note_on_ticks = {}
    note_spans    = []
    for tick, etype, note in events:
        if etype == 'on':
            note_on_ticks[note] = tick
        elif note in note_on_ticks:
            note_spans.append((note_on_ticks.pop(note), tick, note))

    note_spans.sort()

    result      = []
    cursor_tick = note_spans[0][0] if note_spans else 0

    for start, end, midi_note in note_spans:
        gap_beats = (start - cursor_tick) / tpb
        if gap_beats >= MINIMUM_REST_BEATS:
            dur, dotted = snap_duration(gap_beats)
            # Only insert rest if it represents a meaningful duration
            # (>= a 16th note).  Smaller snapped values are timing noise.
            beat_val = DURATION_BEAT_VALUES.get(dur, 0.0) * (1.5 if dotted else 1.0)
            if beat_val >= 0.25:
                result.append({'type': 'rest', 'midi': None, 'beats': gap_beats,
                               'dur': dur, 'dotted': dotted})

        note_beats = (end - start) / tpb
        dur, dotted = snap_duration(note_beats)
        result.append({'type': 'note', 'midi': midi_note, 'beats': note_beats,
                       'dur': dur, 'dotted': dotted})

        cursor_tick = end

    return result


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def build_json_list(notes, key='C'):
    """
    Return the list of dicts that becomes notes_json in the DB.

    key is used for enharmonic spelling: diatonic notes always use the key's
    spelling; chromatic accidentals follow the resolution heuristic.
    """
    result = []
    for i, n in enumerate(notes):
        # Find the next non-rest note for the chromatic resolution heuristic
        next_midi = None
        for j in range(i + 1, len(notes)):
            if notes[j]['type'] == 'note':
                next_midi = notes[j]['midi']
                break

        if n['type'] == 'rest':
            entry = {'key': 'b/4', 'duration': n['dur'] + 'r'}
        else:
            entry = {
                'key':      note_to_vex(n['midi'], next_midi, key),
                'duration': n['dur'],
            }
        if n['dotted']:
            entry['dotted'] = True
        result.append(entry)
    return result


def print_output(notes, key='C'):
    note_list  = build_json_list(notes, key)
    dur_values = sorted({n['dur'] for n in notes})

    print()
    print("=" * 60)
    print("PASTE INTO notes_json COLUMN IN DB BROWSER:")
    print("=" * 60)
    print(json.dumps(note_list))

    print()
    print("=" * 60)
    print("OTHER FIELDS TO FILL IN (melody table):")
    print("=" * 60)
    print("  name            →  (your melody name)")
    print("  description     →  (optional description)")
    print("  midi_filename   →  (e.g.  my_melody.mid)")
    print("  time_signature  →  4/4  3/4  2/4  6/8  9/8  12/8")
    print(f"  key_signature   →  {key}  (passed via --key flag)")
    print("  clef            →  treble  bass  tenor")
    print(f"  min_duration    →  {dur_values[0]}  (shortest note detected: {dur_values})")
    print("  difficulty      →  1–5")
    print("  tempo           →  (BPM from Logic Pro)")

    print()
    print("=" * 60)
    print("OPTIONAL: Python tuples for generate_midi.py backup")
    print("=" * 60)
    print("'notes': [")
    for i, n in enumerate(notes):
        next_midi = None
        for j in range(i + 1, len(notes)):
            if notes[j]['type'] == 'note':
                next_midi = notes[j]['midi']
                break
        if n['type'] == 'rest':
            dur_str = n['dur'] + 'r'
            dotted  = ', True' if n['dotted'] else ''
            print(f"    ('{dur_str}', '{n['dur']}'{dotted}),")
        else:
            vex    = note_to_vex(n['midi'], next_midi, key)
            dotted = ', True' if n['dotted'] else ''
            print(f"    ('{vex}', '{n['dur']}'{dotted}),")
    print("],")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    # Parse args: positional midi_path + optional track_idx + optional --key KEY
    args = sys.argv[1:]
    key  = 'C'
    if '--key' in args:
        idx  = args.index('--key')
        key  = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    midi_path = args[0]
    if not os.path.exists(midi_path):
        print(f'File not found: {midi_path}')
        sys.exit(1)

    track_idx = int(args[1]) if len(args) > 1 else None
    notes     = extract_notes(midi_path, track_idx)
    print_output(notes, key)
