import pytest
from melody_generator import (
    KEY_PC, CHORD_INTERVALS, CLEF_RANGE,
    realize_harmony, chord_tone_midis,
)


def test_key_pc_c_is_zero():
    assert KEY_PC['C'] == 0


def test_key_pc_g_is_seven():
    assert KEY_PC['G'] == 7


def test_key_pc_f_is_five():
    assert KEY_PC['F'] == 5


def test_key_pc_am_is_nine():
    assert KEY_PC['Am'] == 9


def test_chord_intervals_maj():
    assert CHORD_INTERVALS['maj'] == [0, 4, 7]


def test_chord_intervals_min():
    assert CHORD_INTERVALS['min'] == [0, 3, 7]


def test_chord_intervals_dom7():
    assert CHORD_INTERVALS['dom7'] == [0, 4, 7, 10]


def test_clef_range_treble():
    low, high = CLEF_RANGE['treble']
    assert low == 60   # c/4
    assert high == 79  # g/5


def test_clef_range_bass():
    low, high = CLEF_RANGE['bass']
    assert low == 36   # c/2
    assert high == 55  # g/3


def test_realize_harmony_c_major_I_IV_V_I():
    chords = [
        {"degree": "I",  "quality": "maj", "inversion": 0, "beats": 4},
        {"degree": "IV", "quality": "maj", "inversion": 0, "beats": 4},
        {"degree": "V",  "quality": "maj", "inversion": 0, "beats": 4},
        {"degree": "I",  "quality": "maj", "inversion": 0, "beats": 4},
    ]
    windows = realize_harmony(chords, 'C', 'major')
    assert len(windows) == 4
    # I in C = {0, 4, 7}  (C, E, G)
    assert windows[0]['chord_pcs'] == {0, 4, 7}
    assert windows[0]['start_beat'] == 0.0
    assert windows[0]['dur_beats'] == 4.0
    # IV in C = {5, 9, 0} (F, A, C)
    assert windows[1]['chord_pcs'] == {5, 9, 0}
    # V in C = {7, 11, 2} (G, B, D)
    assert windows[2]['chord_pcs'] == {7, 11, 2}


def test_realize_harmony_am_minor_i_iv_V():
    chords = [
        {"degree": "i",  "quality": "min", "inversion": 0, "beats": 4},
        {"degree": "iv", "quality": "min", "inversion": 0, "beats": 4},
        {"degree": "V",  "quality": "maj", "inversion": 0, "beats": 4},
    ]
    windows = realize_harmony(chords, 'Am', 'minor')
    # Am tonic pc = 9; i = {9, 0, 4}
    assert 9 in windows[0]['chord_pcs']
    # iv in Am = Dm = {2, 5, 9}
    assert 2 in windows[1]['chord_pcs']
    # V in Am = E major = {4, 8, 11}
    assert 4 in windows[2]['chord_pcs']


def test_chord_tone_midis_in_treble_range():
    # C major chord (root_pc=0) in treble range 60–79
    midis = chord_tone_midis(0, 'maj', 60, 79)
    for m in midis:
        assert 60 <= m <= 79
    # Should include C5 (72), E5 (76), G5 (79), C4 (60)? check some
    assert 72 in midis  # c/5
    assert 64 in midis  # e/4
    assert 67 in midis  # g/4


# ── Rhythm tests ─────────────────────────────────────────────────────────────

import random
from melody_generator import build_rhythm, strong_beats, BEAT_VALUES


def test_strong_beats_4_4():
    sb = strong_beats('4/4', 2)
    assert 0.0 in sb   # beat 1 of measure 1
    assert 2.0 in sb   # beat 3 of measure 1 (half-bar accent)
    assert 4.0 in sb   # beat 1 of measure 2


def test_strong_beats_3_4():
    sb = strong_beats('3/4', 2)
    assert 0.0 in sb
    assert 3.0 in sb
    assert 1.0 not in sb  # beats 2 and 3 are weak


def test_build_rhythm_fills_exact_duration_4_4():
    rng = random.Random(42)
    slots = build_rhythm('4/4', 2, 'q', complexity=1, syncopation=False, rng=rng)
    total = sum(BEAT_VALUES[s['dur']] * (1.5 if s['dotted'] else 1.0) for s in slots)
    assert abs(total - 8.0) < 0.001  # 2 measures × 4 beats


def test_build_rhythm_fills_exact_duration_3_4():
    rng = random.Random(7)
    slots = build_rhythm('3/4', 4, 'q', complexity=1, syncopation=False, rng=rng)
    total = sum(BEAT_VALUES[s['dur']] * (1.5 if s['dotted'] else 1.0) for s in slots)
    assert abs(total - 12.0) < 0.001  # 4 measures × 3 beats


def test_build_rhythm_strong_slots_on_strong_beats():
    rng = random.Random(1)
    slots = build_rhythm('4/4', 2, 'q', complexity=1, syncopation=False, rng=rng)
    sb = strong_beats('4/4', 2)
    for s in slots:
        if s['beat'] in sb:
            assert s['is_strong']


def test_build_rhythm_min_duration_respected():
    rng = random.Random(99)
    slots = build_rhythm('4/4', 2, '8', complexity=2, syncopation=False, rng=rng)
    for s in slots:
        dur_key = s['dur'].rstrip('r')
        val = BEAT_VALUES[dur_key] * (1.5 if s['dotted'] else 1.0)
        assert val >= BEAT_VALUES['8'] * 0.99  # nothing shorter than min_duration


# ── Skeleton placement tests ──────────────────────────────────────────────────

from melody_generator import place_skeleton, active_window


def test_active_window_finds_correct_chord():
    windows = realize_harmony([
        {"degree": "I",  "quality": "maj", "inversion": 0, "beats": 4},
        {"degree": "V",  "quality": "maj", "inversion": 0, "beats": 4},
    ], 'C', 'major')
    w = active_window(2.0, windows)
    assert 0 in w['chord_pcs']  # still on I at beat 2

    w2 = active_window(4.0, windows)
    assert 7 in w2['chord_pcs']  # V starts at beat 4 (G)


def test_place_skeleton_strong_beats_are_chord_tones():
    rng = random.Random(42)
    chords = [
        {"degree": "I",  "quality": "maj", "inversion": 0, "beats": 4},
        {"degree": "V",  "quality": "maj", "inversion": 0, "beats": 4},
    ]
    windows = realize_harmony(chords, 'C', 'major')
    slots = build_rhythm('4/4', 2, 'q', complexity=1, syncopation=False, rng=rng)
    contour = {"start_midi": 64, "high_midi": 72, "low_midi": 60}
    result = place_skeleton(slots, windows, contour, 'treble', 'C', rng)

    for s in result:
        if s['is_strong'] and s['midi'] is not None:
            win = active_window(s['beat'], windows)
            assert s['midi'] % 12 in win['chord_pcs'], (
                f"Note {s['midi']} (pc={s['midi']%12}) not in chord pcs {win['chord_pcs']}"
            )


def test_place_skeleton_notes_in_clef_range():
    rng = random.Random(7)
    chords = [{"degree": "I", "quality": "maj", "inversion": 0, "beats": 4}]
    windows = realize_harmony(chords, 'C', 'major')
    slots = build_rhythm('4/4', 1, 'q', complexity=1, syncopation=False, rng=rng)
    contour = {"start_midi": 64, "high_midi": 72, "low_midi": 60}
    result = place_skeleton(slots, windows, contour, 'treble', 'C', rng)
    low, high = CLEF_RANGE['treble']
    for s in result:
        if s['midi'] is not None:
            assert low <= s['midi'] <= high


from melody_generator import CLEF_RANGE


def test_place_skeleton_consecutive_strong_notes_within_9_semitones():
    """Strong-beat notes should prefer moves ≤ 9 semitones (reachable filter)."""
    rng = random.Random(42)
    chords = [
        {"degree": "I", "quality": "maj", "inversion": 0, "beats": 4},
        {"degree": "V", "quality": "maj", "inversion": 0, "beats": 4},
        {"degree": "I", "quality": "maj", "inversion": 0, "beats": 4},
        {"degree": "V", "quality": "maj", "inversion": 0, "beats": 4},
    ]
    windows = realize_harmony(chords, 'C', 'major')
    slots = build_rhythm('4/4', 4, 'q', complexity=1, syncopation=False, rng=rng)
    contour = {"start_midi": 64, "high_midi": 72, "low_midi": 60}
    result = place_skeleton(slots, windows, contour, 'treble', 'C', rng)

    strong_midis = [s['midi'] for s in result if s['is_strong'] and s['midi'] is not None]
    # Check that most consecutive leaps are within 9 semitones
    # (fallback may rarely exceed, but in normal conditions should hold)
    large_leaps = sum(1 for i in range(1, len(strong_midis))
                      if abs(strong_midis[i] - strong_midis[i-1]) > 9)
    # Allow at most 1 large leap (fallback case), not systemic violations
    assert large_leaps <= 1, f"Too many large leaps: {large_leaps} in {strong_midis}"
