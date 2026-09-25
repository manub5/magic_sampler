from pathlib import Path

from choppeur.gui.library_panel import LibraryPanel

_LOADING_PLACEHOLDER = "…"


def _make_library(root: Path) -> None:
    album_a = root / "AlbumA"
    album_a.mkdir()
    (album_a / "01 - Track One.wav").write_bytes(b"")
    (album_a / "cover.jpg").write_bytes(b"")  # ignoré : pas un fichier audio

    album_b = root / "AlbumB"
    album_b.mkdir()
    (album_b / "01 - Other.mp3").write_bytes(b"")


def _find_top_level(panel: LibraryPanel, name: str):
    return next(
        panel.topLevelItem(i)
        for i in range(panel.topLevelItemCount())
        if panel.topLevelItem(i).text(0) == name
    )


def test_set_root_lists_top_level_folders_without_descending(qapp, tmp_path):
    _make_library(tmp_path)
    panel = LibraryPanel()

    panel.set_root(tmp_path)

    assert panel.topLevelItemCount() == 2
    names = sorted(panel.topLevelItem(i).text(0) for i in range(panel.topLevelItemCount()))
    assert names == ["AlbumA", "AlbumB"]

    # Un seul niveau chargé : chaque dossier n'a qu'un enfant provisoire, pas
    # encore son contenu réel (indispensable pour ne pas geler sur un NAS).
    album_a_item = _find_top_level(panel, "AlbumA")
    assert album_a_item.childCount() == 1
    assert album_a_item.child(0).text(0) == _LOADING_PLACEHOLDER


def test_expanding_a_folder_loads_its_audio_files_only(qapp, tmp_path):
    _make_library(tmp_path)
    panel = LibraryPanel()
    panel.set_root(tmp_path)
    album_a_item = _find_top_level(panel, "AlbumA")

    panel.expandItem(album_a_item)

    child_names = sorted(
        album_a_item.child(i).text(0) for i in range(album_a_item.childCount())
    )
    assert child_names == ["01 - Track One.wav"]


def test_expanding_twice_does_not_duplicate_children(qapp, tmp_path):
    _make_library(tmp_path)
    panel = LibraryPanel()
    panel.set_root(tmp_path)
    album_a_item = _find_top_level(panel, "AlbumA")

    panel.expandItem(album_a_item)
    panel.expandItem(album_a_item)

    assert album_a_item.childCount() == 1


def test_selecting_a_track_emits_track_selected(qapp, tmp_path):
    _make_library(tmp_path)
    panel = LibraryPanel()
    panel.set_root(tmp_path)
    album_a_item = _find_top_level(panel, "AlbumA")
    panel.expandItem(album_a_item)
    track_item = album_a_item.child(0)

    received = []
    panel.track_selected.connect(received.append)

    track_item.setSelected(True)

    assert received == [tmp_path / "AlbumA" / "01 - Track One.wav"]


def test_selecting_a_folder_emits_folder_selected_before_expansion(qapp, tmp_path):
    _make_library(tmp_path)
    panel = LibraryPanel()
    panel.set_root(tmp_path)

    received = []
    panel.folder_selected.connect(received.append)

    panel.topLevelItem(0).setSelected(True)

    assert len(received) == 1
    assert received[0] in (tmp_path / "AlbumA", tmp_path / "AlbumB")


def test_set_root_on_unreadable_folder_emits_load_failed(qapp, tmp_path):
    # Un fichier (pas un dossier) fait échouer iterdir() avec OSError, quels
    # que soient les droits de l'utilisateur (y compris root) : cible fiable
    # pour simuler un dossier NAS devenu inaccessible.
    not_a_folder = tmp_path / "not_a_folder"
    not_a_folder.write_bytes(b"")
    panel = LibraryPanel()

    received = []
    panel.load_failed.connect(lambda folder, message: received.append((folder, message)))

    panel.set_root(not_a_folder)

    assert len(received) == 1
    assert received[0][0] == not_a_folder


def test_a_broken_symlink_does_not_break_the_rest_of_the_listing(qapp, tmp_path):
    album = tmp_path / "AlbumC"
    album.mkdir()
    (album / "01 - Good.wav").write_bytes(b"")
    (album / "broken_link.wav").symlink_to(album / "does_not_exist.wav")

    panel = LibraryPanel()
    panel.set_root(tmp_path)
    album_item = _find_top_level(panel, "AlbumC")

    panel.expandItem(album_item)

    names = [album_item.child(i).text(0) for i in range(album_item.childCount())]
    assert names == ["01 - Good.wav"]
