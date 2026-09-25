from choppeur.core.settings import (
    Settings,
    default_cache_path,
    default_settings_path,
    load_settings,
    save_settings,
)


def test_defaults():
    settings = Settings()
    assert settings.export_format == "wav"
    assert settings.loop_lengths_bars == (1, 2, 4, 8)
    assert settings.gpu_mode == "auto"


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "settings.toml"
    original = Settings(
        library_root="/musique",
        export_dir="/musique/export",
        export_format="flac",
        loop_lengths_bars=(2, 4),
        candidates_per_track=5,
        max_one_shot_seconds=1.5,
        gpu_mode="cpu",
    )

    save_settings(original, path)
    loaded = load_settings(path)

    assert loaded == original


def test_load_missing_file_returns_defaults(tmp_path):
    loaded = load_settings(tmp_path / "does_not_exist.toml")
    assert loaded == Settings()


def test_default_paths_point_to_choppeur_directories():
    assert default_settings_path().name == "settings.toml"
    assert default_cache_path().name == "analyses.sqlite"
    assert "choppeur" in str(default_settings_path())
    assert "choppeur" in str(default_cache_path())


def test_load_partial_file_fills_in_defaults(tmp_path):
    path = tmp_path / "settings.toml"
    path.write_text('export_format = "flac"\n')

    loaded = load_settings(path)

    assert loaded.export_format == "flac"
    assert loaded.candidates_per_track == Settings().candidates_per_track
