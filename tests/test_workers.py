import numpy as np
import soundfile as sf
from PySide6.QtCore import QEventLoop

from choppeur.core.cache import AnalysisCache
from choppeur.core.models import Analysis, Candidate, CandidateType, Track
from choppeur.core.settings import Settings
from choppeur.gui import workers

SAMPLE_RATE = 22050


def _write_click_track(path, n_clicks=6, interval_seconds=0.5, sample_rate=SAMPLE_RATE):
    total_samples = int((n_clicks * interval_seconds + 0.5) * sample_rate)
    signal = np.zeros(total_samples, dtype=np.float32)
    click_len = int(0.01 * sample_rate)
    rng = np.random.default_rng(0)
    for i in range(n_clicks):
        start = int(i * interval_seconds * sample_rate)
        signal[start : start + click_len] += rng.uniform(-1.0, 1.0, click_len)
    sf.write(str(path), signal, sample_rate, subtype="PCM_24")


def _track(path) -> Track:
    return Track(
        path=path,
        artist="Burial",
        album="Untrue",
        title="Etched Headplate",
        track_number=3,
        duration_seconds=3.5,
        sample_rate=SAMPLE_RATE,
    )


def _fake_analyze_rhythm(path, *, device):
    return 120.0, (0.0, 0.5, 1.0, 1.5, 2.0, 2.5), (0.0, 2.0)


def test_analyze_track_returns_candidates_and_fills_cache(tmp_path, monkeypatch):
    audio_path = tmp_path / "track.wav"
    _write_click_track(audio_path)
    track = _track(audio_path)
    monkeypatch.setattr(workers.rhythm, "analyze_rhythm", _fake_analyze_rhythm)

    with AnalysisCache(tmp_path / "cache.sqlite") as cache:
        assert cache.get(track) is None

        analysis, candidates = workers.analyze_track(track, Settings(), cache)

        assert analysis.tempo_bpm == 120.0
        assert len(candidates) > 0
        assert cache.get(track) == analysis


def test_analyze_track_uses_cache_without_recomputing_rhythm(tmp_path, monkeypatch):
    audio_path = tmp_path / "track.wav"
    _write_click_track(audio_path)
    track = _track(audio_path)
    monkeypatch.setattr(workers.rhythm, "analyze_rhythm", _fake_analyze_rhythm)

    with AnalysisCache(tmp_path / "cache.sqlite") as cache:
        workers.analyze_track(track, Settings(), cache)

        def _boom(*args, **kwargs):
            raise AssertionError("analyze_rhythm ne doit pas être rappelé : le cache doit suffire")

        monkeypatch.setattr(workers.rhythm, "analyze_rhythm", _boom)

        analysis, candidates = workers.analyze_track(track, Settings(), cache)
        assert analysis.tempo_bpm == 120.0
        assert len(candidates) > 0


def test_track_analysis_worker_emits_finished(monkeypatch, tmp_path):
    track = _track(tmp_path / "track.wav")
    fake_analysis = Analysis(track=track, tempo_bpm=120.0, beat_times=(), downbeat_times=())
    fake_candidates = [
        Candidate(type=CandidateType.ONE_SHOT, start_seconds=0.0, end_seconds=0.2, score=1.0)
    ]
    monkeypatch.setattr(
        workers, "analyze_track", lambda *a, **k: (fake_analysis, fake_candidates)
    )

    worker = workers.TrackAnalysisWorker(track, Settings())
    received = []
    worker.finished.connect(lambda analysis, candidates: received.append((analysis, candidates)))

    worker.run()

    assert received == [(fake_analysis, fake_candidates)]


def test_track_analysis_worker_emits_failed_on_error(monkeypatch, tmp_path):
    track = _track(tmp_path / "track.wav")

    def _boom(*args, **kwargs):
        raise RuntimeError("échec de décodage")

    monkeypatch.setattr(workers, "analyze_track", _boom)

    worker = workers.TrackAnalysisWorker(track, Settings())
    received = []
    worker.failed.connect(received.append)

    worker.run()

    assert received == ["échec de décodage"]


def test_album_analysis_worker_processes_all_tracks_with_progress(monkeypatch, tmp_path):
    tracks = [_track(tmp_path / f"track{i}.wav") for i in range(3)]

    def _fake_analyze(track, settings, cache=None):
        analysis = Analysis(track=track, tempo_bpm=120.0, beat_times=(), downbeat_times=())
        return analysis, []

    monkeypatch.setattr(workers, "analyze_track", _fake_analyze)

    worker = workers.AlbumAnalysisWorker(tracks, Settings())
    progress_events = []
    done_events = []
    finished_events = []
    worker.progress.connect(lambda done, total: progress_events.append((done, total)))
    worker.track_done.connect(lambda analysis, candidates: done_events.append(analysis))
    worker.finished.connect(lambda: finished_events.append(True))

    worker.run()

    assert progress_events == [(1, 3), (2, 3), (3, 3)]
    assert len(done_events) == 3
    assert finished_events == [True]


def test_album_analysis_worker_continues_after_one_track_fails(monkeypatch, tmp_path):
    tracks = [_track(tmp_path / f"track{i}.wav") for i in range(3)]

    def _fake_analyze(track, settings, cache=None):
        if track.path.name == "track1.wav":
            raise RuntimeError("piste corrompue")
        return Analysis(track=track, tempo_bpm=120.0, beat_times=(), downbeat_times=()), []

    monkeypatch.setattr(workers, "analyze_track", _fake_analyze)

    worker = workers.AlbumAnalysisWorker(tracks, Settings())
    failed_events = []
    done_events = []
    worker.track_failed.connect(lambda track, message: failed_events.append((track, message)))
    worker.track_done.connect(lambda analysis, candidates: done_events.append(analysis))

    worker.run()

    assert len(failed_events) == 1
    assert failed_events[0][1] == "piste corrompue"
    assert len(done_events) == 2


def test_album_analysis_worker_stop_before_run_processes_nothing(monkeypatch, tmp_path):
    tracks = [_track(tmp_path / "track0.wav")]
    monkeypatch.setattr(
        workers,
        "analyze_track",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("ne doit pas être appelé")),
    )

    worker = workers.AlbumAnalysisWorker(tracks, Settings())
    worker.stop()
    finished_events = []
    worker.finished.connect(lambda: finished_events.append(True))

    worker.run()

    assert finished_events == [True]


def test_start_in_thread_runs_worker_to_completion(qapp, monkeypatch, tmp_path):
    track = _track(tmp_path / "track.wav")
    fake_analysis = Analysis(track=track, tempo_bpm=120.0, beat_times=(), downbeat_times=())
    monkeypatch.setattr(workers, "analyze_track", lambda *a, **k: (fake_analysis, []))

    worker = workers.TrackAnalysisWorker(track, Settings())
    received = []
    worker.finished.connect(lambda analysis, candidates: received.append(analysis))

    thread = workers.start_in_thread(worker)

    # worker.finished est émis depuis le thread d'analyse ; le "quit" du thread
    # (connecté dans start_in_thread) est donc livré en connexion "queued" et a
    # besoin que la boucle d'évènements du thread principal tourne pour être
    # traité. On la fait tourner jusqu'à la fin de l'analyse (ou timeout).
    loop = QEventLoop()
    worker.finished.connect(lambda *_: loop.quit())
    thread.start()
    loop.exec()

    assert thread.wait(5000), "le thread d'analyse ne s'est pas terminé à temps"
    assert received == [fake_analysis]
