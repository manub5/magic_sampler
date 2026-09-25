from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from choppeur.core.audio_io import AUDIO_EXTENSIONS

_PATH_ROLE = Qt.ItemDataRole.UserRole
_LOADING_PLACEHOLDER = "…"


class LibraryPanel(QTreeWidget):
    """Navigation dossiers -> albums -> pistes.

    Le contenu est chargé dossier par dossier, à l'ouverture (jamais toute
    l'arborescence d'un coup) : sur un NAS ou un dossier réseau, parcourir
    tout l'arbre à l'avance peut geler l'interface (chaque accès a une
    latence réseau) ou tourner indéfiniment sur un lien symbolique circulaire.
    """

    track_selected = Signal(Path)
    folder_selected = Signal(Path)
    load_failed = Signal(Path, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemExpanded.connect(self._on_item_expanded)

    def set_root(self, root: Path) -> None:
        self.clear()
        self._populate_level(self.invisibleRootItem(), root)

    def _populate_level(self, parent_item: QTreeWidgetItem, folder: Path) -> None:
        """Ajoute uniquement les enfants directs de `folder` (un seul niveau)."""
        try:
            entries = sorted(folder.iterdir(), key=lambda p: p.name.lower())
        except OSError as exc:
            # Dossier illisible (permissions, partage réseau déconnecté...) : on le
            # signale plutôt que de laisser un panneau vide sans explication.
            self.load_failed.emit(folder, str(exc))
            return

        for entry in entries:
            try:
                is_dir = entry.is_dir()
            except OSError:
                continue  # entrée inaccessible (lien cassé, droit réseau...) : ignorée

            if is_dir:
                item = QTreeWidgetItem(parent_item, [entry.name])
                item.setData(0, _PATH_ROLE, entry)
                # Enfant provisoire : le vrai contenu n'est lu qu'à l'ouverture du dossier.
                QTreeWidgetItem(item, [_LOADING_PLACEHOLDER])
            else:
                try:
                    # entry.exists() suit les liens symboliques : un lien cassé
                    # (fréquent sur un partage réseau) renvoie False sans lever
                    # d'exception, et n'est donc pas proposé comme piste.
                    is_audio = entry.suffix.lower() in AUDIO_EXTENSIONS and entry.exists()
                except OSError:
                    continue
                if is_audio:
                    item = QTreeWidgetItem(parent_item, [entry.name])
                    item.setData(0, _PATH_ROLE, entry)

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        if item.childCount() != 1 or item.child(0).text(0) != _LOADING_PLACEHOLDER:
            return  # déjà chargé, ou dossier vide
        item.takeChild(0)
        folder: Path | None = item.data(0, _PATH_ROLE)
        if folder is not None:
            self._populate_level(item, folder)

    def _on_selection_changed(self) -> None:
        items = self.selectedItems()
        if not items:
            return
        path: Path | None = items[0].data(0, _PATH_ROLE)
        if path is None:
            return
        if path.is_dir():
            self.folder_selected.emit(path)
        else:
            self.track_selected.emit(path)
