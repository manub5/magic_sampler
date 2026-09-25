from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtGui import QColor

from choppeur.core.models import Candidate, CandidateType

_LOOP_COLOR = QColor("#4C9AFF")
_ONE_SHOT_COLOR = QColor("#FF8C42")


def _downsample(samples: np.ndarray, max_points: int) -> np.ndarray:
    if len(samples) <= max_points:
        return samples
    factor = int(np.ceil(len(samples) / max_points))
    return samples[::factor]


class WaveformView(pg.PlotWidget):
    """Forme d'onde d'une piste, avec les marqueurs de début/fin des candidats."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMenuEnabled(False)
        self.setLabel("bottom", "Temps", units="s")
        self.showAxis("left", False)
        self._waveform_item: pg.PlotDataItem | None = None
        self._marker_lines: list[pg.InfiniteLine] = []

    def set_waveform(
        self, samples: np.ndarray, sample_rate: int, *, max_points: int = 20_000
    ) -> None:
        self.clear()
        self._marker_lines = []

        downsampled = _downsample(samples, max_points)
        duration = len(samples) / sample_rate
        times = np.linspace(0, duration, num=len(downsampled), endpoint=False)
        self._waveform_item = self.plot(times, downsampled, pen=pg.mkPen(width=1))

    def set_candidates(self, candidates: list[Candidate]) -> None:
        for line in self._marker_lines:
            self.removeItem(line)
        self._marker_lines = []

        for candidate in candidates:
            color = _LOOP_COLOR if candidate.type is CandidateType.LOOP else _ONE_SHOT_COLOR
            for position in (candidate.start_seconds, candidate.end_seconds):
                line = pg.InfiniteLine(pos=position, angle=90, pen=pg.mkPen(color, width=1))
                self.addItem(line)
                self._marker_lines.append(line)
