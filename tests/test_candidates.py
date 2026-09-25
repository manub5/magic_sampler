import numpy as np

from choppeur.core import candidates
from choppeur.core.models import CandidateType

SAMPLE_RATE = 22050


def _make_loopable_signal(duration_seconds=9.0, sample_rate=SAMPLE_RATE):
    t = np.linspace(0, duration_seconds, int(duration_seconds * sample_rate), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)


def test_find_loop_candidates_respects_bar_alignment_and_duration():
    signal = _make_loopable_signal(duration_seconds=9.0)
    downbeat_times = (0.0, 2.0, 4.0, 6.0, 8.0)  # 120 BPM, 4 temps/mesure -> 2s/mesure

    result = candidates.find_loop_candidates(
        signal, SAMPLE_RATE, tempo_bpm=120.0, downbeat_times=downbeat_times,
        lengths_bars=(1, 2),
    )

    assert len(result) > 0
    duration = len(signal) / SAMPLE_RATE
    for candidate in result:
        assert candidate.type is CandidateType.LOOP
        assert candidate.bars in (1, 2)
        assert candidate.start_seconds in downbeat_times
        assert candidate.end_seconds <= duration + 1e-9
        assert candidate.bpm == 120.0

    scores = [c.score for c in result]
    assert scores == sorted(scores, reverse=True)


def test_find_loop_candidates_empty_without_enough_downbeats():
    signal = _make_loopable_signal(duration_seconds=2.0)
    assert candidates.find_loop_candidates(signal, SAMPLE_RATE, 120.0, (0.0,)) == []
    assert candidates.find_loop_candidates(signal, SAMPLE_RATE, 0.0, (0.0, 1.0)) == []


def _click_track(n_clicks=4, interval_seconds=0.5, sample_rate=SAMPLE_RATE):
    total_samples = int((n_clicks * interval_seconds + 0.5) * sample_rate)
    signal = np.zeros(total_samples, dtype=np.float32)
    click_len = int(0.01 * sample_rate)
    rng = np.random.default_rng(0)
    onset_times = []
    for i in range(n_clicks):
        start = int(i * interval_seconds * sample_rate)
        signal[start : start + click_len] += rng.uniform(-1.0, 1.0, click_len)
        onset_times.append(start / sample_rate)
    return signal, tuple(onset_times)


def test_find_one_shot_candidates_one_per_onset_with_short_duration():
    signal, onset_times = _click_track(n_clicks=4, interval_seconds=0.5)

    result = candidates.find_one_shot_candidates(
        signal, SAMPLE_RATE, onset_times, max_duration_seconds=0.4
    )

    assert len(result) == len(onset_times)
    for candidate in result:
        assert candidate.type is CandidateType.ONE_SHOT
        assert candidate.start_seconds in onset_times
        assert candidate.end_seconds > candidate.start_seconds
        assert candidate.duration_seconds <= 0.4 + 1e-9

    scores = [c.score for c in result]
    assert scores == sorted(scores, reverse=True)
