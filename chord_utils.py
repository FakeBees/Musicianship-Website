"""
chord_utils.py
Utilities for harmonic dictation: MIDI chord inference, chord analysis,
chord name formatting, and grading.
"""

import json
import logging

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Preferred note names for each pitch class per key.
# Keys that prefer sharps use sharp spellings; flat keys use flat spellings.
KEY_SPELLING = {
    # Chromatic scale names indexed by pitch class 0–11
    # Format: list of 12 note names ordered by pitch class
    # Sharp-side keys: use sharps for diatonic notes; flats for borrowed/chromatic tones
    # Flat-side keys: use flats throughout
    # C uses flats for chromatic notes (borrowed chords like bVII=Bb, bIII=Eb, bVI=Ab)
    'C':  ['C','Db','D','Eb','E','F','F#','G','Ab','A','Bb','B'],
    'G':  ['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B'],
    'D':  ['C','C#','D','Eb','E','F','F#','G','G#','A','Bb','B'],
    'A':  ['C','C#','D','D#','E','F','F#','G','G#','A','Bb','B'],
    'E':  ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'],
    'B':  ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'],
    'F#': ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'],
    'Gb': ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'],
    'F':  ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'],
    'Bb': ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'],
    'Eb': ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'],
    'Ab': ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'],
    'Db': ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'],
    # Minor keys (use same accidental preference as relative major)
    'Am': ['C','Db','D','Eb','E','F','F#','G','Ab','A','Bb','B'],
    'Em': ['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B'],
    'Bm': ['C','C#','D','D#','E','F','F#','G','G#','A','Bb','B'],
    'Dm': ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'],
    'Gm': ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'],
    'Cm': ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'],
    'Fm': ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'],
}

# Known triad interval patterns (semitones above root), as frozensets
INTERVAL_PATTERNS = {
    'major':      frozenset({0, 4, 7}),
    'minor':      frozenset({0, 3, 7}),
    'diminished': frozenset({0, 3, 6}),
    'augmented':  frozenset({0, 4, 8}),
    'sus2':       frozenset({0, 2, 7}),
    'sus4':       frozenset({0, 5, 7}),
}

# Diatonic scale pitch classes for each key (natural minor for minor keys)
SCALE_DEGREES = {
    'C':  [0, 2, 4, 5, 7, 9, 11],
    'G':  [7, 9, 11, 0, 2, 4, 6],
    'D':  [2, 4, 6, 7, 9, 11, 1],
    'A':  [9, 11, 1, 2, 4, 6, 8],
    'E':  [4, 6, 8, 9, 11, 1, 3],
    'B':  [11, 1, 3, 4, 6, 8, 10],
    'F#': [6, 8, 10, 11, 1, 3, 5],
    'Gb': [6, 8, 10, 11, 1, 3, 5],
    'F':  [5, 7, 9, 10, 0, 2, 4],
    'Bb': [10, 0, 2, 3, 5, 7, 9],
    'Eb': [3, 5, 7, 8, 10, 0, 2],
    'Ab': [8, 10, 0, 1, 3, 5, 7],
    'Db': [1, 3, 5, 6, 8, 10, 0],
    # Minor keys (natural minor)
    'Am': [9, 11, 0, 2, 4, 5, 7],
    'Em': [4, 6, 7, 9, 11, 0, 2],
    'Bm': [11, 1, 2, 4, 6, 7, 9],
    'Dm': [2, 4, 5, 7, 9, 10, 0],
    'Gm': [7, 9, 10, 0, 2, 3, 5],
    'Cm': [0, 2, 3, 5, 7, 8, 10],
    'Fm': [5, 7, 8, 10, 0, 1, 3],
}

# Roman numeral symbols for scale degrees 0–6
_ROMAN_UPPER = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII']
_ROMAN_LOWER = ['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii']


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _note_name(pc: int, key_signature: str) -> str:
    """Return the preferred note name for pitch class pc in the given key."""
    spelling = KEY_SPELLING.get(key_signature, KEY_SPELLING['C'])
    return spelling[pc % 12]


# ---------------------------------------------------------------------------
# analyse_chord
# ---------------------------------------------------------------------------

def analyse_chord(pitches: set, key_signature: str = 'C') -> dict:
    """
    Given a set of MIDI pitch numbers, return a chord dict.
    The dict shape matches the spec in HARMONIC_DICTATION_PLAN.md §2b.
    """
    if not pitches:
        return {}

    pitches = set(pitches)
    pcs = set(p % 12 for p in pitches)
    bass_midi = min(pitches)
    bass_pc = bass_midi % 12
    bass_name = _note_name(bass_pc, key_signature)

    best = None
    best_score = -1

    # Prefer the bass note as root (tiebreaker for equal scores)
    # Try bass_pc first so it is favoured when scores tie
    pcs_ordered = sorted(pcs, key=lambda pc: (0 if pc == bass_pc else 1))

    for root_pc in pcs_ordered:
        intervals = frozenset((pc - root_pc) % 12 for pc in pcs)
        for quality, pattern in INTERVAL_PATTERNS.items():
            core_intervals = frozenset(i for i in intervals if i in pattern)
            if core_intervals == pattern:
                # More matched tones wins; ties broken by bass-note preference (order above)
                score = len(pattern)
                if score > best_score:
                    best_score = score
                    best = (root_pc, quality, intervals)

    if best is None:
        # Fallback: pick root as bass note, quality as major
        root_pc = bass_pc
        quality = 'major'
        intervals = frozenset((pc - root_pc) % 12 for pc in pcs)
    else:
        root_pc, quality, intervals = best

    root_name = _note_name(root_pc, key_signature)

    # Remaining intervals after core triad
    pattern = INTERVAL_PATTERNS[quality]
    remaining = frozenset(i for i in intervals if i not in pattern)

    # Seventh detection
    seventh = None
    seventh_intervals = set()
    if 11 in remaining:
        seventh = 'major7'
        seventh_intervals.add(11)
    elif 10 in remaining:
        seventh = 'minor7'
        seventh_intervals.add(10)
    elif 9 in remaining and quality == 'diminished':
        seventh = 'diminished7'
        seventh_intervals.add(9)

    remaining = frozenset(i for i in remaining if i not in seventh_intervals)

    # Extension detection (two-pass: triad quality is already known)
    has_perfect_fifth = 7 in pattern
    has_major_third   = 4 in pattern
    extensions = []

    ext_map = {
        1:  'b9',
        2:  '9',
        5:  '11',
        9:  '13',
    }
    for i in sorted(remaining):
        if i == 3 and quality in ('major', 'augmented'):
            extensions.append('#9')
        elif i == 6:
            if has_perfect_fifth:
                extensions.append('#11')
            # else it was already the diminished fifth (core triad), skip
        elif i == 8:
            if has_major_third and has_perfect_fifth:
                extensions.append('b13')
            # else augmented fifth (core triad), skip
        elif i in ext_map:
            extensions.append(ext_map[i])

    sus = None
    if quality == 'sus2':
        sus = 'sus2'
        quality = 'major'  # store underlying quality as major for sus chords
    elif quality == 'sus4':
        sus = 'sus4'
        quality = 'major'

    return {
        'root_pc':   root_pc,
        'root_name': root_name,
        'quality':   quality,
        'bass_pc':   bass_pc,
        'bass_name': bass_name,
        'seventh':   seventh,
        'extensions': extensions,
        'sus':       sus,
    }


# ---------------------------------------------------------------------------
# infer_chords_from_midi
# ---------------------------------------------------------------------------

def infer_chords_from_midi(midi_path: str, key_signature: str = 'C') -> list:
    """
    Parse a MIDI file and return a list of chord dicts.
    Uses mido to read events; groups simultaneous notes into chords.
    """
    try:
        import mido
    except ImportError:
        raise ImportError("mido is required: pip install mido")

    mid = mido.MidiFile(midi_path)
    ticks_per_beat = mid.ticks_per_beat

    # Collect all note events with absolute tick times
    events = []  # (abs_tick, type, pitch)
    for track in mid.tracks:
        abs_tick = 0
        for msg in track:
            abs_tick += msg.time
            if msg.type == 'note_on' and msg.velocity > 0:
                events.append((abs_tick, 'on', msg.note))
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                events.append((abs_tick, 'off', msg.note))

    if not events:
        logging.warning("infer_chords_from_midi: no note events found in %s", midi_path)
        return []

    events.sort(key=lambda e: (e[0], 0 if e[1] == 'off' else 1))

    # Build timeline of (start_tick, pitch_set) events
    active: dict = {}  # pitch -> start_tick
    chord_events = []  # (start_tick, end_tick, frozenset of pitches)
    current_set: set = set()
    current_start = 0

    for tick, etype, pitch in events:
        if etype == 'on':
            if current_set and tick > current_start:
                chord_events.append((current_start, tick, frozenset(current_set)))
            active[pitch] = tick
            current_set.add(pitch)
            current_start = tick
        else:
            if current_set and tick > current_start:
                chord_events.append((current_start, tick, frozenset(current_set)))
            current_set.discard(pitch)
            active.pop(pitch, None)
            current_start = tick

    # Merge consecutive identical pitch sets
    merged = []
    for start, end, ps in chord_events:
        if merged and merged[-1][2] == ps:
            merged[-1] = (merged[-1][0], end, ps)
        else:
            merged.append([start, end, ps])

    # Filter: keep only chords lasting at least one quarter note
    min_duration = ticks_per_beat
    result = []
    for start, end, ps in merged:
        duration = end - start
        if duration < min_duration:
            continue
        result.append(analyse_chord(set(ps), key_signature))

    if not result:
        logging.warning("infer_chords_from_midi: no chords long enough found in %s", midi_path)

    return result


# ---------------------------------------------------------------------------
# pitch_class_to_scale_degree
# ---------------------------------------------------------------------------

def pitch_class_to_scale_degree(pc: int, key_signature: str):
    """
    Return the 0-indexed scale degree of pc in key_signature, or None if chromatic.
    """
    scale = SCALE_DEGREES.get(key_signature, SCALE_DEGREES['C'])
    if pc in scale:
        return scale.index(pc)
    return None


# ---------------------------------------------------------------------------
# format_chord_name
# ---------------------------------------------------------------------------

def format_chord_name(chord: dict, mode: str, key_signature: str) -> str:
    """
    Return a human-readable chord symbol string.
    mode: 'lead' | 'roman' | 'nashville'
    """
    if not chord:
        return '?'

    root_pc  = chord.get('root_pc', 0)
    root_name= chord.get('root_name', 'C')
    quality  = chord.get('quality', 'major')
    bass_pc  = chord.get('bass_pc', root_pc)
    bass_name= chord.get('bass_name', root_name)
    seventh      = chord.get('seventh')
    exts         = chord.get('extensions', []) or []
    sus          = chord.get('sus')
    prefer_sharp = chord.get('prefer_sharp')  # True=raised, False=lowered, None=diatonic/default

    # Quality suffixes for lead sheet
    _quality_suffix = {
        'major':      '',
        'minor':      'm',
        'diminished': 'dim',
        'augmented':  '+',
    }
    # Seventh suffixes
    def _seventh_suffix(quality, seventh):
        if seventh == 'major7':
            return 'maj7'
        if seventh == 'minor7':
            if quality == 'minor':
                return 'm7'   # already has 'm' from quality
            return '7'        # dominant
        if seventh == 'diminished7':
            return 'dim7'
        return ''

    def _ext_str(exts):
        order = ['b9','9','#9','11','#11','13','b13']
        sorted_exts = sorted(exts, key=lambda x: order.index(x) if x in order else 99)
        return ''.join(
            e.replace('b', '♭').replace('#', '♯') for e in sorted_exts
        )

    if mode == 'lead':
        root_display = root_name.replace('b', '♭').replace('#', '♯')
        if sus:
            symbol = root_display + sus
        else:
            q_suf = _quality_suffix.get(quality, '')
            if seventh:
                if quality == 'diminished' and seventh == 'diminished7':
                    symbol = root_display + 'dim7'
                elif quality == 'minor' and seventh == 'minor7':
                    symbol = root_display + 'm7'
                elif quality == 'minor' and seventh == 'major7':
                    symbol = root_display + 'mmaj7'
                elif quality == 'diminished' and seventh == 'minor7':
                    # half-diminished
                    symbol = root_display + 'm7b5'
                else:
                    s_suf = _seventh_suffix(quality, seventh)
                    symbol = root_display + q_suf + s_suf
            else:
                symbol = root_display + q_suf
        symbol += _ext_str(exts)
        if bass_pc != root_pc:
            symbol += '/' + bass_name.replace('b', '♭').replace('#', '♯')
        return symbol

    # Roman or Nashville
    scale = SCALE_DEGREES.get(key_signature, SCALE_DEGREES['C'])
    degree = pitch_class_to_scale_degree(root_pc, key_signature)
    is_minor_key = key_signature.endswith('m')

    if degree is not None:
        prefix = ''
        deg_idx = degree  # 0-indexed
    else:
        # Chromatic — find nearest diatonic degree and add accidental
        # Try flat (lower by 1)
        flat_pc = (root_pc + 1) % 12
        sharp_pc = (root_pc - 1) % 12
        flat_deg = pitch_class_to_scale_degree(flat_pc, key_signature)
        sharp_deg = pitch_class_to_scale_degree(sharp_pc, key_signature)
        if prefer_sharp is True and sharp_deg is not None:
            prefix = '♯'
            deg_idx = sharp_deg
        elif prefer_sharp is False and flat_deg is not None:
            prefix = '♭'
            deg_idx = flat_deg
        elif flat_deg is not None:
            prefix = '♭'
            deg_idx = flat_deg
        elif sharp_deg is not None:
            prefix = '♯'
            deg_idx = sharp_deg
        else:
            prefix = ''
            deg_idx = 0

    if mode == 'roman':
        # Uppercase for major/aug/sus, lowercase for minor/dim
        if quality in ('minor', 'diminished'):
            numeral = prefix + _ROMAN_LOWER[deg_idx]
        else:
            numeral = prefix + _ROMAN_UPPER[deg_idx]
        if sus:
            symbol = numeral + sus
        elif seventh:
            if quality == 'diminished' and seventh == 'diminished7':
                symbol = numeral + '°⁷'
            elif quality == 'diminished' and seventh == 'minor7':
                symbol = numeral + 'ø⁷'
            elif seventh == 'major7':
                symbol = numeral + 'maj⁷'
            else:
                symbol = numeral + '⁷'
        else:
            if quality == 'diminished':
                symbol = numeral + '°'
            elif quality == 'augmented':
                symbol = numeral + '⁺'
            else:
                symbol = numeral
        symbol += _ext_str(exts)
        if bass_pc != root_pc:
            intervals = INTERVAL_PATTERNS.get(quality, INTERVAL_PATTERNS['major'])
            sorted_intervals = sorted(intervals)
            third_pc  = (root_pc + sorted_intervals[1]) % 12 if len(sorted_intervals) > 1 else None
            fifth_pc  = (root_pc + sorted_intervals[2]) % 12 if len(sorted_intervals) > 2 else None
            seventh_pc = None
            if seventh == 'major7':
                seventh_pc = (root_pc + 11) % 12
            elif seventh in ('minor7', 'dominant7'):
                seventh_pc = (root_pc + 10) % 12
            elif seventh == 'diminished7':
                seventh_pc = (root_pc + 9) % 12
            if bass_pc == third_pc:
                symbol += '6'
            elif bass_pc == fifth_pc:
                symbol += '64'
            elif seventh_pc is not None and bass_pc == seventh_pc:
                symbol += '4/2'
            else:
                symbol += '/' + bass_name.replace('b', '♭').replace('#', '♯')
        return symbol

    if mode == 'nashville':
        if quality in ('minor', 'diminished'):
            numeral = prefix + str(deg_idx + 1)
        else:
            numeral = prefix + str(deg_idx + 1)
        if sus:
            symbol = numeral + sus
        elif seventh:
            if quality == 'diminished' and seventh == 'diminished7':
                symbol = numeral + '°⁷'
            elif quality == 'diminished' and seventh == 'minor7':
                symbol = numeral + 'ø⁷'
            elif seventh == 'major7':
                symbol = numeral + 'maj⁷'
            else:
                symbol = numeral + '⁷'
        else:
            if quality == 'diminished':
                symbol = numeral + '°'
            elif quality == 'augmented':
                symbol = numeral + '⁺'
            elif quality == 'minor':
                symbol = numeral + 'm'
            else:
                symbol = numeral
        symbol += _ext_str(exts)
        if bass_pc != root_pc:
            bass_deg = pitch_class_to_scale_degree(bass_pc, key_signature)
            if bass_deg is not None:
                symbol += '/' + str(bass_deg + 1)
            else:
                symbol += '/' + bass_name.replace('b', '♭').replace('#', '♯')
        return symbol

    return root_name  # fallback


# ---------------------------------------------------------------------------
# grade_harmonic_attempt
# ---------------------------------------------------------------------------

def grade_harmonic_attempt(correct_chords: list, user_chords: list):
    """
    Returns (chord_letter_accuracy, chord_quality_accuracy, overall_score)
    as percentages (0–100).

    chord_letter_accuracy: % of positions where root_pc matches.
    chord_quality_accuracy: % of positions where quality, sus, seventh,
        and extensions all match exactly.
    Extra or missing chords count as wrong.
    """
    total = max(len(correct_chords), len(user_chords)) if correct_chords or user_chords else 0
    if total == 0:
        return 0.0, 0.0, 0.0

    letter_correct  = 0
    quality_correct = 0

    for i in range(total):
        c = correct_chords[i] if i < len(correct_chords) else None
        u = user_chords[i]    if i < len(user_chords)    else None
        if c and u:
            if c.get('root_pc') == u.get('root_pc'):
                letter_correct += 1
            c_exts = sorted(c.get('extensions') or [])
            u_exts = sorted(u.get('extensions') or [])
            if (c.get('quality')  == u.get('quality')
                    and c.get('sus')      == u.get('sus')
                    and c.get('seventh')  == u.get('seventh')
                    and c_exts            == u_exts):
                quality_correct += 1

    letter_acc  = round(letter_correct  / total * 100, 1)
    quality_acc = round(quality_correct / total * 100, 1)
    overall     = round((letter_acc + quality_acc) / 2, 1)
    return letter_acc, quality_acc, overall
