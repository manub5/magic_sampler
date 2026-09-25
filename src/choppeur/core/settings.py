from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

import tomli_w
from platformdirs import user_cache_dir, user_config_dir

APP_NAME = "choppeur"
_DEFAULT_LOOP_LENGTHS_BARS = (1, 2, 4, 8)


@dataclass
class Settings:
    library_root: str | None = None
    export_dir: str | None = None
    export_format: str = "wav"  # "wav" (24 bits, défaut) ou "flac"
    loop_lengths_bars: tuple[int, ...] = _DEFAULT_LOOP_LENGTHS_BARS
    candidates_per_track: int = 8
    max_one_shot_seconds: float = 2.0
    gpu_mode: str = "auto"  # "auto" ou "cpu"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["loop_lengths_bars"] = list(self.loop_lengths_bars)
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> Settings:
        merged = {**cls().to_dict(), **data}
        merged["loop_lengths_bars"] = tuple(merged["loop_lengths_bars"])
        return cls(**merged)


def default_settings_path() -> Path:
    return Path(user_config_dir(APP_NAME)) / "settings.toml"


def default_cache_path() -> Path:
    return Path(user_cache_dir(APP_NAME)) / "analyses.sqlite"


def load_settings(path: Path | None = None) -> Settings:
    path = path or default_settings_path()
    if not path.exists():
        return Settings()
    with path.open("rb") as f:
        data = tomllib.load(f)
    return Settings.from_dict(data)


def save_settings(settings: Settings, path: Path | None = None) -> None:
    path = path or default_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        tomli_w.dump(settings.to_dict(), f)
