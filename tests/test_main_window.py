import time

import numpy as np
import pytest
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


@pytest.fixture
def make_window(tmp_path):
    """Fabrique de MainWindow qui ferme proprement chaque fenêtre créée (et
    attend la fin de son éventuel QThread d'analyse) à la fin du test.
    Sans ça, un thread encore en cours à la sortie du process pytest peut
    provoquer un plantage natif au lieu d'une simple erreur Python."""
    created: list[MainWindow] = []

    def _factory(**settings_kwargs) -> MainWindow:
        settings = Settings(**settings_kwargs)
        cache = AnalysisCache(tmp_path / f"cache-{len(created)}.sqlite")
        window = MainWindow(settings=settings, cache=cache)
        created.append(window)
        return window

    yield _factory

    for window in created:
        window.close()


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
    candidates = [Candidate(type=CandidateType.ONE_SHOT, start_seconds=0.0, end_seconds=0.1, score=1.0)]
    return analysis, candidates


def test_window_starts_with_album_analysis_disabled(qapp, make_window, tmp_path):
    window = make_window()
    assert window.windowTitle() == "Choppeur"
    assert window.analyze_album_button.isEnabled() is False


def test_selecting_a_folder_enables_album_analysis(qapp, make_window, tmp_path):
    album, _ = _make_library(tmp_path)
    window = make_window()
    window.library_panel.set_root(tmp_path)

    window.library_panel.topLevelItem(0).setSelected(True)

    assert window.analyze_album_button.isEnabled() is True
    assert window._current_folder == album


def test_library_load_failure_is_shown_in_status_bar(qapp, make_window, tmp_path):
    window = make_window()
    not_a_folder = tmp_path / "not_a_folder"
    not_a_folder.write_bytes(b"")

    window.library_panel.set_root(not_a_folder)

    assert "Impossible de lire" in window.status_bar.currentMessage()


def test_selecting_a_track_runs_analysis_and_updates_panels(qapp, make_window, monkeypatch, tmp_path):
    _, paths = _make_library(tmp_path, n_tracks=1)
    monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)

    window = make_window()
    window._on_track_selected(paths[0])

    _pump_until(lambda: window.candidates_panel._list.count() > 0)

    assert window.candidates_panel._list.count() == 1
    assert window.waveform_view._waveform_item is not None


def test_second_track_selection_while_busy_does_not_replace_running_thread(
    qapp, make_window, monkeypatch, tmp_path
):
    """
    Reproduit un vrai plantage trouvé en revue de code : sélectionner une
    deuxième piste pendant qu'une analyse tourne déjà remplaçait la seule
    référence Python vers le QThread en cours, que Qt détruisait alors que
    le thread tournait encore (SIGABRT/SIGBUS observés en pratique).
    """
    _, paths = _make_library(tmp_path, n_tracks=2)
    monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)
    window = make_window()

    window._on_track_selected(paths[0])
    first_thread = window._thread
    assert first_thread is not None
    assert first_thread.isRunning()

    window._on_track_selected(paths[1])  # ne doit pas remplacer le thread en cours

    assert window._thread is first_thread
    assert "en cours" in window.status_bar.currentMessage()

    _pump_until(lambda: window.candidates_panel._list.count() > 0)


def test_library_panel_disabled_while_a_track_analysis_runs(qapp, make_window, monkeypatch, tmp_path):
    _, paths = _make_library(tmp_path, n_tracks=1)
    monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)
    window = make_window()

    window._on_track_selected(paths[0])
    assert window.library_panel.isEnabled() is False

    _pump_until(lambda: window.candidates_panel._list.count() > 0)
    assert window.library_panel.isEnabled() is True


def test_analyzing_an_album_reports_progress_and_reenables_button(qapp, make_window, monkeypatch, tmp_path):
    album, _paths = _make_library(tmp_path, n_tracks=2)
    monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)

    window = make_window()
    window._current_folder = album

    window._on_analyze_album_clicked()

    _pump_until(window.analyze_album_button.isEnabled)

    assert window.progress_bar.isVisible() is False
    assert window.progress_bar.maximum() == 2


def test_analyze_album_does_not_scan_the_folder_on_the_gui_thread(qapp, make_window, monkeypatch, tmp_path):
    """
    Bug de performance trouvé en revue de code : le dossier était parcouru
    (avec lecture des tags de chaque piste) directement dans
    _on_analyze_album_clicked, avant même de démarrer le thread d'analyse.
    Sur un dossier réseau avec des milliers de pistes, ça gelait l'interface
    avant même que la barre de progression n'apparaisse. Le parcours doit
    se faire dans le thread d'arrière-plan (AlbumAnalysisWorker.run).
    """
    album, _paths = _make_library(tmp_path, n_tracks=2)
    monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)

    window = make_window()
    window._current_folder = album

    window._on_analyze_album_clicked()

    # Juste après l'appel (avant tout traitement d'évènements), le dossier ne
    # doit pas encore avoir été scanné : la barre est indéterminée (0, 0).
    assert window.progress_bar.maximum() == 0

    _pump_until(window.analyze_album_button.isEnabled)
    assert window.progress_bar.maximum() == 2  # mis à jour une fois le scan terminé


def test_analyze_album_on_empty_folder_reports_no_audio_files(qapp, make_window, tmp_path):
    empty_album = tmp_path / "EmptyAlbum"
    empty_album.mkdir()

    window = make_window()
    window._current_folder = empty_album

    window._on_analyze_album_clicked()
    _pump_until(lambda: "Aucun fichier audio" in window.status_bar.currentMessage())


def test_analyze_album_reenables_ui_when_folder_becomes_unreachable(qapp, make_window, monkeypatch, tmp_path):
    """
    Un dossier réseau qui se déconnecte juste avant le scan ne doit jamais
    laisser l'interface bloquée en "analyse en cours" pour toujours.
    """
    album = tmp_path / "Album"
    album.mkdir()

    def _boom(folder):
        raise OSError("Input/output error")

    monkeypatch.setattr(workers, "tracks_in_folder", _boom)

    window = make_window()
    window._current_folder = album

    window._on_analyze_album_clicked()
    _pump_until(window.analyze_album_button.isEnabled)

    assert "inaccessible" in window.status_bar.currentMessage()
    assert window.library_panel.isEnabled() is True


def test_settings_dialog_accepted_updates_and_saves_settings(qapp, make_window, monkeypatch, tmp_path):
    window = make_window()
    new_settings = Settings(export_format="flac")

    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr("choppeur.gui.settings_dialog.SettingsDialog.settings", lambda self: new_settings)
    saved = []
    monkeypatch.setattr(main_window_module, "save_settings", saved.append)

    window._on_settings_clicked()

    assert window.settings == new_settings
    assert saved == [new_settings]


def test_export_flow_writes_checked_candidate_to_chosen_directory(qapp, make_window, monkeypatch, tmp_path):
    _, paths = _make_library(tmp_path, n_tracks=1)
    monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)

    window = make_window()
    window._on_track_selected(paths[0])
    _pump_until(lambda: window.candidates_panel._list.count() > 0)

    window.candidates_panel._list.item(0).setCheckState(Qt.CheckState.Checked)

    export_dir = tmp_path / "export"
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args, **kwargs: str(export_dir))

    window._on_export_requested(window.candidates_panel.checked_candidates())

    exported_files = list(export_dir.glob("*.wav"))
    assert len(exported_files) == 1


def test_export_respects_the_flac_format_setting(qapp, make_window, monkeypatch, tmp_path):
    """
    Bug réel trouvé en revue de code : _on_export_requested n'a jamais lu
    self.settings.export_format, donc régler "Format d'export" sur FLAC dans
    les paramètres n'avait aucun effet — l'export produisait toujours du WAV.
    """
    _, paths = _make_library(tmp_path, n_tracks=1)
    monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)

    window = make_window(export_format="flac")
    window._on_track_selected(paths[0])
    _pump_until(lambda: window.candidates_panel._list.count() > 0)
    window.candidates_panel._list.item(0).setCheckState(Qt.CheckState.Checked)

    export_dir = tmp_path / "export"
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args, **kwargs: str(export_dir))

    window._on_export_requested(window.candidates_panel.checked_candidates())

    assert len(list(export_dir.glob("*.flac"))) == 1
    assert list(export_dir.glob("*.wav")) == []


def test_close_event_stops_album_worker_before_closing_the_cache(qapp, make_window, monkeypatch, tmp_path):
    """
    Bug réel trouvé en revue de code : fermer la fenêtre pendant une analyse
    d'album attendait un délai fixe de 2 s puis fermait le cache SQLite sans
    égard pour le thread d'analyse encore en cours, qui plantait ensuite sur
    "Cannot operate on a closed database" pour chaque piste restante.
    """
    _, paths = _make_library(tmp_path, n_tracks=5)

    def _slow_analyze(track, settings, cache=None):
        time.sleep(0.1)
        analysis = Analysis(track=track, tempo_bpm=120.0, beat_times=(), downbeat_times=())
        return analysis, []

    monkeypatch.setattr(workers, "analyze_track", _slow_analyze)

    window = make_window()
    window._current_folder = paths[0].parent
    window._on_analyze_album_clicked()

    running_worker = window._worker
    assert isinstance(running_worker, workers.AlbumAnalysisWorker)
    failures: list[str] = []
    running_worker.track_failed.connect(lambda track, message: failures.append(message))

    window.close()  # doit attendre la fin réelle du thread, pas un délai arbitraire

    assert running_worker._stop_requested is True
    assert not any("closed database" in message for message in failures)
