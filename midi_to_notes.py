"""
midi_to_notes.py
================
Parse a MIDI file (e.g. exported from Logic Pro) and print the notes in the
format needed by the Musicianship Trainer.

Usage:
    python3 midi_to_notes.py path/to/file.mid [track_index]

    track_index defaults to the first track that contains note events.

Requirements:
    pip install mido

Output:
  1. notes_json  — the JSON string to paste into the `notes_json` column in
                   DB Browser. This is all you need for a manual DB insert.

  2. Python tuples — only needed if you want to add the melody to
                     generate_midi.py as a backup. You can ignore this section
                     once the melody is in the database.

Workflow (DB Browser, no generate_midi.py required):
  1. Export MIDI from Logic Pro → drop into static/midi/
  2. Run this script → copy the notes_json line
  3. In DB Browser: Insert Row into the `melody` table, paste the JSON
     into `notes_json`, fill in the other fields manually.
  4. In `melody_tags`: add rows linking your new melody id to tag ids.
"""

import sys
import os

try:
    import mido
except ImportError:
    print("mido is not installed.  Run:  pip install mido")
    sys.exit(1)


# ---------------------------------------------------------------------------
# MIDI pitch → VexFlow note name
# Using sharps by default; edit PREFER_FLATS to switch.
# ---------------------------------------------------------------------------
PREFER_FLATS = False   # set True to get bb/4 instead of a#/4, etc.

SHARP_NAMES = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b']
FLAT_NAMES  = ['c', 'db', 'd', 'eb', 'e', 'f', 'gb', 'g', 'ab', 'a', 'bb', 'b']

def midi_to_vex(midi_note):
    octave    = (midi_note // 12) - 1
    pc        = midi_note % 12
    name      = (FLAT_NAMES if PREFER_FLATS else SHARP_NAMES)[pc]
    return f'{name}/{octave}'


# ---------------------------------------------------------------------------
# Duration snapping
# ---------------------------------------------------------------------------
# Standard durations in quarter-note beat fractions
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
        { 'type': 'note'|'rest', 'midi': int, 'beats': float, 'dotted': bool, 'dur': str }
    """
    mid = mido.MidiFile(midi_file)
    tpb = mid.ticks_per_beat   # ticks per quarter note

    # Pick the track with the most note events if not specified
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

    # Collect (tick, type, note, velocity) events in absolute time
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

    # Build (start_tick, end_tick, midi_note) tuples
    note_on_ticks = {}   # midi_note → abs_tick
    note_spans    = []   # (start_tick, end_tick, midi_note)
    for tick, etype, note in events:
        if etype == 'on':
            note_on_ticks[note] = tick
        elif note in note_on_ticks:
            note_spans.append((note_on_ticks.pop(note), tick, note))

    note_spans.sort()

    # Insert rests between consecutive notes
    result      = []
    cursor_tick = note_spans[0][0] if note_spans else 0

    for start, end, midi_note in note_spans:
        # Gap before this note → rest
        gap_beats = (start - cursor_tick) / tpb
        if gap_beats > 0.05:   # ignore sub-16th gaps (articulation / timing slop)
            dur, dotted = snap_duration(gap_beats)
            result.append({'type': 'rest', 'midi': None, 'beats': gap_beats,
                           'dur': dur, 'dotted': dotted})

        # The note itself
        note_beats = (end - start) / tpb
        dur, dotted = snap_duration(note_beats)
        result.append({'type': 'note', 'midi': midi_note, 'beats': note_beats,
                       'dur': dur, 'dotted': dotted})

        cursor_tick = end

    return result


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def build_json_list(notes):
    """Return the list of dicts that becomes notes_json in the DB."""
    result = []
    for n in notes:
        if n['type'] == 'rest':
            entry = {'key': 'b/4', 'duration': n['dur'] + 'r'}
        else:
            entry = {'key': midi_to_vex(n['midi']), 'duration': n['dur']}
        if n['dotted']:
            entry['dotted'] = True
        result.append(entry)
    return result


def print_output(notes):
    import json

    note_list = build_json_list(notes)
    dur_values = sorted({n['dur'] for n in notes})

    # --- PRIMARY OUTPUT: notes_json for DB Browser -------------------------
    print()
    print("=" * 60)
    print("PASTE INTO notes_json COLUMN IN DB BROWSER:")
    print("=" * 60)
    print(json.dumps(note_list))

    # --- DB Browser field guide --------------------------------------------
    print()
    print("=" * 60)
    print("OTHER FIELDS TO FILL IN (melody table):")
    print("=" * 60)
    print("  name            →  (your melody name)")
    print("  description     →  (optional description)")
    print("  midi_filename   →  (e.g.  my_melody.mid)")
    print("  time_signature  →  4/4  3/4  2/4  6/8  9/8  12/8")
    print("  key_signature   →  C  G  D  A  F  Bb  Eb  Am  Dm  ...")
    print("  clef            →  treble  bass  tenor")
    print(f"  min_duration    →  {dur_values[0]}  (shortest note detected: {dur_values})")
    print("  difficulty      →  1–5")
    print("  tempo           →  (BPM from Logic Pro)")

    # --- SECONDARY OUTPUT: Python tuples for generate_midi.py backup ------
    print()
    print("=" * 60)
    print("OPTIONAL: Python tuples for generate_midi.py backup")
    print("=" * 60)
    print("'notes': [")
    for n in notes:
        if n['type'] == 'rest':
            dur_str = n['dur'] + 'r'
            dotted  = ', True' if n['dotted'] else ''
            print(f"    ('{dur_str}', '{n['dur']}'{dotted}),")
        else:
            key    = midi_to_vex(n['midi'])
            dotted = ', True' if n['dotted'] else ''
            print(f"    ('{key}', '{n['dur']}'{dotted}),")
    print("],")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    midi_path = sys.argv[1]
    if not os.path.exists(midi_path):
        print(f'File not found: {midi_path}')
        sys.exit(1)

    track_idx = int(sys.argv[2]) if len(sys.argv) > 2 else None
    notes     = extract_notes(midi_path, track_idx)
    print_output(notes)
