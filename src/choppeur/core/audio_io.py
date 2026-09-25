from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from mutagen import File as MutagenFile

from choppeur.core.models import Candidate, Track
from choppeur.core.naming import build_filename, unique_path

_NATIVE_EXTENSIONS = {".wav", ".flac", ".ogg", ".aiff", ".aif"}

# Extensions reconnues comme pistes audio dans la bibliothèque (lues nativement
# ou via ffmpeg, voir _load_via_ffmpeg).
AUDIO_EXTENSIONS = _NATIVE_EXTENSIONS | {".mp3", ".m4a", ".aac"}


class AudioLoadError(RuntimeError):
    pass


def _read_or_raise(readable_path: Path, *, context: str) -> tuple[np.ndarray, int]:
    """sf.read en traduisant toute erreur en AudioLoadError, pour que l'appelant
    ait toujours le même type d'erreur à afficher, quel que soit le format
    d'origine ou la raison (fichier vide, tronqué, corrompu... libsndfile lève
    sa propre exception, ex. LibsndfileError, selon le cas, jamais garanti)."""
    try:
        return sf.read(str(readable_path), always_2d=False, dtype="float32")
    except Exception as exc:
        raise AudioLoadError(f"Impossible de lire {context} : {exc}") from exc


def load(path: Path, *, mono: bool = True) -> tuple[np.ndarray, int]:
    """Charge un fichier audio en lecture seule (jamais de modification de la source)."""
    if path.suffix.lower() in _NATIVE_EXTENSIONS:
        samples, sample_rate = _read_or_raise(path, context=str(path))
    else:
        samples, sample_rate = _load_via_ffmpeg(path)

    if mono and samples.ndim > 1:
        samples = samples.mean(axis=1)

    return samples, sample_rate


def _load_via_ffmpeg(path: Path) -> tuple[np.ndarray, int]:
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise AudioLoadError(f"ffmpeg est requis pour lire {path.suffix} mais n'est pas installé.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        wav_path = Path(tmp_dir) / "decoded.wav"
        # nosec B603 : chemin ffmpeg résolu (pas de recherche PATH partielle),
        # arguments passés en liste (pas de shell=True) : pas d'injection possible.
        result = subprocess.run(  # nosec B603
            [ffmpeg_path, "-v", "error", "-y", "-i", str(path), str(wav_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise AudioLoadError(f"Échec du décodage de {path} : {result.stderr.strip()}")
        return _read_or_raise(wav_path, context=f"{path} après décodage")


def read_track(path: Path) -> Track:
    """Lit les tags (artiste, album, titre, piste) et les métadonnées audio, sans jamais
    modifier le fichier source.

    Un fichier vide, tronqué ou corrompu ne doit jamais faire planter la
    lecture de toute une bibliothèque ou d'un album entier à cause d'une
    seule piste illisible : mutagen peut lever ses propres exceptions
    (ex. EmptyChunk) au lieu de renvoyer None dans ce cas, donc on les
    traite comme "pas de tags" plutôt que de les laisser remonter.
    """
    try:
        tags = MutagenFile(str(path), easy=True)
    except Exception:  # noqa: BLE001 - fichier illisible : on retombe sur les valeurs par défaut
        tags = None
    audio_info = tags.info if tags is not None else None

    def _tag(key: str) -> str | None:
        if tags is None:
            return None
        values = tags.get(key)
        return values[0] if values else None

    track_number = None
    raw_track_number = _tag("tracknumber")
    if raw_track_number:
        try:
            track_number = int(str(raw_track_number).split("/")[0])
        except ValueError:
            track_number = None

    return Track(
        path=path,
        artist=_tag("artist") or "Inconnu",
        album=_tag("album") or "Inconnu",
        title=_tag("title") or path.stem,
        track_number=track_number,
        duration_seconds=float(audio_info.length) if audio_info is not None else 0.0,
        sample_rate=int(getattr(audio_info, "sample_rate", 0) or 0) if audio_info is not None else 0,
    )


def export_segment(
    samples: np.ndarray,
    sample_rate: int,
    start_seconds: float,
    end_seconds: float,
    destination: Path,
    *,
    subtype: str = "PCM_24",
) -> None:
    """Écrit le segment vers `destination`.

    Réserve d'abord le nom de fichier de façon atomique (O_EXCL) : si un autre
    export (un deuxième export lancé en même temps, par exemple) a déjà créé
    ce fichier entre-temps, lève `FileExistsError` plutôt que d'écraser
    silencieusement son contenu. `export_candidates` s'appuie là-dessus pour
    choisir un autre nom en cas de collision.
    """
    start_index = max(0, round(start_seconds * sample_rate))
    end_index = min(len(samples), round(end_seconds * sample_rate))
    segment = samples[start_index:end_index]
    destination.parent.mkdir(parents=True, exist_ok=True)

    fd = os.open(str(destination), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    os.close(fd)
    try:
        sf.write(str(destination), segment, sample_rate, subtype=subtype)
    except Exception:
        # Écrire a échoué pour une raison qui n'est pas une collision de nom
        # (ex. disque plein) : on libère le nom réservé au lieu de le laisser
        # définitivement "brûlé" par un fichier de 0 octet, pour qu'une
        # nouvelle tentative réutilise le même nom plutôt que de sauter à
        # "_2", "_3", ... indéfiniment.
        destination.unlink(missing_ok=True)
        raise


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
    """Exporte chaque candidat sous un nom automatique, sans jamais écraser un fichier existant
    (y compris si deux exports tournent en même temps sur le même dossier)."""
    exported_paths = []
    for candidate in candidates:
        filename = build_filename(track, candidate, extension=file_format)
        while True:
            path = unique_path(destination, filename)
            try:
                export_segment(
                    samples,
                    sample_rate,
                    candidate.start_seconds,
                    candidate.end_seconds,
                    path,
                    subtype=subtype,
                )
            except FileExistsError:
                continue  # un autre export a pris ce nom entre-temps : on retente avec le suivant
            break
        exported_paths.append(path)
    return exported_paths
