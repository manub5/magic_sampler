import os
import threading
import time
from pathlib import Path

from choppeur.core.cache import AnalysisCache
from choppeur.core.models import Analysis, Track


def _track(path: Path) -> Track:
    return Track(
        path=path,
        artist="Burial",
        album="Untrue",
        title="Etched Headplate",
        track_number=3,
        duration_seconds=240.0,
        sample_rate=44100,
    )


def _analysis(track: Track) -> Analysis:
    return Analysis(
        track=track,
        tempo_bpm=139.0,
        beat_times=(0.0, 0.5, 1.0),
        downbeat_times=(0.0, 2.0),
        onset_times=(0.1, 0.6),
    )


def test_cache_miss_then_hit(tmp_path):
    audio_path = tmp_path / "track.wav"
    audio_path.write_bytes(b"\x00" * 100)
    track = _track(audio_path)

    with AnalysisCache(tmp_path / "cache.sqlite") as cache:
        assert cache.get(track) is None

        analysis = _analysis(track)
        cache.set(analysis)

        cached = cache.get(track)
        assert cached == analysis


def test_cache_miss_after_file_changes(tmp_path):
    audio_path = tmp_path / "track.wav"
    audio_path.write_bytes(b"\x00" * 100)
    track = _track(audio_path)

    with AnalysisCache(tmp_path / "cache.sqlite") as cache:
        cache.set(_analysis(track))

        # Le fichier change (taille + date de modification différentes)
        time.sleep(0.01)
        audio_path.write_bytes(b"\x00" * 200)
        os.utime(audio_path, None)

        assert cache.get(track) is None


def test_cache_usable_from_a_different_thread_than_the_one_that_created_it(tmp_path):
    """
    Reproduit le bug réel de l'appli : le cache est créé dans le thread
    principal (MainWindow) mais interrogé/écrit depuis le QThread d'analyse.
    sqlite3 refuse ça par défaut (check_same_thread=True) et lève
    ProgrammingError — d'où check_same_thread=False + verrou dans
    AnalysisCache.
    """
    audio_path = tmp_path / "track.wav"
    audio_path.write_bytes(b"\x00" * 100)
    track = _track(audio_path)
    cache = AnalysisCache(tmp_path / "cache.sqlite")

    errors: list[Exception] = []

    def worker() -> None:
        try:
            cache.set(_analysis(track))
            cache.get(track)
        except Exception as exc:  # noqa: BLE001 - on veut capturer n'importe quelle erreur du thread
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=5)

    assert errors == []
    assert cache.get(track) == _analysis(track)
    cache.close()


def test_cache_persists_across_instances(tmp_path):
    audio_path = tmp_path / "track.wav"
    audio_path.write_bytes(b"\x00" * 100)
    track = _track(audio_path)
    database_path = tmp_path / "cache.sqlite"

    with AnalysisCache(database_path) as cache:
        cache.set(_analysis(track))

    with AnalysisCache(database_path) as cache:
        assert cache.get(track) == _analysis(track)
