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


# ── Ornamentation ─────────────────────────────────────────────────────────────

MAJOR_SCALE_INTERVALS = [0, 2, 4, 5, 7, 9, 11]
MINOR_SCALE_INTERVALS = [0, 2, 3, 5, 7, 8, 10]   # natural minor


def key_pcs(key: str, mode: str) -> set:
    """Return the set of pitch classes in the key's diatonic scale."""
    tonic = KEY_PC.get(key, 0)
    intervals = MAJOR_SCALE_INTERVALS if mode == 'major' else MINOR_SCALE_INTERVALS
    return {(tonic + i) % 12 for i in intervals}


def _step_between(midi_a: int, midi_b: int, diatonic_pcs: set):
    """
    Return a diatonic note that fills the interval between midi_a and midi_b by step.
    Works if the interval is a third (3-4 semitones); returns None otherwise.
    """
    diff = midi_b - midi_a
    if abs(diff) not in (3, 4):
        return None
    direction = 1 if diff > 0 else -1
    for semis in [direction, direction * 2]:
        candidate_pc = (midi_a + semis) % 12
        if candidate_pc in diatonic_pcs:
            return midi_a + semis
    return None


def _neighbor(midi: int, diatonic_pcs: set, direction: int = 1) -> int:
    """Return the nearest diatonic neighbor in the given direction (+1 or -1 semitone steps)."""
    for delta in [direction, -direction, 2 * direction, -2 * direction]:
        candidate = midi + delta
        if candidate % 12 in diatonic_pcs and candidate != midi:
            return candidate
    return midi


def apply_techniques(slots: list, windows: list, enabled: list,
                     key: str, mode: str, rng: random.Random) -> tuple:
    """
    Fill weak-beat slots (midi=None) using the enabled ornamentation techniques.

    Priority order (for each weak slot):
      1. passing_tone  - if the surrounding strong notes form a third
      2. neighbor_tone - step away then back
      3. anticipation  - early arrival on next strong tone
      4. escape_tone   - step in wrong direction then leap
      5. appoggiatura  - non-chord tone resolving down to next chord tone
      6. suspension    - hold the previous strong tone (tie)
      fallback         - repeat the previous note

    Returns (updated_slots, list_of_technique_names_actually_inserted).
    """
    diatonic = key_pcs(key, mode)
    used_techniques = set()
    n = len(slots)

    for i, s in enumerate(slots):
        if s['midi'] is not None or s['dur'].endswith('r'):
            continue

        # Find surrounding strong-beat notes
        prev_midi = next((slots[j]['midi'] for j in range(i - 1, -1, -1)
                         if slots[j]['midi'] is not None), None)
        next_midi = next((slots[j]['midi'] for j in range(i + 1, n)
                         if slots[j]['midi'] is not None), None)

        win = active_window(s['beat'], windows)
        chosen = None

        # 1. Passing tone
        if 'passing_tone' in enabled and prev_midi and next_midi:
            pt = _step_between(prev_midi, next_midi, diatonic)
            if pt is not None:
                chosen = pt
                used_techniques.add('passing_tone')

        # 2. Neighbor tone
        if chosen is None and 'neighbor_tone' in enabled and prev_midi:
            nb_dir = rng.choice([1, -1])
            nb = _neighbor(prev_midi, diatonic, nb_dir)
            if nb != prev_midi:
                chosen = nb
                used_techniques.add('neighbor_tone')

        # 3. Anticipation (early arrival on next strong tone)
        if chosen is None and 'anticipation' in enabled and next_midi:
            if rng.random() < 0.4:
                chosen = next_midi
                used_techniques.add('anticipation')

        # 4. Escape tone (step opposite direction to next note, then leap resolves)
        if chosen is None and 'escape_tone' in enabled and prev_midi and next_midi:
            diff = next_midi - prev_midi
            escape_dir = -1 if diff > 0 else 1
            esc = _neighbor(prev_midi, diatonic, escape_dir)
            if esc != prev_midi and abs(esc - next_midi) <= 9:
                chosen = esc
                used_techniques.add('escape_tone')

        # 5. Appoggiatura (accented non-chord tone resolving to chord tone)
        if chosen is None and 'appoggiatura' in enabled and next_midi:
            ct = {(win['root_pc'] + interval) % 12
                  for interval in CHORD_INTERVALS.get(win['quality'], [0, 4, 7])}
            if next_midi % 12 in ct:
                for delta in [1, 2, -1, -2]:
                    candidate = next_midi + delta
                    if candidate % 12 not in ct and candidate % 12 in diatonic:
                        chosen = candidate
                        used_techniques.add('appoggiatura')
                        break

        # 6. Suspension (repeat previous strong tone)
        if chosen is None and 'suspension' in enabled and prev_midi:
            if rng.random() < 0.3:
                chosen = prev_midi
                used_techniques.add('suspension')

        # Fallback: repeat previous note
        if chosen is None:
            chosen = prev_midi if prev_midi is not None else (next_midi or 60)

        s['midi'] = chosen

    return slots, list(used_techniques)


# ── Auto-tagging and difficulty ───────────────────────────────────────────────

TECHNIQUE_TAGS = {
    'passing_tone':  'passing-tone',
    'neighbor_tone': 'neighbor-tone',
    'appoggiatura':  'appoggiatura',
    'suspension':    'suspension',
    'anticipation':  'anticipation',
    'escape_tone':   'escape-tone',
}

TECHNIQUE_DIFFICULTY = {
    'passing_tone':  0.5, 'neighbor_tone': 0.5,
    'appoggiatura':  1.5, 'suspension':    1.5,
    'anticipation':  1.0, 'escape_tone':   1.0,
}

TIME_SIG_TAGS = {
    '3/4': ['waltz'], '2/4': ['march'],
    '6/8': ['compound-meter'], '9/8': ['compound-meter'], '12/8': ['compound-meter'],
}

MIN_DUR_TAGS = {
    '8':  ['eighth-notes'], '16': ['sixteenth-notes'],
}


def auto_tags(params: dict, techniques_used: list) -> list:
    tags = []
    tags += TIME_SIG_TAGS.get(params.get('time_sig', '4/4'), [])
    tags += MIN_DUR_TAGS.get(params.get('min_duration', 'q'), [])
    if params.get('clef') == 'bass':
        tags.append('bass-clef')
    elif params.get('clef') == 'tenor':
        tags.append('tenor-clef')
    if params.get('mode') == 'minor':
        tags.append('minor-scale')
    else:
        tags.append('major-scale')
    for t in techniques_used:
        tag = TECHNIQUE_TAGS.get(t)
        if tag:
            tags.append(tag)
    return list(dict.fromkeys(tags))   # deduplicate, preserve order


def suggest_difficulty(slots: list, techniques_used: list, gen_prog_difficulty: int = 1) -> int:
    score = gen_prog_difficulty * 0.5
    for t in techniques_used:
        score += TECHNIQUE_DIFFICULTY.get(t, 0.5)
    # Count leaps > 4 semitones
    midis = [s['midi'] for s in slots if s.get('midi') is not None]
    for i in range(1, len(midis)):
        if abs(midis[i] - midis[i - 1]) > 4:
            score += 0.3
    return max(1, min(5, round(score)))


# ── Emit ─────────────────────────────────────────────────────────────────────

def slots_to_notes_json(slots: list, key: str) -> str:
    """Convert filled slots to VexFlow note JSON string."""
    from midi_to_notes import note_to_vex
    notes = []
    for s in slots:
        dur = s['dur']
        dotted = s.get('dotted', False)
        midi = s.get('midi')

        if dur.endswith('r') or midi is None:
            entry = {'key': 'b/4', 'duration': (dur.rstrip('r') + 'r') if not dur.endswith('r') else dur}
        else:
            vex_key = note_to_vex(midi, None, key)
            entry = {'key': vex_key, 'duration': dur}

        if dotted:
            entry['dotted'] = True
        notes.append(entry)
    return json.dumps(notes)


def write_preview_midi(notes_json_str: str, tempo: int) -> str:
    """
    Write a preview MIDI to static/melodic/_preview/_preview.mid.
    Returns the relative path 'melodic/_preview/_preview.mid'.
    """
    from generate_midi import DURATION_BEATS
    from midiutil import MIDIFile
    notes = json.loads(notes_json_str)
    dest_dir = os.path.join(STATIC_DIR, 'melodic', '_preview')
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, '_preview.mid')

    midi = MIDIFile(1)
    midi.addTempo(0, 0, tempo)
    time = 0.0
    for n in notes:
        dur_str = n['duration']
        dotted  = n.get('dotted', False)
        base    = dur_str.rstrip('r')
        beats   = DURATION_BEATS.get(base, 1) * (1.5 if dotted else 1)
        if not dur_str.endswith('r'):
            # Parse VexFlow key to MIDI
            key_str = n['key']
            name, octave = key_str.split('/')
            pc_map = {'c':0,'c#':1,'db':1,'d':2,'d#':3,'eb':3,'e':4,'f':5,
                      'f#':6,'gb':6,'g':7,'g#':8,'ab':8,'a':9,'a#':10,'bb':10,'b':11}
            pc = pc_map.get(name.lower(), 0)
            midi_num = (int(octave) + 1) * 12 + pc
            midi.addNote(0, 0, midi_num, time, beats * 0.9, 90)
        time += beats

    with open(dest_path, 'wb') as f:
        midi.writeFile(f)
    return 'melodic/_preview/_preview.mid'


# ── Top-level generate() ──────────────────────────────────────────────────────

def generate(params: dict) -> dict:
    """
    Generate a melody from params dict.

    Required params keys:
      key (str), mode (str), gen_progression_chords (list[dict]),
      time_sig (str), num_measures (int), min_duration (str), clef (str),
      start_midi (int), high_midi (int), low_midi (int),
      techniques (list[str]), rhythm_complexity (int, 1-3),
      syncopation (bool), seed (int|None), tempo (int)

    Returns:
      notes_json (str), midi_path (str), difficulty_suggestion (int),
      auto_tags (list[str]), generation_params (dict)
    """
    seed = params.get('seed')
    rng  = random.Random(seed)

    chords  = params['gen_progression_chords']
    key     = params['key']
    mode    = params['mode']
    clef    = params['clef']
    tempo   = params.get('tempo', 100)

    windows = realize_harmony(chords, key, mode)
    slots   = build_rhythm(
        params['time_sig'], params['num_measures'],
        params['min_duration'], params['rhythm_complexity'],
        params['syncopation'], rng,
    )
    contour = {
        'start_midi': params['start_midi'],
        'high_midi':  params['high_midi'],
        'low_midi':   params['low_midi'],
    }
    slots = place_skeleton(slots, windows, contour, clef, key, rng)
    slots, techniques_used = apply_techniques(
        slots, windows, params.get('techniques', []), key, mode, rng
    )

    gp_diff = params.get('gen_prog_difficulty', 1)

    notes_json_str = slots_to_notes_json(slots, key)
    midi_path      = write_preview_midi(notes_json_str, tempo)

    return {
        'notes_json':            notes_json_str,
        'midi_path':             midi_path,
        'difficulty_suggestion': suggest_difficulty(slots, techniques_used, gp_diff),
        'auto_tags':             auto_tags(params, techniques_used),
        'generation_params':     params,
    }
