from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from choppeur.core import audio_io, onsets, rhythm
from choppeur.core import candidates as candidates_module
from choppeur.core.cache import AnalysisCache
from choppeur.core.models import Analysis, Candidate, Track
from choppeur.core.settings import Settings


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
        except Exception as exc:  # remonté à l'interface plutôt qu'avalé
            self.failed.emit(str(exc))
        else:
            self.finished.emit(analysis, candidates)


class AlbumAnalysisWorker(QObject):
    """Analyse toutes les pistes d'un album l'une après l'autre, avec progression."""

    progress = Signal(int, int)  # (pistes traitées, total)
    track_done = Signal(object, list)  # Analysis, list[Candidate]
    track_failed = Signal(object, str)  # Track, message
    finished = Signal()

    def __init__(self, tracks: list[Track], settings: Settings, cache: AnalysisCache | None = None):
        super().__init__()
        self._tracks = tracks
        self._settings = settings
        self._cache = cache
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:
        total = len(self._tracks)
        for index, track in enumerate(self._tracks, start=1):
            if self._stop_requested:
                break
            try:
                analysis, candidates = analyze_track(track, self._settings, self._cache)
            except Exception as exc:
                self.track_failed.emit(track, str(exc))
            else:
                self.track_done.emit(analysis, candidates)
            self.progress.emit(index, total)
        self.finished.emit()


def start_in_thread(worker: QObject) -> QThread:
    """Câblage standard Qt : lance worker.run() dans un nouveau QThread au démarrage,
    et détruit le thread une fois worker.finished émis."""
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    thread.finished.connect(thread.deleteLater)
    return thread
