"""
generate_holistic_exercises.py
================================
Seeds the HolisticExercise table with two sample exercises.
Creates the exercise folder structure under static/holistic/,
writes MIDI files using midiutil, and generates a test WAV using
Python's built-in wave + struct modules (no external dependencies
beyond mido and midiutil which are already installed).

Usage:
    python3 generate_holistic_exercises.py
"""

import json
import math
import os
import struct
import sys
import wave

# ── Ensure midiutil and mido are available ─────────────────────────────────
try:
    from midiutil import MIDIFile
except ImportError:
    print("ERROR: midiutil is required. Run: pip install midiutil")
    sys.exit(1)

try:
    import mido  # noqa: F401 — used inside chord_utils / midi_to_notes
except ImportError:
    print("ERROR: mido is required. Run: pip install mido")
    sys.exit(1)

# ── Project imports ────────────────────────────────────────────────────────
# Must be done BEFORE importing app so Flask app context is available.
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, HolisticExercise
from midi_to_notes import extract_notes, build_json_list, midi_to_vex
from chord_utils import infer_chords_from_midi


# ---------------------------------------------------------------------------
# WAV synthesis helpers
# ---------------------------------------------------------------------------

SAMPLE_RATE = 44100


def midi_pitch_to_freq(midi_note):
    """Convert a MIDI note number to frequency in Hz."""
    return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))


def generate_wav(filepath, chords_with_durations, tempo_bpm, sample_rate=SAMPLE_RATE):
    """
    Generate a WAV file by summing sine waves for each chord.

    chords_with_durations: list of (midi_pitches, duration_beats)
    """
    frames = []
    seconds_per_beat = 60.0 / tempo_bpm
    for pitches, beats in chords_with_durations:
        n_samples = int(beats * seconds_per_beat * sample_rate)
        for i in range(n_samples):
            t = i / sample_rate
            amp_env = min(1.0, t * 20) * max(0.0, 1.0 - t * 0.3)
            sample = 0.0
            for p in pitches:
                freq = midi_pitch_to_freq(p)
                sample += math.sin(2 * math.pi * freq * t)
            if pitches:
                sample /= len(pitches)
            sample *= amp_env
            frames.append(struct.pack('<h', int(sample * 16000)))

    with wave.open(filepath, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join(frames))


# ---------------------------------------------------------------------------
# MIDI writing helpers
# ---------------------------------------------------------------------------

def write_melody_midi(filepath, notes_midi, tempo_bpm):
    """
    Write a single-track melody MIDI file.

    notes_midi: list of (midi_pitch, duration_beats) tuples.
                Use midi_pitch=None for rests.
    """
    midi = MIDIFile(1)
    midi.addTempo(0, 0, tempo_bpm)
    time = 0.0
    for pitch, duration in notes_midi:
        if pitch is not None:
            midi.addNote(0, 0, pitch, time, duration, 90)
        time += duration
    with open(filepath, 'wb') as f:
        midi.writeFile(f)


def write_harmony_midi(filepath, chords_midi, tempo_bpm):
    """
    Write a single-track harmony MIDI file.

    chords_midi: list of (midi_pitches_list, duration_beats) tuples.
    """
    midi = MIDIFile(1)
    midi.addTempo(0, 0, tempo_bpm)
    time = 0.0
    for pitches, duration in chords_midi:
        for pitch in pitches:
            midi.addNote(0, 0, pitch, time, duration, 80)
        time += duration
    with open(filepath, 'wb') as f:
        midi.writeFile(f)


# ---------------------------------------------------------------------------
# Exercise definitions
# ---------------------------------------------------------------------------

def make_exercise_1(static_dir):
    """
    Exercise 1 — simple_c_major
    C major, 4/4, tempo 80, difficulty 1.
    Primary melody (8 quarter notes): C4–E4–G4–E4–F4–D4–G4–C4 (2 measures)
    Harmony (half-note chords): I (C, 2 beats), V (G, 2 beats), IV (F, 2 beats), I (C, 2 beats)
    No extra lines.
    """
    folder_name = 'holistic/simple_c_major'
    folder_path = os.path.join(static_dir, 'holistic', 'simple_c_major')
    os.makedirs(folder_path, exist_ok=True)

    tempo = 80

    # Melody: C4=60, E4=64, G4=67, E4=64, F4=65, D4=62, G4=67, C4=60
    melody_notes_midi = [
        (60, 1), (64, 1), (67, 1), (64, 1),
        (65, 1), (62, 1), (67, 1), (60, 1),
    ]

    # Harmony: I=C major [48,52,55,60], V=G major [43,47,50,55], IV=F major [41,45,48,53], I
    # Using half-note chords (2 beats each)
    c_major = [48, 52, 55, 60]  # C3, E3, G3, C4
    g_major = [43, 47, 50, 55]  # G2, B2, D3, G3
    f_major = [41, 45, 48, 53]  # F2, A2, C3, F3
    harmony_chords_midi = [
        (c_major, 2), (g_major, 2), (f_major, 2), (c_major, 2),
    ]

    melody_mid = os.path.join(folder_path, 'melody.mid')
    harmony_mid = os.path.join(folder_path, 'harmony.mid')
    audio_wav = os.path.join(folder_path, 'audio.wav')

    write_melody_midi(melody_mid, melody_notes_midi, tempo)
    write_harmony_midi(harmony_mid, harmony_chords_midi, tempo)

    # WAV: mix melody + chord tones
    # Build combined pitches per chord (melody notes over each chord)
    # Simplify: just use harmony chords for WAV
    generate_wav(audio_wav, harmony_chords_midi, tempo)

    # Parse melody MIDI for notes_json
    melody_raw = extract_notes(melody_mid)
    melody_notes_json = build_json_list(melody_raw)

    # Parse harmony MIDI for chords_json
    harmony_chords_json = infer_chords_from_midi(harmony_mid, key_signature='C')

    return {
        'name': 'Simple C Major Melody',
        'description': 'A short two-measure melody in C major with basic I–V–IV–I harmony.',
        'folder': folder_name,
        'wav_filename': 'audio.wav',
        'key_signature': 'C',
        'time_signature': '4/4',
        'tempo': tempo,
        'difficulty': 1,
        'is_major': True,
        'melody_clef': 'treble',
        'melody_notes_json': json.dumps(melody_notes_json),
        'harmony_chords_json': json.dumps(harmony_chords_json),
        'extra_lines_json': json.dumps([]),
    }


def make_exercise_3(static_dir):
    """
    Exercise 3 — test_melody
    C major, 4/4, tempo 98, difficulty 2.
    Uses user-supplied WAV, harmony MIDI, and melody MIDI.
    """
    folder_name = 'holistic/test_melody'
    folder_path = os.path.join(static_dir, 'holistic', 'test_melody')

    tempo = 98

    melody_mid  = os.path.join(folder_path, 'melody.mid')
    harmony_mid = os.path.join(folder_path, 'harmony.mid')

    # Parse melody MIDI for notes_json
    melody_raw        = extract_notes(melody_mid)
    melody_notes_json = build_json_list(melody_raw)

    # Parse harmony MIDI for chords_json
    harmony_chords_json = infer_chords_from_midi(harmony_mid, key_signature='C')

    return {
        'name':                'test',
        'description':         'I hope this works',
        'folder':              folder_name,
        'wav_filename':        'audio.wav',
        'key_signature':       'C',
        'time_signature':      '4/4',
        'tempo':               tempo,
        'difficulty':          2,
        'is_major':            True,
        'melody_clef':         'treble',
        'melody_notes_json':   json.dumps(melody_notes_json),
        'harmony_chords_json': json.dumps(harmony_chords_json),
        'extra_lines_json':    json.dumps([]),
    }


def make_exercise_2(static_dir):
    """
    Exercise 2 — g_major_melody_bass
    G major, 4/4, tempo 88, difficulty 2.
    Primary melody (8 quarter notes): G4–A4–B4–G4–A4–C5–B4–G4 (2 measures)
    Bass line (whole notes): G2, D2 (one per measure)
    Harmony (half-note chords): I (G, 2 beats), V (D, 2 beats), IV (C, 2 beats), I (G, 2 beats)
    """
    folder_name = 'holistic/g_major_melody_bass'
    folder_path = os.path.join(static_dir, 'holistic', 'g_major_melody_bass')
    os.makedirs(folder_path, exist_ok=True)

    tempo = 88

    # Melody: G4=67, A4=69, B4=71, G4=67, A4=69, C5=72, B4=71, G4=67
    melody_notes_midi = [
        (67, 1), (69, 1), (71, 1), (67, 1),
        (69, 1), (72, 1), (71, 1), (67, 1),
    ]

    # Bass line: G2=43 (whole note = 4 beats), D2=38 (whole note)
    bass_notes_midi = [
        (43, 4),  # G2
        (38, 4),  # D2
    ]

    # Harmony: I=G major [43,47,50,55], V=D major [38,42,45,50], IV=C major [36,40,43,48], I
    g_major = [43, 47, 50, 55]  # G2, B2, D3, G3
    d_major = [38, 42, 45, 50]  # D2, F#2, A2, D3
    c_major = [36, 40, 43, 48]  # C2, E2, G2, C3
    harmony_chords_midi = [
        (g_major, 2), (d_major, 2), (c_major, 2), (g_major, 2),
    ]

    melody_mid  = os.path.join(folder_path, 'melody.mid')
    melody1_mid = os.path.join(folder_path, 'melody_1.mid')
    harmony_mid = os.path.join(folder_path, 'harmony.mid')
    audio_wav   = os.path.join(folder_path, 'audio.wav')

    write_melody_midi(melody_mid,  melody_notes_midi, tempo)
    write_melody_midi(melody1_mid, bass_notes_midi,   tempo)
    write_harmony_midi(harmony_mid, harmony_chords_midi, tempo)

    # WAV: mix melody + bass + chord tones
    # Simplify: use harmony + bass for WAV
    combined = []
    # interleave bass + chords — use harmony duration pairs and add bass
    # bass: [G2 for 4 beats, D2 for 4 beats] vs harmony [2+2 / 2+2]
    # For simplicity, generate WAV from harmony only (rough test file)
    generate_wav(audio_wav, harmony_chords_midi, tempo)

    # Parse melody MIDI
    melody_raw  = extract_notes(melody_mid)
    melody_notes_json = build_json_list(melody_raw)

    # Parse bass MIDI for extra_lines
    bass_raw  = extract_notes(melody1_mid)
    bass_notes_json = build_json_list(bass_raw)

    # Parse harmony MIDI
    harmony_chords_json = infer_chords_from_midi(harmony_mid, key_signature='G')

    extra_lines = [
        {
            'type':  'melody',
            'file':  'melody_1.mid',
            'label': 'Bass line',
            'clef':  'bass',
            'notes': bass_notes_json,
        }
    ]

    return {
        'name': 'G Major Melody with Bass',
        'description': 'A two-measure melody in G major with a bass line and I–V–IV–I harmony.',
        'folder': folder_name,
        'wav_filename': 'audio.wav',
        'key_signature': 'G',
        'time_signature': '4/4',
        'tempo': tempo,
        'difficulty': 2,
        'is_major': True,
        'melody_clef': 'treble',
        'melody_notes_json': json.dumps(melody_notes_json),
        'harmony_chords_json': json.dumps(harmony_chords_json),
        'extra_lines_json': json.dumps(extra_lines),
    }


# ---------------------------------------------------------------------------
# Seeder
# ---------------------------------------------------------------------------

def seed():
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    os.makedirs(os.path.join(static_dir, 'holistic'), exist_ok=True)

    EXERCISES = [
        ('Exercise 1 — simple_c_major',    make_exercise_1),
        ('Exercise 2 — g_major_melody_bass', make_exercise_2),
        ('Exercise 3 — test_melody',        make_exercise_3),
    ]

    print("Generating exercise assets...")
    exercises_data = []
    for label, fn in EXERCISES:
        try:
            exercises_data.append(fn(static_dir))
            print("  [OK]", label)
        except Exception as e:
            print("  [ERROR]", label, ":", e)
            import traceback; traceback.print_exc()

    with app.app_context():
        db.create_all()

        # Upsert: add new exercises, skip ones whose folder already exists in DB.
        existing_folders = {ex.folder for ex in HolisticExercise.query.all()}

        added = 0
        for data in exercises_data:
            if data['folder'] in existing_folders:
                print("  [SKIP] already seeded:", data['folder'])
                continue
            ex = HolisticExercise(
                name                = data['name'],
                description         = data['description'],
                folder              = data['folder'],
                wav_filename        = data['wav_filename'],
                key_signature       = data['key_signature'],
                time_signature      = data['time_signature'],
                tempo               = data['tempo'],
                difficulty          = data['difficulty'],
                is_major            = data['is_major'],
                melody_clef         = data['melody_clef'],
                melody_notes_json   = data['melody_notes_json'],
                harmony_chords_json = data['harmony_chords_json'],
                extra_lines_json    = data['extra_lines_json'],
            )
            db.session.add(ex)
            added += 1

        db.session.commit()
        count = HolisticExercise.query.count()
        print("Added {} new exercise(s). Total: {}.".format(added, count))


if __name__ == '__main__':
    seed()
