from __future__ import annotations

import librosa
import numpy as np


def detect_onsets(samples: np.ndarray, sample_rate: int) -> tuple[float, ...]:
    """Instants d'attaque (secondes), pour repérer le début des one-shots."""
    onset_times = librosa.onset.onset_detect(y=samples, sr=sample_rate, units="time")
    return tuple(float(t) for t in onset_times)


def separate_percussive_harmonic(samples: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Sépare le signal en (percussif, harmonique)."""
    harmonic, percussive = librosa.effects.hpss(samples)
    return percussive, harmonic
