import numpy as np

from choppeur.core.models import Candidate, CandidateType
from choppeur.gui.waveform_view import WaveformView

SAMPLE_RATE = 22050


def test_set_waveform_plots_downsampled_data(qapp):
    view = WaveformView()
    samples = np.sin(np.linspace(0, 20, 50_000)).astype(np.float32)

    view.set_waveform(samples, SAMPLE_RATE, max_points=1_000)

    assert view._waveform_item is not None
    x_data, y_data = view._waveform_item.getData()
    assert len(x_data) <= 1_000
    assert len(x_data) == len(y_data)
    assert x_data[0] == 0.0


def test_set_waveform_keeps_short_signals_untouched(qapp):
    view = WaveformView()
    samples = np.zeros(100, dtype=np.float32)

    view.set_waveform(samples, SAMPLE_RATE, max_points=1_000)

    _, y_data = view._waveform_item.getData()
    assert len(y_data) == 100


def test_set_candidates_adds_two_marker_lines_per_candidate(qapp):
    view = WaveformView()
    view.set_waveform(np.zeros(1000, dtype=np.float32), SAMPLE_RATE)

    candidates = [
        Candidate(type=CandidateType.LOOP, start_seconds=0.0, end_seconds=1.0, score=1.0),
        Candidate(type=CandidateType.ONE_SHOT, start_seconds=2.0, end_seconds=2.2, score=0.5),
    ]

    view.set_candidates(candidates)

    assert len(view._marker_lines) == 4

    # Un second appel doit remplacer les marqueurs, pas les cumuler
    view.set_candidates(candidates[:1])
    assert len(view._marker_lines) == 2
