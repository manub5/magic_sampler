from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt

from choppeur.core.models import Candidate, CandidateType, Track
from choppeur.gui.candidates_panel import CandidatesPanel

SAMPLE_RATE = 1000


def _track(tmp_path: Path) -> Track:
    return Track(
        path=tmp_path / "source.wav",
        artist="Burial",
        album="Untrue",
        title="Etched Headplate",
        track_number=3,
        duration_seconds=3.0,
        sample_rate=SAMPLE_RATE,
    )


def _candidates() -> list[Candidate]:
    return [
        Candidate(type=CandidateType.LOOP, start_seconds=0.0, end_seconds=1.0, score=1.0, bpm=120, bars=1),
        Candidate(type=CandidateType.ONE_SHOT, start_seconds=1.0, end_seconds=1.2, score=0.5),
    ]


def test_set_candidates_populates_list_unchecked(qapp, tmp_path):
    panel = CandidatesPanel()
    samples = np.zeros(SAMPLE_RATE * 3, dtype=np.float32)

    panel.set_candidates(samples, SAMPLE_RATE, _track(tmp_path), _candidates())

    assert panel._list.count() == 2
    assert panel.checked_candidates() == []
    assert "Boucle 1 mesures" in panel._list.item(0).text()
    assert "One-shot" in panel._list.item(1).text()


def test_checked_candidates_reflects_checkbox_state(qapp, tmp_path):
    panel = CandidatesPanel()
    samples = np.zeros(SAMPLE_RATE * 3, dtype=np.float32)
    candidates = _candidates()
    panel.set_candidates(samples, SAMPLE_RATE, _track(tmp_path), candidates)

    panel._list.item(1).setCheckState(Qt.CheckState.Checked)

    assert panel.checked_candidates() == [candidates[1]]


def test_preview_plays_selected_candidate_with_loop_flag(qapp, tmp_path, monkeypatch):
    panel = CandidatesPanel()
    samples = np.arange(SAMPLE_RATE * 3, dtype=np.float32)
    candidates = _candidates()
    panel.set_candidates(samples, SAMPLE_RATE, _track(tmp_path), candidates)

    calls = []
    monkeypatch.setattr(
        "choppeur.gui.candidates_panel.sd.play",
        lambda data, sample_rate, loop: calls.append((data, sample_rate, loop)),
    )

    panel.preview(candidates[0])

    assert len(calls) == 1
    data, sample_rate, loop = calls[0]
    assert sample_rate == SAMPLE_RATE
    assert loop is True
    assert len(data) == SAMPLE_RATE  # 1 seconde (0.0 -> 1.0s)


def test_preview_one_shot_does_not_loop(qapp, tmp_path, monkeypatch):
    panel = CandidatesPanel()
    samples = np.zeros(SAMPLE_RATE * 3, dtype=np.float32)
    candidates = _candidates()
    panel.set_candidates(samples, SAMPLE_RATE, _track(tmp_path), candidates)

    calls = []
    monkeypatch.setattr(
        "choppeur.gui.candidates_panel.sd.play",
        lambda data, sample_rate, loop: calls.append(loop),
    )

    panel.preview(candidates[1])

    assert calls == [False]


def test_stop_preview_calls_sounddevice_stop(qapp, monkeypatch):
    panel = CandidatesPanel()
    calls = []
    monkeypatch.setattr("choppeur.gui.candidates_panel.sd.stop", lambda: calls.append(True))

    panel.stop_preview()

    assert calls == [True]


def test_export_checked_writes_only_checked_candidates(qapp, tmp_path):
    panel = CandidatesPanel()
    samples = np.zeros(SAMPLE_RATE * 3, dtype=np.float32)
    candidates = _candidates()
    panel.set_candidates(samples, SAMPLE_RATE, _track(tmp_path), candidates)
    panel._list.item(0).setCheckState(Qt.CheckState.Checked)

    exported = panel.export_checked(tmp_path / "export")

    assert len(exported) == 1
    assert exported[0].exists()
    assert "loop" in exported[0].name


def test_export_button_emits_checked_candidates(qapp, tmp_path):
    panel = CandidatesPanel()
    samples = np.zeros(SAMPLE_RATE * 3, dtype=np.float32)
    candidates = _candidates()
    panel.set_candidates(samples, SAMPLE_RATE, _track(tmp_path), candidates)
    panel._list.item(1).setCheckState(Qt.CheckState.Checked)

    received = []
    panel.export_requested.connect(received.append)
    panel._export_button.click()

    assert received == [[candidates[1]]]
