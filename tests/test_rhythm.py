import numpy as np
import pytest

from choppeur.core import rhythm


def test_estimate_tempo_from_regular_beats():
    # 120 BPM : un temps toutes les 0.5 seconde
    beat_times = tuple(np.arange(0, 10, 0.5))
    assert rhythm.estimate_tempo(beat_times) == pytest.approx(120.0, rel=1e-6)


def test_estimate_tempo_ignores_a_single_outlier_interval():
    # Un intervalle isolé abîmé ne doit pas casser l'estimation (médiane, pas moyenne)
    beat_times = (0.0, 0.5, 1.0, 1.5, 4.0, 4.5, 5.0)
    assert rhythm.estimate_tempo(beat_times) == pytest.approx(120.0, rel=1e-6)


def test_estimate_tempo_returns_zero_with_fewer_than_two_beats():
    assert rhythm.estimate_tempo(()) == 0.0
    assert rhythm.estimate_tempo((1.0,)) == 0.0


def test_analyze_rhythm_converts_tracker_output(monkeypatch, tmp_path):
    """
    Vérifie le câblage de analyze_rhythm sans télécharger le modèle beat_this
    (impossible dans cet environnement : cloud.cp.jku.at est bloqué par la
    politique réseau du bac à sable). Le tracker lui-même est simulé.
    """
    audio_path = tmp_path / "track.wav"
    audio_path.touch()

    class FakeTracker:
        def __call__(self, path: str):
            assert path == str(audio_path)
            return np.array([0.0, 0.5, 1.0, 1.5]), np.array([0.0, 1.0])

    monkeypatch.setattr(rhythm, "_get_tracker", lambda checkpoint, device: FakeTracker())

    tempo, beats, downbeats = rhythm.analyze_rhythm(audio_path, device="cpu")

    assert tempo == pytest.approx(120.0, rel=1e-6)
    assert beats == (0.0, 0.5, 1.0, 1.5)
    assert downbeats == (0.0, 1.0)
