from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from beat_this.inference import File2Beats

_trackers: dict[tuple[str, str], File2Beats] = {}


def default_device() -> str:
    """auto : GPU si disponible, sinon CPU (voir docs/SPEC.md « Utilisation du GPU »)."""
    return "cuda" if torch.cuda.is_available() else "cpu"


def _get_tracker(checkpoint: str, device: str) -> File2Beats:
    key = (checkpoint, device)
    if key not in _trackers:
        _trackers[key] = File2Beats(checkpoint_path=checkpoint, device=device, dbn=False)
    return _trackers[key]


def estimate_tempo(beat_times: tuple[float, ...]) -> float:
    """BPM à partir de la médiane des intervalles entre temps (robuste aux erreurs isolées)."""
    if len(beat_times) < 2:
        return 0.0
    intervals = np.diff(np.asarray(beat_times, dtype=np.float64))
    median_interval = float(np.median(intervals))
    if median_interval <= 0:
        return 0.0
    return 60.0 / median_interval


def analyze_rhythm(
    path: Path, *, device: str | None = None, checkpoint: str = "final0"
) -> tuple[float, tuple[float, ...], tuple[float, ...]]:
    """
    Analyse un fichier audio avec beat_this.

    Retourne (tempo_bpm, temps, premiers_temps_de_mesure), tous les temps en secondes.
    """
    tracker = _get_tracker(checkpoint, device or default_device())
    beats, downbeats = tracker(str(path))
    beat_times = tuple(float(b) for b in beats)
    downbeat_times = tuple(float(b) for b in downbeats)
    return estimate_tempo(beat_times), beat_times, downbeat_times
