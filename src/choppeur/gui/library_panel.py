from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg", ".aiff", ".aif"}

_PATH_ROLE = Qt.ItemDataRole.UserRole


class LibraryPanel(QTreeWidget):
    """Navigation dossiers -> albums -> pistes d'une bibliothèque locale ou NAS montée."""

    track_selected = Signal(Path)
    folder_selected = Signal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.itemSelectionChanged.connect(self._on_selection_changed)

    def set_root(self, root: Path) -> None:
        self.clear()
        self._populate(self.invisibleRootItem(), root)

    def _populate(self, parent_item: QTreeWidgetItem, folder: Path) -> None:
        try:
            entries = sorted(folder.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            return

        for entry in entries:
            if entry.is_dir():
                item = QTreeWidgetItem(parent_item, [entry.name])
                item.setData(0, _PATH_ROLE, entry)
                self._populate(item, entry)
            elif entry.suffix.lower() in AUDIO_EXTENSIONS:
                item = QTreeWidgetItem(parent_item, [entry.name])
                item.setData(0, _PATH_ROLE, entry)

    def _on_selection_changed(self) -> None:
        items = self.selectedItems()
        if not items:
            return
        path: Path = items[0].data(0, _PATH_ROLE)
        if path is None:
            return
        if path.is_dir():
            self.folder_selected.emit(path)
        else:
            self.track_selected.emit(path)
