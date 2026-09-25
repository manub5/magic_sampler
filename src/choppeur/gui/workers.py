from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from choppeur.core import audio_io, onsets, rhythm
from choppeur.core import candidates as candidates_module
from choppeur.core.audio_io import AUDIO_EXTENSIONS
from choppeur.core.cache import AnalysisCache
from choppeur.core.models import Analysis, Candidate, Track
from choppeur.core.settings import Settings


def tracks_in_folder(folder: Path) -> list[Track]:
    """Pistes audio directement dans `folder` (un seul niveau, voir gui/library_panel.py),
    triées par nom. Lit les tags de chaque fichier (mutagen) : sur un dossier réseau
    avec des milliers de pistes, ça peut prendre du temps — à appeler depuis un thread
    d'arrière-plan (voir AlbumAnalysisWorker), jamais depuis le thread de l'interface."""
    paths = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS)
    return [audio_io.read_track(p) for p in paths]


def analyze_track(
    track: Track, settings: Settings, cache: AnalysisCache | None = None
) -> tuple[Analysis, list[Candidate]]:
    """Pipeline complet pour une piste : rythme + onsets (via le cache si possible),
    puis sélection des candidats boucles et one-shots."""
    analysis = cache.get(track) if cache else None
    samples, sample_rate = audio_io.load(track.path)

    if analysis is None:
        device = rhythm.resolve_device(settings.gpu_mode)
        tempo_bpm, beat_times, downbeat_times = rhythm.analyze_rhythm(track.path, device=device)
        onset_times = onsets.detect_onsets(samples, sample_rate)
        analysis = Analysis(
            track=track,
            tempo_bpm=tempo_bpm,
            beat_times=beat_times,
            downbeat_times=downbeat_times,
            onset_times=onset_times,
        )
        if cache:
            cache.set(analysis)

    loops = candidates_module.find_loop_candidates(
        samples,
        sample_rate,
        analysis.tempo_bpm,
        analysis.downbeat_times,
        lengths_bars=settings.loop_lengths_bars,
        max_candidates=settings.candidates_per_track,
    )
    shots = candidates_module.find_one_shot_candidates(
        samples,
        sample_rate,
        analysis.onset_times,
        max_duration_seconds=settings.max_one_shot_seconds,
        max_candidates=settings.candidates_per_track,
    )
    all_candidates = sorted(loops + shots, key=lambda c: c.score, reverse=True)
    return analysis, all_candidates


class TrackAnalysisWorker(QObject):
    """Analyse une piste ; à déplacer dans un QThread pour ne pas geler l'interface."""

    finished = Signal(object, list)  # Analysis, list[Candidate]
    failed = Signal(str)

    def __init__(self, track: Track, settings: Settings, cache: AnalysisCache | None = None):
        super().__init__()
        self._track = track
        self._settings = settings
        self._cache = cache

    def run(self) -> None:
        try:
            analysis, candidates = analyze_track(self._track, self._settings, self._cache)
        except Exception as exc:  # noqa: BLE001 - remonté à l'interface plutôt qu'avalé
            self.failed.emit(str(exc))
        else:
            self.finished.emit(analysis, candidates)


class AlbumAnalysisWorker(QObject):
    """Analyse toutes les pistes audio d'un dossier l'une après l'autre, avec progression.

    Le dossier est parcouru (et les tags de chaque piste lus) ici, dans run(),
    pas avant : sur un dossier réseau avec des milliers de pistes, ce
    parcours peut prendre du temps, et il ne doit jamais bloquer le thread
    de l'interface pendant qu'on affiche la barre de progression.
    """

    scan_done = Signal(int)  # nombre de pistes trouvées, une fois le dossier parcouru
    scan_failed = Signal(str)  # le dossier lui-même est devenu illisible (ex. NAS déconnecté)
    progress = Signal(int, int)  # (pistes traitées, total)
    track_done = Signal(object, list)  # Analysis, list[Candidate]
    track_failed = Signal(object, str)  # Track, message
    finished = Signal()

    def __init__(self, folder: Path, settings: Settings, cache: AnalysisCache | None = None):
        super().__init__()
        self._folder = folder
        self._settings = settings
        self._cache = cache
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:
        try:
            tracks = tracks_in_folder(self._folder)
        except OSError as exc:
            # Le dossier lui-même est devenu illisible en cours de route (NAS
            # déconnecté, dossier supprimé...) : sans ce garde-fou, l'exception
            # tuait run() avant finished.emit(), et plus rien ne redémarrait
            # jamais l'interface (bouton et bibliothèque restaient désactivés
            # indéfiniment, aucun signal pour le signaler).
            self.scan_failed.emit(str(exc))
            self.finished.emit()
            return

        self.scan_done.emit(len(tracks))

        total = len(tracks)
        for index, track in enumerate(tracks, start=1):
            if self._stop_requested:
                break
            try:
                analysis, candidates = analyze_track(track, self._settings, self._cache)
            except Exception as exc:  # noqa: BLE001 - une piste en erreur ne doit pas arrêter l'album
                self.track_failed.emit(track, str(exc))
            else:
                self.track_done.emit(analysis, candidates)
            self.progress.emit(index, total)
        self.finished.emit()


def start_in_thread(worker: TrackAnalysisWorker | AlbumAnalysisWorker) -> QThread:
    """Câblage standard Qt : lance worker.run() dans un nouveau QThread au démarrage,
    et détruit le thread une fois worker.finished émis."""
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    thread.finished.connect(thread.deleteLater)
    return thread
