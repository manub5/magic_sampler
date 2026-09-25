from __future__ import annotations

import re
from pathlib import Path

from choppeur.core.models import Candidate, CandidateType, Track

_FORBIDDEN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize(value: str) -> str:
    cleaned = _FORBIDDEN_CHARS.sub("_", value).strip()
    return cleaned or "sans_nom"


def _format_position(seconds: float, *, with_millis: bool) -> str:
    total_ms = round(seconds * 1000)
    minutes, rest_ms = divmod(total_ms, 60_000)
    secs, millis = divmod(rest_ms, 1000)
    if with_millis:
        return f"{minutes:02d}m{secs:02d}s{millis:03d}"
    return f"{minutes:02d}m{secs:02d}s"


def _track_label(track: Track) -> str:
    if track.track_number is not None:
        return f"{track.track_number:02d}"
    return _sanitize(track.title)


def build_filename(track: Track, candidate: Candidate, *, extension: str = "wav") -> str:
    artist = _sanitize(track.artist)
    album = _sanitize(track.album)
    piste = _track_label(track)

    if candidate.type is CandidateType.LOOP:
        position = _format_position(candidate.start_seconds, with_millis=False)
        bpm = round(candidate.bpm or 0)
        return f"{artist}_{album}_{piste}_loop_{bpm}bpm_{candidate.bars}bars_{position}.{extension}"

    position = _format_position(candidate.start_seconds, with_millis=True)
    return f"{artist}_{album}_{piste}_shot_{position}.{extension}"


def unique_path(directory: Path, filename: str) -> Path:
    candidate_path = directory / filename
    if not candidate_path.exists():
        return candidate_path

    stem, suffix = candidate_path.stem, candidate_path.suffix
    n = 2
    while True:
        alt = directory / f"{stem}_{n}{suffix}"
        if not alt.exists():
            return alt
        n += 1
