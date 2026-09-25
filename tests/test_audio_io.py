import hashlib
import shutil
import subprocess

import numpy as np
import pytest
import soundfile as sf

from choppeur.core import audio_io
from choppeur.core.models import Candidate, CandidateType, Track

SAMPLE_RATE = 44100


def _write_sine(path, duration_seconds=1.0, frequency=440.0, sample_rate=SAMPLE_RATE):
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), endpoint=False)
    samples = 0.5 * np.sin(2 * np.pi * frequency * t).astype(np.float32)
    sf.write(str(path), samples, sample_rate, subtype="PCM_24")
    return samples


def test_load_wav_returns_samples_and_sample_rate(tmp_path):
    wav_path = tmp_path / "tone.wav"
    expected = _write_sine(wav_path)

    samples, sample_rate = audio_io.load(wav_path)

    assert sample_rate == SAMPLE_RATE
    assert len(samples) == len(expected)


def test_load_never_modifies_the_source_file(tmp_path):
    wav_path = tmp_path / "tone.wav"
    _write_sine(wav_path)
    before = hashlib.sha256(wav_path.read_bytes()).hexdigest()

    audio_io.load(wav_path)

    after = hashlib.sha256(wav_path.read_bytes()).hexdigest()
    assert before == after


def test_export_segment_writes_expected_duration(tmp_path):
    samples = np.zeros(SAMPLE_RATE * 2, dtype=np.float32)
    destination = tmp_path / "out" / "segment.wav"

    audio_io.export_segment(samples, SAMPLE_RATE, 0.5, 1.5, destination)

    written, sample_rate = sf.read(str(destination))
    assert sample_rate == SAMPLE_RATE
    assert len(written) == SAMPLE_RATE  # 1 seconde


def test_export_candidates_writes_named_files_without_overwrite(tmp_path):
    samples = np.zeros(SAMPLE_RATE * 3, dtype=np.float32)
    track = Track(
        path=tmp_path / "source.wav",
        artist="Burial",
        album="Untrue",
        title="Etched Headplate",
        track_number=3,
        duration_seconds=3.0,
        sample_rate=SAMPLE_RATE,
    )
    loop = Candidate(
        type=CandidateType.LOOP, start_seconds=0.0, end_seconds=1.0, score=1.0, bpm=120, bars=1
    )
    shot = Candidate(type=CandidateType.ONE_SHOT, start_seconds=1.0, end_seconds=1.2, score=0.5)
    destination = tmp_path / "export"

    paths = audio_io.export_candidates(samples, SAMPLE_RATE, track, [loop, shot], destination)

    assert len(paths) == 2
    assert all(p.exists() for p in paths)
    assert paths[0].name == "Burial_Untrue_03_loop_120bpm_1bars_00m00s.wav"
    assert paths[1].name == "Burial_Untrue_03_shot_00m01s000.wav"

    # Un second export ne doit jamais écraser les fichiers déjà exportés
    more_paths = audio_io.export_candidates(samples, SAMPLE_RATE, track, [loop], destination)
    assert more_paths[0].name == "Burial_Untrue_03_loop_120bpm_1bars_00m00s_2.wav"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg non installé")
def test_load_decodes_mp3_via_ffmpeg(tmp_path):
    wav_path = tmp_path / "tone.wav"
    _write_sine(wav_path, duration_seconds=0.5)
    mp3_path = tmp_path / "tone.mp3"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(wav_path), str(mp3_path)],
        check=True,
    )

    samples, sample_rate = audio_io.load(mp3_path)

    assert sample_rate > 0
    assert len(samples) > 0
