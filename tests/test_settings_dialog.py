from choppeur.core.settings import Settings
from choppeur.gui.settings_dialog import SettingsDialog


def test_dialog_reflects_initial_settings(qapp):
    settings = Settings(export_format="flac", candidates_per_track=3, gpu_mode="cpu")
    dialog = SettingsDialog(settings)

    assert dialog._export_format.currentText() == "flac"
    assert dialog._candidates_per_track.value() == 3
    assert dialog._gpu_mode.currentText() == "cpu"


def test_settings_reads_back_edited_values(qapp):
    dialog = SettingsDialog(Settings())

    dialog._library_root.setText("/musique")
    dialog._export_dir.setText("/musique/export")
    dialog._export_format.setCurrentText("flac")
    dialog._loop_lengths_bars.setText("2,4")
    dialog._candidates_per_track.setValue(10)
    dialog._max_one_shot_seconds.setValue(3.5)
    dialog._gpu_mode.setCurrentText("cpu")

    result = dialog.settings()

    assert result == Settings(
        library_root="/musique",
        export_dir="/musique/export",
        export_format="flac",
        loop_lengths_bars=(2, 4),
        candidates_per_track=10,
        max_one_shot_seconds=3.5,
        gpu_mode="cpu",
    )
