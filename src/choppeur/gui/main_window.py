from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from choppeur.core import audio_io
from choppeur.core.audio_io import AUDIO_EXTENSIONS
from choppeur.core.cache import AnalysisCache
from choppeur.core.models import Analysis, Candidate, Track
from choppeur.core.settings import (
    Settings,
    default_cache_path,
    load_settings,
    save_settings,
)
from choppeur.gui.candidates_panel import CandidatesPanel
from choppeur.gui.library_panel import LibraryPanel
from choppeur.gui.settings_dialog import SettingsDialog
from choppeur.gui.waveform_view import WaveformView
from choppeur.gui.workers import AlbumAnalysisWorker, TrackAnalysisWorker, start_in_thread


def _tracks_in_folder(folder: Path) -> list[Track]:
    paths = sorted(
        p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
    )
    return [audio_io.read_track(p) for p in paths]


class MainWindow(QMainWindow):
    """Fenêtre principale : bibliothèque, forme d'onde, candidats, paramètres."""

    def __init__(
        self,
        settings: Settings | None = None,
        cache: AnalysisCache | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Choppeur")
        self.resize(1100, 700)

        self.settings = settings if settings is not None else load_settings()
        self.cache = cache if cache is not None else AnalysisCache(default_cache_path())

        self._current_track: Track | None = None
        self._current_folder: Path | None = None
        self._thread: QThread | None = None
        self._worker: QObject | None = None  # référence gardée : PySide6 ne la garde pas seul

        self.library_panel = LibraryPanel()
        self.waveform_view = WaveformView()
        self.candidates_panel = CandidatesPanel()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        open_library_button = QPushButton("Ouvrir une bibliothèque…")
        open_library_button.clicked.connect(self._on_open_library_clicked)

        self.analyze_album_button = QPushButton("Analyser l'album entier")
        self.analyze_album_button.setEnabled(False)
        self.analyze_album_button.clicked.connect(self._on_analyze_album_clicked)

        settings_button = QPushButton("Paramètres…")
        settings_button.clicked.connect(self._on_settings_clicked)

        top_buttons = QHBoxLayout()
        top_buttons.addWidget(open_library_button)
        top_buttons.addWidget(self.analyze_album_button)
        top_buttons.addStretch(1)
        top_buttons.addWidget(settings_button)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(self.waveform_view)
        right_layout.addWidget(self.candidates_panel)
        right_layout.addWidget(self.progress_bar)

        splitter = QSplitter()
        splitter.addWidget(self.library_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 1)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.addLayout(top_buttons)
        central_layout.addWidget(splitter)
        self.setCentralWidget(central)

        self.library_panel.track_selected.connect(self._on_track_selected)
        self.library_panel.folder_selected.connect(self._on_folder_selected)
        self.library_panel.load_failed.connect(self._on_library_load_failed)
        self.candidates_panel.export_requested.connect(self._on_export_requested)
        self.candidates_panel.preview_failed.connect(self._on_preview_failed)

        if self.settings.library_root:
            self.library_panel.set_root(Path(self.settings.library_root))

    # --- bibliothèque ---------------------------------------------------

    def _on_open_library_clicked(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Dossier racine de la bibliothèque")
        if not directory:
            return
        self.settings.library_root = directory
        save_settings(self.settings)
        self.library_panel.set_root(Path(directory))

    def _on_folder_selected(self, folder: Path) -> None:
        self._current_folder = folder
        self.analyze_album_button.setEnabled(True)

    def _on_library_load_failed(self, folder: Path, message: str) -> None:
        self.status_bar.showMessage(f"Impossible de lire {folder} : {message}", 8000)

    # --- analyse d'une piste ---------------------------------------------

    def _on_track_selected(self, path: Path) -> None:
        track = audio_io.read_track(path)
        self._current_track = track
        self.status_bar.showMessage(f"Analyse de {track.title}…")

        worker = TrackAnalysisWorker(track, self.settings, self.cache)
        worker.finished.connect(self._on_track_analyzed)
        worker.failed.connect(self._on_track_failed)
        self._run_worker(worker)

    def _on_track_analyzed(self, analysis: Analysis, candidates: list[Candidate]) -> None:
        samples, sample_rate = audio_io.load(analysis.track.path)

        self.waveform_view.set_waveform(samples, sample_rate)
        self.waveform_view.set_candidates(candidates)
        self.candidates_panel.set_candidates(samples, sample_rate, analysis.track, candidates)

        self.status_bar.showMessage(
            f"{analysis.track.title} — {round(analysis.tempo_bpm)} BPM, "
            f"{len(candidates)} candidats",
            5000,
        )

    def _on_track_failed(self, message: str) -> None:
        self.status_bar.showMessage(f"Échec de l'analyse : {message}", 8000)

    # --- analyse d'un album entier ---------------------------------------

    def _on_analyze_album_clicked(self) -> None:
        if self._current_folder is None:
            QMessageBox.information(self, "Choppeur", "Sélectionnez d'abord un dossier d'album.")
            return

        tracks = _tracks_in_folder(self._current_folder)
        if not tracks:
            QMessageBox.information(self, "Choppeur", "Aucun fichier audio dans ce dossier.")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(tracks))
        self.progress_bar.setValue(0)
        self.analyze_album_button.setEnabled(False)

        worker = AlbumAnalysisWorker(tracks, self.settings, self.cache)
        worker.progress.connect(self._on_album_progress)
        worker.track_failed.connect(self._on_album_track_failed)
        worker.finished.connect(self._on_album_finished)
        self._run_worker(worker)

    def _on_album_progress(self, done: int, total: int) -> None:
        self.progress_bar.setValue(done)
        self.status_bar.showMessage(f"Analyse de l'album : {done}/{total} pistes")

    def _on_album_track_failed(self, track: Track, message: str) -> None:
        self.status_bar.showMessage(f"{track.title} : échec ({message})", 8000)

    def _on_album_finished(self) -> None:
        self.progress_bar.setVisible(False)
        self.analyze_album_button.setEnabled(True)
        self.status_bar.showMessage("Analyse de l'album terminée", 5000)

    # --- paramètres -------------------------------------------------------

    def _on_settings_clicked(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = dialog.settings()
            save_settings(self.settings)

    # --- préécoute -------------------------------------------------------

    def _on_preview_failed(self, message: str) -> None:
        self.status_bar.showMessage(message, 8000)

    # --- export -------------------------------------------------------

    def _on_export_requested(self, candidates: list[Candidate]) -> None:
        if not candidates:
            QMessageBox.information(self, "Choppeur", "Aucun candidat coché à exporter.")
            return

        start_dir = self.settings.export_dir or str(Path.home())
        directory = QFileDialog.getExistingDirectory(self, "Dossier d'export", start_dir)
        if not directory:
            return

        exported = self.candidates_panel.export_checked(Path(directory))
        self.status_bar.showMessage(f"{len(exported)} fichier(s) exporté(s)", 5000)

    # --- infrastructure -------------------------------------------------

    def _run_worker(self, worker: QObject) -> None:
        self._worker = worker  # évite que Python ne le détruise pendant l'exécution
        self._thread = start_in_thread(worker)
        self._thread.start()

    def closeEvent(self, event) -> None:  # noqa: N802 - signature imposée par Qt
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        self.cache.close()
        super().closeEvent(event)
