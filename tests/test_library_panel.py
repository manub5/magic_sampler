from pathlib import Path

from choppeur.gui.library_panel import LibraryPanel


def _make_library(root: Path) -> None:
    album_a = root / "AlbumA"
    album_a.mkdir()
    (album_a / "01 - Track One.wav").write_bytes(b"")
    (album_a / "cover.jpg").write_bytes(b"")  # ignoré : pas un fichier audio

    album_b = root / "AlbumB"
    album_b.mkdir()
    (album_b / "01 - Other.mp3").write_bytes(b"")


def test_set_root_lists_folders_and_audio_files_only(qapp, tmp_path):
    _make_library(tmp_path)
    panel = LibraryPanel()

    panel.set_root(tmp_path)

    assert panel.topLevelItemCount() == 2
    names = sorted(panel.topLevelItem(i).text(0) for i in range(panel.topLevelItemCount()))
    assert names == ["AlbumA", "AlbumB"]

    album_a_item = next(
        panel.topLevelItem(i)
        for i in range(panel.topLevelItemCount())
        if panel.topLevelItem(i).text(0) == "AlbumA"
    )
    child_names = sorted(
        album_a_item.child(i).text(0) for i in range(album_a_item.childCount())
    )
    assert child_names == ["01 - Track One.wav"]


def test_selecting_a_track_emits_track_selected(qapp, tmp_path):
    _make_library(tmp_path)
    panel = LibraryPanel()
    panel.set_root(tmp_path)

    album_a_item = next(
        panel.topLevelItem(i)
        for i in range(panel.topLevelItemCount())
        if panel.topLevelItem(i).text(0) == "AlbumA"
    )
    track_item = album_a_item.child(0)

    received = []
    panel.track_selected.connect(received.append)

    track_item.setSelected(True)

    assert received == [tmp_path / "AlbumA" / "01 - Track One.wav"]


def test_selecting_a_folder_emits_folder_selected(qapp, tmp_path):
    _make_library(tmp_path)
    panel = LibraryPanel()
    panel.set_root(tmp_path)

    received = []
    panel.folder_selected.connect(received.append)

    panel.topLevelItem(0).setSelected(True)

    assert len(received) == 1
    assert received[0] in (tmp_path / "AlbumA", tmp_path / "AlbumB")
