from __future__ import annotations

from pathlib import Path

import numpy as np
import sounddevice as sd
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from choppeur.core import audio_io
from choppeur.core.models import Candidate, CandidateType, Track


def _label_for(candidate: Candidate) -> str:
    minutes, seconds = divmod(int(candidate.start_seconds), 60)
    position = f"{minutes:02d}:{seconds:02d}"
    if candidate.type is CandidateType.LOOP:
        return f"Boucle {candidate.bars} mesures — {round(candidate.bpm or 0)} BPM — {position}"
    return f"One-shot — {position} (score {candidate.score:.2f})"


class CandidatesPanel(QWidget):
    """Liste des candidats d'une piste : cocher, préécouter (boucle répétée), exporter."""

    export_requested = Signal(list)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._samples: np.ndarray | None = None
        self._sample_rate: int = 0
        self._track: Track | None = None
        self._candidates: list[Candidate] = []

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self._preview_button = QPushButton("Préécouter")
        self._stop_button = QPushButton("Arrêter")
        self._export_button = QPushButton("Exporter la sélection")

        self._preview_button.clicked.connect(self._on_preview_clicked)
        self._stop_button.clicked.connect(self.stop_preview)
        self._export_button.clicked.connect(self._on_export_clicked)

        buttons = QHBoxLayout()
        buttons.addWidget(self._preview_button)
        buttons.addWidget(self._stop_button)
        buttons.addWidget(self._export_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._list)
        layout.addLayout(buttons)

    def set_candidates(
        self,
        samples: np.ndarray,
        sample_rate: int,
        track: Track,
        candidates: list[Candidate],
    ) -> None:
        self._samples = samples
        self._sample_rate = sample_rate
        self._track = track
        self._candidates = candidates

        self._list.clear()
        for candidate in candidates:
            item = QListWidgetItem(_label_for(candidate))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._list.addItem(item)

    def checked_candidates(self) -> list[Candidate]:
        return [
            self._candidates[i]
            for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _selected_candidate(self) -> Candidate | None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._candidates):
            return None
        return self._candidates[row]

    def _on_preview_clicked(self) -> None:
        candidate = self._selected_candidate()
        if candidate is not None:
            self.preview(candidate)

    def preview(self, candidate: Candidate) -> None:
        if self._samples is None:
            return
        start = round(candidate.start_seconds * self._sample_rate)
        end = round(candidate.end_seconds * self._sample_rate)
        segment = self._samples[start:end]
        loop = candidate.type is CandidateType.LOOP
        sd.play(segment, self._sample_rate, loop=loop)

    def stop_preview(self) -> None:
        sd.stop()

    def _on_export_clicked(self) -> None:
        self.export_requested.emit(self.checked_candidates())

    def export_checked(self, destination: Path) -> list[Path]:
        if self._samples is None or self._track is None:
            return []
        return audio_io.export_candidates(
            self._samples, self._sample_rate, self._track, self.checked_candidates(), destination
        )
