from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class CandidateType(Enum):
    LOOP = "loop"
    ONE_SHOT = "shot"


@dataclass(frozen=True)
class Track:
    path: Path
    artist: str
    album: str
    title: str
    track_number: int | None
    duration_seconds: float
    sample_rate: int


@dataclass(frozen=True)
class Analysis:
    track: Track
    tempo_bpm: float
    beat_times: tuple[float, ...]
    downbeat_times: tuple[float, ...]
    onset_times: tuple[float, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Candidate:
    type: CandidateType
    start_seconds: float
    end_seconds: float
    score: float
    bpm: float | None = None
    bars: int | None = None

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds
