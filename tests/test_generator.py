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
