"""
melody_generator.py
===================
Rule/constraint melody generator.  No ML; every note traces to a music-theory rule.

Public API
----------
generate(params: dict) -> dict
    params keys: key, mode, gen_progression_id, time_sig, num_measures,
                 min_duration, clef, start_midi, high_midi, low_midi,
                 techniques (list[str]), rhythm_complexity (1–3),
                 syncopation (bool), seed (int|None)
    returns: {notes_json, midi_path, difficulty_suggestion, auto_tags, generation_params}
"""

import json
import os
import random

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')

# ── Pitch-class constants ────────────────────────────────────────────────────

KEY_PC = {
    'C': 0,  'G': 7,  'D': 2,  'A': 9,  'E': 4,  'B': 11, 'F#': 6,
    'F': 5,  'Bb': 10, 'Eb': 3, 'Ab': 8, 'Db': 1, 'Gb': 6,
    'Am': 9, 'Em': 4, 'Bm': 11, 'F#m': 6, 'C#m': 1, 'G#m': 8,
    'Dm': 2, 'Gm': 7, 'Cm': 0, 'Fm': 5, 'Bbm': 10, 'Ebm': 3,
}

# Semitones above tonic for each scale degree (major / natural-minor)
MAJOR_DEGREE_PC = {
    'I': 0, 'II': 2, 'III': 4, 'IV': 5, 'V': 7, 'VI': 9, 'VII': 11,
    'i': 0, 'ii': 2, 'iii': 4, 'iv': 5, 'v': 7, 'vi': 9, 'vii': 11,
}
MINOR_DEGREE_PC = {
    'I': 0, 'i': 0, 'II': 2, 'ii': 2, 'III': 3, 'iii': 3,
    'IV': 5, 'iv': 5, 'V': 7, 'v': 7, 'VI': 8, 'vi': 8,
    'VII': 10, 'vii': 10,
}

CHORD_INTERVALS = {
    'maj':   [0, 4, 7],
    'min':   [0, 3, 7],
    'dim':   [0, 3, 6],
    'aug':   [0, 4, 8],
    'dom7':  [0, 4, 7, 10],
    'maj7':  [0, 4, 7, 11],
    'min7':  [0, 3, 7, 10],
    'dim7':  [0, 3, 6, 9],
    'hdim7': [0, 3, 6, 10],
}

CLEF_RANGE = {
    'treble': (60, 79),   # c/4 – g/5
    'bass':   (36, 55),   # c/2 – g/3
    'tenor':  (48, 67),   # c/3 – g/4
}

BEAT_VALUES = {'w': 4.0, 'h': 2.0, 'q': 1.0, '8': 0.5, '16': 0.25}
DUR_ORDER   = ['16', '8', 'q', 'h', 'w']   # shortest → longest

# ── Harmony ──────────────────────────────────────────────────────────────────

def realize_harmony(chords: list, key: str, mode: str) -> list:
    """
    Translate key-agnostic scale-degree chords into pitch-class sets.

    Returns list of dicts:
      {chord_pcs: set[int], root_pc: int, quality: str,
       start_beat: float, dur_beats: float}
    """
    tonic_pc  = KEY_PC.get(key, 0)
    degree_pc = MAJOR_DEGREE_PC if mode == 'major' else MINOR_DEGREE_PC
    windows   = []
    beat      = 0.0
    for c in chords:
        degree   = c['degree']
        quality  = c.get('quality', 'maj')
        dur      = float(c.get('beats', 4))
        root_offset = degree_pc.get(degree, 0)
        root_pc  = (tonic_pc + root_offset) % 12
        intervals = CHORD_INTERVALS.get(quality, [0, 4, 7])
        chord_pcs = {(root_pc + i) % 12 for i in intervals}
        windows.append({
            'chord_pcs': chord_pcs,
            'root_pc':   root_pc,
            'quality':   quality,
            'start_beat': beat,
            'dur_beats':  dur,
        })
        beat += dur
    return windows


def chord_tone_midis(root_pc: int, quality: str, low_midi: int, high_midi: int) -> list:
    """Return all MIDI note numbers in [low_midi, high_midi] that are chord tones."""
    intervals = CHORD_INTERVALS.get(quality, [0, 4, 7])
    result = []
    for midi in range(low_midi, high_midi + 1):
        if midi % 12 in {(root_pc + i) % 12 for i in intervals}:
            result.append(midi)
    return result
