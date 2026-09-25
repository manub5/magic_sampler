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
    preview_failed = Signal(str)

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
        """Le candidat sur la ligne courante, ou à défaut le premier coché
        (cocher une case ne place pas toujours la ligne "courante" au sens Qt)."""
        row = self._list.currentRow()
        if 0 <= row < len(self._candidates):
            return self._candidates[row]
        checked = self.checked_candidates()
        return checked[0] if checked else None

    def _on_preview_clicked(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None:
            self.preview_failed.emit("Sélectionnez ou cochez un candidat à préécouter.")
            return
        self.preview(candidate)

    def preview(self, candidate: Candidate) -> None:
        if self._samples is None:
            self.preview_failed.emit("Aucune piste chargée.")
            return

        start = max(0, round(candidate.start_seconds * self._sample_rate))
        end = min(len(self._samples), round(candidate.end_seconds * self._sample_rate))
        segment = self._samples[start:end]
        if len(segment) == 0:
            self.preview_failed.emit("Ce candidat est vide (durée nulle).")
            return

        loop = candidate.type is CandidateType.LOOP
        try:
            sd.play(segment, self._sample_rate, loop=loop)
        except Exception as exc:  # noqa: BLE001 - toute erreur PortAudio doit remonter à l'UI
            # Erreur PortAudio la plus fréquente en pratique : aucun périphérique de
            # sortie par défaut disponible/configuré. On la remonte au lieu de la
            # laisser disparaître silencieusement (Qt avale les exceptions des slots).
            self.preview_failed.emit(f"Échec de la préécoute : {exc}")

    def stop_preview(self) -> None:
        try:
            sd.stop()
        except Exception as exc:  # noqa: BLE001 - idem : ne jamais avaler silencieusement
            self.preview_failed.emit(f"Échec de l'arrêt de la préécoute : {exc}")

    def _on_export_clicked(self) -> None:
        self.export_requested.emit(self.checked_candidates())

    def export_checked(
        self, destination: Path, *, file_format: str = "wav", subtype: str = "PCM_24"
    ) -> list[Path]:
        if self._samples is None or self._track is None:
            return []
        return audio_io.export_candidates(
            self._samples,
            self._sample_rate,
            self._track,
            self.checked_candidates(),
            destination,
            file_format=file_format,
            subtype=subtype,
        )
