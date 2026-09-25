import hashlib
import shutil
import subprocess

import numpy as np
import pytest
import soundfile as sf

from choppeur.core import audio_io

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
