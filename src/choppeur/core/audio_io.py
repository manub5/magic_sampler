from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from choppeur.core.models import Candidate, Track
from choppeur.core.naming import build_filename, unique_path

_NATIVE_EXTENSIONS = {".wav", ".flac", ".ogg", ".aiff", ".aif"}


class AudioLoadError(RuntimeError):
    pass


def load(path: Path, *, mono: bool = True) -> tuple[np.ndarray, int]:
    """Charge un fichier audio en lecture seule (jamais de modification de la source)."""
    if path.suffix.lower() in _NATIVE_EXTENSIONS:
        samples, sample_rate = sf.read(str(path), always_2d=False, dtype="float32")
    else:
        samples, sample_rate = _load_via_ffmpeg(path)

    if mono and samples.ndim > 1:
        samples = samples.mean(axis=1)

    return samples, sample_rate


def _load_via_ffmpeg(path: Path) -> tuple[np.ndarray, int]:
    if shutil.which("ffmpeg") is None:
        raise AudioLoadError(
            f"ffmpeg est requis pour lire {path.suffix} mais n'est pas installé."
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        wav_path = Path(tmp_dir) / "decoded.wav"
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(path), str(wav_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AudioLoadError(f"Échec du décodage de {path} : {result.stderr.strip()}")
        return sf.read(str(wav_path), always_2d=False, dtype="float32")


def export_segment(
    samples: np.ndarray,
    sample_rate: int,
    start_seconds: float,
    end_seconds: float,
    destination: Path,
    *,
    subtype: str = "PCM_24",
) -> None:
    start_index = max(0, round(start_seconds * sample_rate))
    end_index = min(len(samples), round(end_seconds * sample_rate))
    segment = samples[start_index:end_index]
    destination.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(destination), segment, sample_rate, subtype=subtype)


def export_candidates(
    samples: np.ndarray,
    sample_rate: int,
    track: Track,
    candidates: list[Candidate],
    destination: Path,
    *,
    file_format: str = "wav",
    subtype: str = "PCM_24",
) -> list[Path]:
    """Exporte chaque candidat sous un nom automatique, sans jamais écraser un fichier existant."""
    exported_paths = []
    for candidate in candidates:
        filename = build_filename(track, candidate, extension=file_format)
        path = unique_path(destination, filename)
        export_segment(
            samples, sample_rate, candidate.start_seconds, candidate.end_seconds, path, subtype=subtype
        )
        exported_paths.append(path)
    return exported_paths
