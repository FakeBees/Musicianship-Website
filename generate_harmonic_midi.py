# Run this script once to create MIDI files and seed the harmonic dictation database.
# Prerequisites: pip install mido midiutil flask flask-sqlalchemy
# Usage: python generate_harmonic_midi.py

import os
import json

from midiutil import MIDIFile

from app import app
from models import db, Tag, ChordProgression
from chord_utils import infer_chords_from_midi

MIDI_DIR = os.path.join(os.path.dirname(__file__), 'static', 'midi')


# ---------------------------------------------------------------------------
# Voice chord helper (not used for seeding since we provide exact voicings,
# but kept for reference / future use)
# ---------------------------------------------------------------------------

def voice_chord(root_pc, quality, bass_pc, seventh=None, extensions=None):
    """
    Return a list of MIDI note numbers for a closed-position voicing.
    Bass note in octave 3, upper voices around octave 4.
    """
    intervals = {
        'major':      [0, 4, 7],
        'minor':      [0, 3, 7],
        'diminished': [0, 3, 6],
        'augmented':  [0, 4, 8],
    }
    seventh_intervals = {
        'major7':      11,
        'minor7':      10,
        'diminished7': 9,
    }
    core = intervals.get(quality, [0, 4, 7])
    bass_midi = 48 + bass_pc  # octave 3 base = C3 (48)
    # Adjust bass to correct pitch class
    while bass_midi % 12 != bass_pc:
        bass_midi += 1
    # Upper voices: root + chord tones starting around C4 (60)
    upper_base = 60 + root_pc
    while upper_base % 12 != root_pc:
        upper_base += 1
    upper = [upper_base + i for i in core]
    if seventh and seventh in seventh_intervals:
        upper.append(upper_base + seventh_intervals[seventh])
    return [bass_midi] + upper


# ---------------------------------------------------------------------------
# Write MIDI from explicit note lists
# ---------------------------------------------------------------------------

def write_harmonic_midi(filename, note_groups, tempo=72, beats_per_chord=2):
    """
    Write a chord progression MIDI file.
    note_groups: list of lists of MIDI note numbers (one list per chord).
    Each chord lasts `beats_per_chord` quarter notes.
    """
    track = 0
    channel = 0
    duration = beats_per_chord
    volume = 100

    midi = MIDIFile(1)
    midi.addTempo(track, 0, tempo)

    for chord_idx, notes in enumerate(note_groups):
        time = chord_idx * beats_per_chord
        for pitch in notes:
            midi.addNote(track, channel, pitch, time, duration, volume)

    path = os.path.join(MIDI_DIR, filename)
    with open(path, 'wb') as f:
        midi.writeFile(f)
    print(f"  Wrote {path}")
    return path


# ---------------------------------------------------------------------------
# Seed helper
# ---------------------------------------------------------------------------

def get_or_create_tag(name, description=''):
    tag = Tag.query.filter_by(name=name).first()
    if not tag:
        tag = Tag(name=name, description=description)
        db.session.add(tag)
    return tag


def seed_progression(name, description, filename, key_signature, tempo,
                     difficulty, category, note_groups, tag_names):
    # Delete existing record with same name to allow re-running
    from models import HarmonicAttempt
    existing = ChordProgression.query.filter_by(name=name).first()
    if existing:
        HarmonicAttempt.query.filter_by(progression_id=existing.id).delete()
        db.session.delete(existing)
        db.session.commit()

    midi_path = os.path.join(MIDI_DIR, filename)
    chords = infer_chords_from_midi(midi_path, key_signature)
    if not chords:
        raise ValueError(f"No chords inferred from {filename}. "
                         "Check that the MIDI file has simultaneous notes.")

    prog = ChordProgression(
        name=name,
        description=description,
        midi_filename=filename,
        key_signature=key_signature,
        tempo=tempo,
        difficulty=difficulty,
        category=category,
        chords_json=json.dumps(chords),
    )
    for tag_name in tag_names:
        tag = get_or_create_tag(tag_name)
        prog.tags.append(tag)

    db.session.add(prog)
    db.session.commit()
    print(f"  Seeded: {name} ({len(chords)} chords)")
    return prog


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    with app.app_context():
        db.create_all()

        os.makedirs(MIDI_DIR, exist_ok=True)

        print("\n--- Progression 1: C major I–IV–V–I ---")
        # I:  bass=C3(48), upper=E4(64), G4(67), C5(72)
        # IV: bass=F3(53), upper=A4(69), C5(72), F5(77)
        # V:  bass=G3(55), upper=B4(71), D5(74), G5(79)
        # I:  bass=C3(48), upper=E4(64), G4(67), C5(72)
        p1_notes = [
            [48, 64, 67, 72],
            [53, 69, 72, 77],
            [55, 71, 74, 79],
            [48, 64, 67, 72],
        ]
        write_harmonic_midi('harm_c_major_I_IV_V_I.mid', p1_notes, tempo=72)
        seed_progression(
            name='c_major_I_IV_V_I',
            description='C major I–IV–V–I (diatonic, difficulty 1)',
            filename='harm_c_major_I_IV_V_I.mid',
            key_signature='C',
            tempo=72,
            difficulty=1,
            category='diatonic',
            note_groups=p1_notes,
            tag_names=[],
        )

        print("\n--- Progression 2: G major I–V–vi–IV ---")
        # I:  bass=G3(55), upper=B4(71), D5(74), G5(79)
        # V:  bass=D3(50), upper=F#4(66), A4(69), D5(74)
        # vi: bass=E3(52), upper=G4(67), B4(71), E5(76)
        # IV: bass=C3(48), upper=E4(64), G4(67), C5(72)
        p2_notes = [
            [55, 71, 74, 79],
            [50, 66, 69, 74],
            [52, 67, 71, 76],
            [48, 64, 67, 72],
        ]
        write_harmonic_midi('harm_g_major_I_V_vi_IV.mid', p2_notes, tempo=76)
        seed_progression(
            name='g_major_I_V_vi_IV',
            description='G major I–V–vi–IV (diatonic, difficulty 1)',
            filename='harm_g_major_I_V_vi_IV.mid',
            key_signature='G',
            tempo=76,
            difficulty=1,
            category='diatonic',
            note_groups=p2_notes,
            tag_names=[],
        )

        print("\n--- Progression 3: C major ii7–V7–Imaj7 ---")
        # ii7:   bass=D3(50), upper=F4(65), A4(69), C5(72)
        # V7:    bass=G3(55), upper=B4(71), D5(74), F5(77)
        # Imaj7: bass=C3(48), upper=E4(64), G4(67), B4(71)
        p3_notes = [
            [50, 65, 69, 72],
            [55, 71, 74, 77],
            [48, 64, 67, 71],
        ]
        write_harmonic_midi('harm_c_major_ii7_V7_Imaj7.mid', p3_notes, tempo=80)
        seed_progression(
            name='c_major_ii7_V7_Imaj7',
            description='C major ii⁷–V⁷–Imaj⁷ (diatonic with sevenths, difficulty 2)',
            filename='harm_c_major_ii7_V7_Imaj7.mid',
            key_signature='C',
            tempo=80,
            difficulty=2,
            category='diatonic',
            note_groups=p3_notes,
            tag_names=['contains:V7'],
        )

        print("\n--- Progression 4: C major I–bVII–IV–I ---")
        # I:    bass=C3(48), upper=E4(64), G4(67), C5(72)
        # bVII: bass=Bb2(46), upper=D4(62), F4(65), Bb4(70)
        # IV:   bass=F3(53), upper=A4(69), C5(72), F5(77)
        # I:    bass=C3(48), upper=E4(64), G4(67), C5(72)
        p4_notes = [
            [48, 64, 67, 72],
            [46, 62, 65, 70],
            [53, 69, 72, 77],
            [48, 64, 67, 72],
        ]
        write_harmonic_midi('harm_c_major_I_bVII_IV_I.mid', p4_notes, tempo=72)
        seed_progression(
            name='c_major_I_bVII_IV_I',
            description='C major I–♭VII–IV–I (mode mixture, difficulty 3)',
            filename='harm_c_major_I_bVII_IV_I.mid',
            key_signature='C',
            tempo=72,
            difficulty=3,
            category='mode_mixture',
            note_groups=p4_notes,
            tag_names=['contains:bVII'],
        )

        print("\n--- Progression 5: C major Vsus4–V–I–IV ---")
        # Vsus4(G): bass=G3(55), upper=C4(60), D4(62), G4(67)  pcs={7,0,2} → sus4
        # V(G):     bass=G3(55), upper=B4(71), D5(74), G5(79)
        # I(C):     bass=C3(48), upper=E4(64), G4(67), C5(72)
        # IV(F):    bass=F3(53), upper=A4(69), C5(72), F5(77)
        p5_notes = [
            [55, 60, 62, 67],
            [55, 71, 74, 79],
            [48, 64, 67, 72],
            [53, 69, 72, 77],
        ]
        write_harmonic_midi('harm_c_major_Vsus4_V_I_IV.mid', p5_notes, tempo=72)
        seed_progression(
            name='c_major_Vsus4_V_I_IV',
            description='C major Vsus4–V–I–IV (sus chords, difficulty 2)',
            filename='harm_c_major_Vsus4_V_I_IV.mid',
            key_signature='C',
            tempo=72,
            difficulty=2,
            category='diatonic',
            note_groups=p5_notes,
            tag_names=['contains:sus'],
        )

        print("\n--- Progression 6: G major Isus2–I–V–IV ---")
        # Isus2(G): bass=G3(55), upper=A3(57), D4(62), G4(67)  pcs={7,9,2} → sus2
        # I(G):     bass=G3(55), upper=B4(71), D5(74), G5(79)
        # V(D):     bass=D3(50), upper=F#4(66), A4(69), D5(74)
        # IV(C):    bass=C3(48), upper=E4(64), G4(67), C5(72)
        p6_notes = [
            [55, 57, 62, 67],
            [55, 71, 74, 79],
            [50, 66, 69, 74],
            [48, 64, 67, 72],
        ]
        write_harmonic_midi('harm_g_major_Isus2_I_V_IV.mid', p6_notes, tempo=76)
        seed_progression(
            name='g_major_Isus2_I_V_IV',
            description='G major Isus2–I–V–IV (sus chords, difficulty 2)',
            filename='harm_g_major_Isus2_I_V_IV.mid',
            key_signature='G',
            tempo=76,
            difficulty=2,
            category='diatonic',
            note_groups=p6_notes,
            tag_names=['contains:sus'],
        )

        print("\nDone. 6 progressions seeded.")


if __name__ == '__main__':
    main()
