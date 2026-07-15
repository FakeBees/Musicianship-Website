import pytest
from app import app
from models import db, HolisticExercise, HolisticLine

@pytest.fixture(autouse=True)
def ctx():
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def _make_exercise():
    ex = HolisticExercise(name='Test', folder='holistic/test/', wav_filename='audio.wav')
    db.session.add(ex)
    db.session.flush()
    mel = HolisticLine(
        holistic_exercise_id=ex.id, line_type='melody', name='Melody', order=0, clef='treble',
        midi_filename='', content_json='[{"key":"c/4","duration":"q"},{"key":"d/4","duration":"q"}]'
    )
    rhy = HolisticLine(
        holistic_exercise_id=ex.id, line_type='rhythm', name='Kick', order=1,
        midi_filename='', content_json='[{"duration":"q"},{"duration":"q"}]'
    )
    harm = HolisticLine(
        holistic_exercise_id=ex.id, line_type='harmonic', name='Harmony', order=2,
        midi_filename='', content_json='[{"root_pc":0,"quality":"major","duration":"w"}]'
    )
    db.session.add_all([mel, rhy, harm])
    db.session.commit()
    return ex, mel, rhy, harm


def test_grade_holistic_attempt_keys_by_line_id():
    from app import grade_holistic_attempt
    ex, mel, rhy, harm = _make_exercise()

    user_data = {
        str(mel.id): [{"key": "c/4", "duration": "q"}, {"key": "d/4", "duration": "q"}],  # perfect
        str(rhy.id): [{"duration": "q"}, {"duration": "q"}],  # perfect
        str(harm.id): [{"root_pc": 0, "quality": "major", "duration": "w"}],  # perfect
    }
    scores, overall = grade_holistic_attempt(ex, user_data)

    assert scores[f'{mel.id}_pitch'] == 100.0
    assert scores[f'{mel.id}_duration'] == 100.0
    assert scores[f'{rhy.id}_duration'] == 100.0
    assert scores[f'{harm.id}_letter'] == 100.0
    assert scores[f'{harm.id}_quality'] == 100.0
    assert overall == 100.0


def test_grade_holistic_attempt_missing_line_data_scores_zero():
    from app import grade_holistic_attempt
    ex, mel, rhy, harm = _make_exercise()

    scores, overall = grade_holistic_attempt(ex, {})

    assert scores[f'{mel.id}_pitch'] == 0.0
    assert scores[f'{rhy.id}_duration'] == 0.0
    assert overall < 50.0
