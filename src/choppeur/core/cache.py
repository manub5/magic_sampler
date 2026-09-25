from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from choppeur.core.models import Analysis, Track

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    path TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime REAL NOT NULL,
    tempo_bpm REAL NOT NULL,
    beat_times TEXT NOT NULL,
    downbeat_times TEXT NOT NULL,
    onset_times TEXT NOT NULL,
    PRIMARY KEY (path, size, mtime)
)
"""


def _fingerprint(path: Path) -> tuple[int, float]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime


class AnalysisCache:
    """
    Cache SQLite des analyses (clé = chemin + taille + date de modification),
    pour ne jamais réanalyser un fichier inchangé.
    """

    def __init__(self, database_path: Path):
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(database_path)
        self._connection.execute(_SCHEMA)
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "AnalysisCache":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def get(self, track: Track) -> Analysis | None:
        size, mtime = _fingerprint(track.path)
        row = self._connection.execute(
            "SELECT tempo_bpm, beat_times, downbeat_times, onset_times "
            "FROM analyses WHERE path = ? AND size = ? AND mtime = ?",
            (str(track.path), size, mtime),
        ).fetchone()
        if row is None:
            return None
        tempo_bpm, beat_times_json, downbeat_times_json, onset_times_json = row
        return Analysis(
            track=track,
            tempo_bpm=tempo_bpm,
            beat_times=tuple(json.loads(beat_times_json)),
            downbeat_times=tuple(json.loads(downbeat_times_json)),
            onset_times=tuple(json.loads(onset_times_json)),
        )

    def set(self, analysis: Analysis) -> None:
        size, mtime = _fingerprint(analysis.track.path)
        self._connection.execute(
            "INSERT OR REPLACE INTO analyses "
            "(path, size, mtime, tempo_bpm, beat_times, downbeat_times, onset_times) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(analysis.track.path),
                size,
                mtime,
                analysis.tempo_bpm,
                json.dumps(analysis.beat_times),
                json.dumps(analysis.downbeat_times),
                json.dumps(analysis.onset_times),
            ),
        )
        self._connection.commit()
