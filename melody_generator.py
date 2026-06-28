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


# ── Rhythm skeleton ───────────────────────────────────────────────────────────

def beats_per_measure(time_sig: str) -> float:
    """Quarter-note beat count per measure."""
    num, den = (int(x) for x in time_sig.split('/'))
    return num * (4.0 / den)


def strong_beats(time_sig: str, num_measures: int) -> set:
    """
    Return the set of beat positions (in quarter-note units) that are metrically strong.
    For simple meters: beats 1 and (for 4/4) 3.
    For compound meters (6/8, 9/8, 12/8): dotted-quarter downbeats.
    """
    num, den = (int(x) for x in time_sig.split('/'))
    bpm = beats_per_measure(time_sig)
    result = set()
    for m in range(num_measures):
        bar_start = m * bpm
        if den == 8:
            # Compound: strong on each dotted-quarter group (every 1.5 beats)
            groups = num // 3
            for g in range(groups):
                result.add(bar_start + g * 1.5)
        else:
            # Simple: beat 1 always strong; beat 3 strong in 4/4
            result.add(bar_start)
            if num == 4:
                result.add(bar_start + 2.0)
    return result


def _beat_cells(min_dur: str, complexity: int, syncopation: bool, rng: random.Random) -> list:
    """
    Return a list of (dur, dotted) tuples that fill exactly 1 quarter-note beat.
    """
    if min_dur == 'q' or complexity == 1:
        return [('q', False)]

    cells_q = [
        [('q', False)],
        [('8', False), ('8', False)],
    ]
    if complexity >= 2 and min_dur == '16':
        cells_q.append([('8', True), ('16', False)])  # dotted-8 + 16th (contains 16th)
    if syncopation and complexity >= 2:
        cells_q.append([('8', False), ('8', False)])  # placeholder for tie-syncopation

    if min_dur == '16' and complexity >= 3:
        cells_q.append([('16', False)] * 4)

    return rng.choice(cells_q)


def build_rhythm(time_sig: str, num_measures: int, min_duration: str,
                 complexity: int, syncopation: bool, rng: random.Random) -> list:
    """
    Build a rhythmic skeleton as a list of note slots.

    Each slot: {"beat": float, "dur": str, "dotted": bool, "is_strong": bool}

    All slots together consume exactly num_measures * beats_per_measure(time_sig) beats.
    """
    num, den = (int(x) for x in time_sig.split('/'))
    bpm = beats_per_measure(time_sig)
    sb = strong_beats(time_sig, num_measures)
    total_beats = num_measures * bpm
    slots = []
    beat = 0.0

    if den == 8:
        # Compound meter: work in dotted-quarter units (1.5 beats each)
        dotted_q_count = int(round(total_beats / 1.5))
        for i in range(dotted_q_count):
            is_strong = any(abs(beat - s) < 0.01 for s in sb)
            if complexity <= 1 or (is_strong and rng.random() < 0.5):
                slots.append({'beat': beat, 'dur': 'q', 'dotted': True, 'is_strong': is_strong})
                beat += 1.5
            else:
                for j in range(3):
                    slots.append({'beat': beat, 'dur': '8', 'dotted': False,
                                  'is_strong': is_strong and j == 0})
                    beat += 0.5
    else:
        # Simple meter: work beat by beat
        while beat < total_beats - 0.001:
            is_strong = any(abs(beat - s) < 0.01 for s in sb)
            remaining = total_beats - beat

            # For the last beat, force a quarter if possible
            if remaining <= 1.0 + 0.001 and min_duration in ('q', 'h', 'w'):
                dur_str = 'q' if abs(remaining - 1.0) < 0.01 else '8'
                slots.append({'beat': beat, 'dur': dur_str, 'dotted': False, 'is_strong': is_strong})
                beat += BEAT_VALUES.get(dur_str, 1.0)
                continue

            cell = _beat_cells(min_duration, complexity, syncopation, rng)
            for dur, dotted in cell:
                val = BEAT_VALUES.get(dur, 1.0) * (1.5 if dotted else 1.0)
                slots.append({'beat': beat, 'dur': dur, 'dotted': dotted,
                              'is_strong': is_strong})
                beat += val
                is_strong = False  # only first note in a cell is on the beat

    return slots


# ── Skeleton placement ────────────────────────────────────────────────────────

def active_window(beat: float, windows: list) -> dict:
    """Return the harmonic window that is active at the given beat position."""
    best = windows[0]
    for w in windows:
        if w['start_beat'] <= beat + 0.001:
            best = w
    return best


def _closest_chord_tone(target_midi: int, chord_tone_list: list) -> int:
    """Return the chord tone MIDI closest in pitch to target_midi."""
    if not chord_tone_list:
        return target_midi
    return min(chord_tone_list, key=lambda m: abs(m - target_midi))


def _toward_waypoint(current: int, waypoint: int, chord_tones: list) -> int:
    """
    Pick the chord tone that moves toward the waypoint.
    If above waypoint: prefer lower; if below: prefer higher.
    Among candidates, prefer the smallest step.
    """
    if not chord_tones:
        return current

    def score(m):
        distance_to_wp = abs(m - waypoint)
        step_size = abs(m - current)
        wrong_direction = 5 if (waypoint > current and m < current) or \
                              (waypoint < current and m > current) else 0
        leap_penalty = max(0, step_size - 7) * 3
        return distance_to_wp + step_size * 0.3 + wrong_direction + leap_penalty

    return min(chord_tones, key=score)


def place_skeleton(slots: list, windows: list, contour: dict,
                   clef: str, key: str, rng: random.Random) -> list:
    """
    Fill strong-beat slots with chord tones, leave weak-beat slots as None.

    Modifies slots in-place (adds 'midi' key) and returns the list.
    Contour: {"start_midi": int, "high_midi": int, "low_midi": int}
    """
    low_midi, high_midi = CLEF_RANGE.get(clef, (60, 79))

    prev_midi = contour['start_midi']
    strong_count = sum(1 for s in slots if s['is_strong'])
    strong_idx   = 0

    for s in slots:
        s['midi'] = None
        if not s['is_strong']:
            continue

        win = active_window(s['beat'], windows)
        ct  = chord_tone_midis(win['root_pc'], win['quality'], low_midi, high_midi)

        progress = strong_idx / max(strong_count - 1, 1)
        if progress < 0.6:
            waypoint = contour['high_midi']
        else:
            waypoint = contour['start_midi']

        reachable = [m for m in ct if abs(m - prev_midi) <= 9] or ct

        midi = _toward_waypoint(prev_midi, waypoint, reachable)
        s['midi'] = midi
        prev_midi  = midi
        strong_idx += 1

    return slots
