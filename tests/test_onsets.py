import numpy as np

from choppeur.core import onsets

SAMPLE_RATE = 22050


def _click_track(n_clicks=5, interval_seconds=0.5, sample_rate=SAMPLE_RATE):
    total_samples = int((n_clicks * interval_seconds + 0.5) * sample_rate)
    signal = np.zeros(total_samples, dtype=np.float32)
    click_len = int(0.01 * sample_rate)
    rng = np.random.default_rng(0)
    for i in range(n_clicks):
        start = int(i * interval_seconds * sample_rate)
        signal[start : start + click_len] += rng.uniform(-1.0, 1.0, click_len)
    return signal


def test_detect_onsets_finds_roughly_one_per_click():
    signal = _click_track(n_clicks=6, interval_seconds=0.5)

    onset_times = onsets.detect_onsets(signal, SAMPLE_RATE)

    assert len(onset_times) >= 5
    # Les attaques doivent être triées et rester dans la durée du signal
    assert list(onset_times) == sorted(onset_times)
    assert all(0 <= t <= len(signal) / SAMPLE_RATE for t in onset_times)


def test_separate_percussive_harmonic_preserves_length():
    signal = _click_track(n_clicks=4, interval_seconds=0.3)

    percussive, harmonic = onsets.separate_percussive_harmonic(signal)

    assert percussive.shape == signal.shape
    assert harmonic.shape == signal.shape
