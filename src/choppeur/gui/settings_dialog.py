from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from choppeur.core.settings import Settings


class SettingsDialog(QDialog):
    """Fenêtre de paramètres (voir docs/SPEC.md « Paramètres »)."""

    def __init__(self, settings: Settings, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Paramètres")

        self._library_root = QLineEdit(settings.library_root or "")
        self._export_dir = QLineEdit(settings.export_dir or "")

        self._export_format = QComboBox()
        self._export_format.addItems(["wav", "flac"])
        self._export_format.setCurrentText(settings.export_format)

        self._loop_lengths_bars = QLineEdit(",".join(str(bars) for bars in settings.loop_lengths_bars))

        self._candidates_per_track = QSpinBox()
        self._candidates_per_track.setRange(1, 50)
        self._candidates_per_track.setValue(settings.candidates_per_track)

        self._max_one_shot_seconds = QDoubleSpinBox()
        self._max_one_shot_seconds.setRange(0.1, 30.0)
        self._max_one_shot_seconds.setSingleStep(0.1)
        self._max_one_shot_seconds.setValue(settings.max_one_shot_seconds)

        self._gpu_mode = QComboBox()
        self._gpu_mode.addItems(["auto", "cpu"])
        self._gpu_mode.setCurrentText(settings.gpu_mode)

        form = QFormLayout()
        form.addRow(
            "Dossier racine de la bibliothèque",
            self._row_with_browse(self._library_root, self._browse_library_root),
        )
        form.addRow(
            "Dossier cible d'export", self._row_with_browse(self._export_dir, self._browse_export_dir)
        )
        form.addRow("Format d'export", self._export_format)
        form.addRow("Longueurs de boucle (mesures, séparées par des virgules)", self._loop_lengths_bars)
        form.addRow("Nombre de candidats par piste", self._candidates_per_track)
        form.addRow("Durée maximale d'un one-shot (s)", self._max_one_shot_seconds)
        form.addRow("Utilisation du GPU", self._gpu_mode)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @staticmethod
    def _row_with_browse(line_edit: QLineEdit, on_browse) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(line_edit)
        button = QPushButton("Parcourir…")
        button.clicked.connect(on_browse)
        row.addWidget(button)
        return row

    def _browse_library_root(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Dossier racine de la bibliothèque")
        if directory:
            self._library_root.setText(directory)

    def _browse_export_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Dossier cible d'export")
        if directory:
            self._export_dir.setText(directory)

    def settings(self) -> Settings:
        lengths = tuple(int(value) for value in self._loop_lengths_bars.text().split(",") if value.strip())
        return Settings(
            library_root=self._library_root.text() or None,
            export_dir=self._export_dir.text() or None,
            export_format=self._export_format.currentText(),
            loop_lengths_bars=lengths,
            candidates_per_track=self._candidates_per_track.value(),
            max_one_shot_seconds=self._max_one_shot_seconds.value(),
            gpu_mode=self._gpu_mode.currentText(),
        )
