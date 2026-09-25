from __future__ import annotations

import numpy as np

from choppeur.core.models import Candidate, CandidateType

DEFAULT_LOOP_LENGTHS_BARS = (1, 2, 4, 8)
DEFAULT_MAX_ONE_SHOT_SECONDS = 2.0
DEFAULT_SILENCE_THRESHOLD_RATIO = 0.1


def _rms(samples: np.ndarray) -> float:
    if len(samples) == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples))))


def _bar_duration(downbeat_times: tuple[float, ...]) -> float | None:
    if len(downbeat_times) < 2:
        return None
    return float(np.median(np.diff(downbeat_times)))


def _regularity_score(downbeat_times: tuple[float, ...], start: float, end: float) -> float:
    """1.0 = tempo parfaitement régulier sur la zone, 0.0 = très irrégulier."""
    in_range = [t for t in downbeat_times if start <= t <= end]
    if len(in_range) < 3:
        return 0.5  # pas assez de mesures dans la zone pour juger : score neutre
    intervals = np.diff(in_range)
    mean_interval = float(np.mean(intervals))
    if mean_interval <= 0:
        return 0.0
    coefficient_of_variation = float(np.std(intervals)) / mean_interval
    return float(np.clip(1.0 - coefficient_of_variation, 0.0, 1.0))


def _cut_smoothness_score(samples: np.ndarray, sample_rate: int, end_seconds: float) -> float:
    """Score haut si le niveau juste avant la coupure est faible (pas de coupure brutale)."""
    window = int(0.03 * sample_rate)  # 30 ms
    end_index = round(end_seconds * sample_rate)
    start_index = max(0, end_index - window)
    tail_rms = _rms(samples[start_index:end_index])
    overall_rms = _rms(samples) or 1e-9
    ratio = tail_rms / overall_rms
    return float(np.clip(1.0 - ratio, 0.0, 1.0))


def find_loop_candidates(
    samples: np.ndarray,
    sample_rate: int,
    tempo_bpm: float,
    downbeat_times: tuple[float, ...],
    *,
    lengths_bars: tuple[int, ...] = DEFAULT_LOOP_LENGTHS_BARS,
    max_candidates: int = 8,
) -> list[Candidate]:
    """Candidats de boucles calées sur le premier temps de mesure, classés par score."""
    bar_duration = _bar_duration(downbeat_times)
    if bar_duration is None or tempo_bpm <= 0:
        return []

    duration_seconds = len(samples) / sample_rate
    overall_rms = _rms(samples) or 1e-9
    candidates: list[Candidate] = []

    for bars in lengths_bars:
        loop_duration = bar_duration * bars
        for start in downbeat_times:
            end = start + loop_duration
            if end > duration_seconds:
                continue

            start_index = round(start * sample_rate)
            end_index = round(end * sample_rate)
            segment = samples[start_index:end_index]

            regularity = _regularity_score(downbeat_times, start, end)
            energy_score = float(np.clip(_rms(segment) / overall_rms, 0.0, 1.0))
            smoothness = _cut_smoothness_score(samples, sample_rate, end)
            score = 0.5 * regularity + 0.3 * energy_score + 0.2 * smoothness

            candidates.append(
                Candidate(
                    type=CandidateType.LOOP,
                    start_seconds=start,
                    end_seconds=end,
                    score=score,
                    bpm=tempo_bpm,
                    bars=bars,
                )
            )

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:max_candidates]


def _find_return_to_silence(
    samples: np.ndarray, sample_rate: int, start: float, limit: float, threshold: float
) -> float:
    window = max(1, int(0.01 * sample_rate))  # fenêtres de 10 ms
    start_index = round(start * sample_rate)
    limit_index = round(limit * sample_rate)
    index = start_index + window
    while index < limit_index:
        if _rms(samples[index : index + window]) <= threshold:
            return index / sample_rate
        index += window
    return limit


def find_one_shot_candidates(
    samples: np.ndarray,
    sample_rate: int,
    onset_times: tuple[float, ...],
    *,
    max_duration_seconds: float = DEFAULT_MAX_ONE_SHOT_SECONDS,
    silence_threshold_ratio: float = DEFAULT_SILENCE_THRESHOLD_RATIO,
    max_candidates: int = 8,
) -> list[Candidate]:
    """Candidats one-shot : début sur une attaque, fin au retour au silence (ou attaque suivante)."""
    duration_seconds = len(samples) / sample_rate
    overall_peak = float(np.max(np.abs(samples))) if len(samples) else 0.0
    threshold = overall_peak * silence_threshold_ratio

    candidates: list[Candidate] = []
    for i, start in enumerate(onset_times):
        next_onset = onset_times[i + 1] if i + 1 < len(onset_times) else duration_seconds
        limit = min(start + max_duration_seconds, next_onset, duration_seconds)
        end = _find_return_to_silence(samples, sample_rate, start, limit, threshold)
        if end <= start:
            continue

        start_index = round(start * sample_rate)
        end_index = round(end * sample_rate)
        score = _rms(samples[start_index:end_index])

        candidates.append(
            Candidate(type=CandidateType.ONE_SHOT, start_seconds=start, end_seconds=end, score=score)
        )

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:max_candidates]
