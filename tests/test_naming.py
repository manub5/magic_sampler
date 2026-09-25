from pathlib import Path

from choppeur.core.models import Candidate, CandidateType, Track
from choppeur.core.naming import build_filename, unique_path


def _track(**overrides) -> Track:
    defaults = dict(
        path=Path("/library/Burial/Untrue/03 - Etched Headplate.mp3"),
        artist="Burial",
        album="Untrue",
        title="Etched Headplate",
        track_number=3,
        duration_seconds=240.0,
        sample_rate=44100,
    )
    defaults.update(overrides)
    return Track(**defaults)


def test_loop_filename_matches_spec_example():
    track = _track()
    candidate = Candidate(
        type=CandidateType.LOOP,
        start_seconds=72.0,
        end_seconds=72.0 + 4 * 60 / 139 * 4,
        score=0.9,
        bpm=139,
        bars=4,
    )
    assert build_filename(track, candidate) == "Burial_Untrue_03_loop_139bpm_4bars_01m12s.wav"


def test_one_shot_filename_matches_spec_example():
    track = _track()
    candidate = Candidate(
        type=CandidateType.ONE_SHOT,
        start_seconds=72.340,
        end_seconds=72.9,
        score=0.8,
    )
    assert build_filename(track, candidate) == "Burial_Untrue_03_shot_01m12s340.wav"


def test_forbidden_characters_are_cleaned():
    track = _track(artist="AC/DC", album='Live: "1992"')
    candidate = Candidate(
        type=CandidateType.ONE_SHOT, start_seconds=0.0, end_seconds=0.5, score=0.5
    )
    name = build_filename(track, candidate)
    assert "/" not in name
    assert '"' not in name
    assert ":" not in name


def test_unique_path_avoids_overwrite(tmp_path):
    (tmp_path / "sample.wav").touch()
    result = unique_path(tmp_path, "sample.wav")
    assert result == tmp_path / "sample_2.wav"

    (tmp_path / "sample_2.wav").touch()
    result = unique_path(tmp_path, "sample.wav")
    assert result == tmp_path / "sample_3.wav"


def test_unique_path_returns_original_when_free(tmp_path):
    result = unique_path(tmp_path, "sample.wav")
    assert result == tmp_path / "sample.wav"
