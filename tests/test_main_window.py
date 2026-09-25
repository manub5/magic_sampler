import time

import numpy as np
import soundfile as sf
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFileDialog

from choppeur.core.cache import AnalysisCache
from choppeur.core.models import Analysis, Candidate, CandidateType
from choppeur.core.settings import Settings
from choppeur.gui import main_window as main_window_module
from choppeur.gui import workers
from choppeur.gui.main_window import MainWindow

SAMPLE_RATE = 1000


def _pump_until(condition, timeout_seconds=3.0):
    from PySide6.QtCore import QCoreApplication

    deadline = time.monotonic() + timeout_seconds
    while not condition():
        QCoreApplication.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError("condition non atteinte à temps")


def _make_window(tmp_path, **settings_kwargs) -> MainWindow:
    settings = Settings(**settings_kwargs)
    cache = AnalysisCache(tmp_path / "cache.sqlite")
    return MainWindow(settings=settings, cache=cache)


def _make_library(root, n_tracks=2):
    album = root / "Album"
    album.mkdir()
    paths = []
    for i in range(n_tracks):
        path = album / f"{i:02d} - Track.wav"
        sf.write(str(path), np.zeros(SAMPLE_RATE, dtype="float32"), SAMPLE_RATE, subtype="PCM_16")
        paths.append(path)
    return album, paths


def _fake_analyze_track(track, settings, cache=None):
    analysis = Analysis(track=track, tempo_bpm=120.0, beat_times=(0.0, 0.5, 1.0), downbeat_times=(0.0,))
    candidates = [
        Candidate(type=CandidateType.ONE_SHOT, start_seconds=0.0, end_seconds=0.1, score=1.0)
    ]
    return analysis, candidates


def test_window_starts_with_album_analysis_disabled(qapp, tmp_path):
    window = _make_window(tmp_path)
    assert window.windowTitle() == "Choppeur"
    assert window.analyze_album_button.isEnabled() is False


def test_selecting_a_folder_enables_album_analysis(qapp, tmp_path):
    album, _ = _make_library(tmp_path)
    window = _make_window(tmp_path)
    window.library_panel.set_root(tmp_path)

    window.library_panel.topLevelItem(0).setSelected(True)

    assert window.analyze_album_button.isEnabled() is True
    assert window._current_folder == album


def test_selecting_a_track_runs_analysis_and_updates_panels(qapp, monkeypatch, tmp_path):
    _, paths = _make_library(tmp_path, n_tracks=1)
    monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)

    window = _make_window(tmp_path)
    window._on_track_selected(paths[0])

    _pump_until(lambda: window.candidates_panel._list.count() > 0)

    assert window.candidates_panel._list.count() == 1
    assert window.waveform_view._waveform_item is not None


def test_analyzing_an_album_reports_progress_and_reenables_button(qapp, monkeypatch, tmp_path):
    album, paths = _make_library(tmp_path, n_tracks=2)
    monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)

    window = _make_window(tmp_path)
    window._current_folder = album

    window._on_analyze_album_clicked()

    _pump_until(lambda: window.analyze_album_button.isEnabled())

    assert window.progress_bar.isVisible() is False
    assert window.progress_bar.maximum() == 2


def test_settings_dialog_accepted_updates_and_saves_settings(qapp, monkeypatch, tmp_path):
    window = _make_window(tmp_path)
    new_settings = Settings(export_format="flac")

    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(
        "choppeur.gui.settings_dialog.SettingsDialog.settings", lambda self: new_settings
    )
    saved = []
    monkeypatch.setattr(main_window_module, "save_settings", lambda settings: saved.append(settings))

    window._on_settings_clicked()

    assert window.settings == new_settings
    assert saved == [new_settings]


def test_export_flow_writes_checked_candidate_to_chosen_directory(qapp, monkeypatch, tmp_path):
    _, paths = _make_library(tmp_path, n_tracks=1)
    monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)

    window = _make_window(tmp_path)
    window._on_track_selected(paths[0])
    _pump_until(lambda: window.candidates_panel._list.count() > 0)

    window.candidates_panel._list.item(0).setCheckState(Qt.CheckState.Checked)

    export_dir = tmp_path / "export"
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *args, **kwargs: str(export_dir)
    )

    window._on_export_requested(window.candidates_panel.checked_candidates())

    exported_files = list(export_dir.glob("*.wav"))
    assert len(exported_files) == 1
