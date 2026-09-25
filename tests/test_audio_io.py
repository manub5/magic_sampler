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


def test_load_empty_file_raises_audio_load_error(tmp_path):
    empty_path = tmp_path / "empty.wav"
    empty_path.write_bytes(b"")

    with pytest.raises(audio_io.AudioLoadError):
        audio_io.load(empty_path)


def test_load_truncated_wav_degrades_gracefully_instead_of_crashing(tmp_path):
    """
    libsndfile est tolérant sur un WAV tronqué : il renvoie ce qu'il a pu lire
    plutôt que de lever une exception. On vérifie juste que load() ne plante
    pas et ne renvoie jamais plus de données que ce qui existe vraiment dans
    le fichier tronqué (pas de données inventées).
    """
    wav_path = tmp_path / "tone.wav"
    original = _write_sine(wav_path)
    truncated = wav_path.read_bytes()[: wav_path.stat().st_size // 2]
    corrupted_path = tmp_path / "corrupted.wav"
    corrupted_path.write_bytes(truncated)

    samples, sample_rate = audio_io.load(corrupted_path)

    assert sample_rate == SAMPLE_RATE
    assert 0 < len(samples) < len(original)


def test_load_garbage_file_with_audio_extension_raises_audio_load_error(tmp_path):
    """Un fichier qui n'est pas du tout de l'audio (mais porte une extension
    audio) doit remonter une AudioLoadError propre, jamais une exception
    brute de libsndfile qui remonterait telle quelle jusqu'à l'interface."""
    fake_path = tmp_path / "not_actually_audio.wav"
    fake_path.write_bytes(b"ceci n'est pas un fichier audio" * 100)

    with pytest.raises(audio_io.AudioLoadError):
        audio_io.load(fake_path)


def test_load_silent_file_returns_zeros_without_crashing(tmp_path):
    wav_path = tmp_path / "silence.wav"
    sf.write(str(wav_path), np.zeros(SAMPLE_RATE, dtype=np.float32), SAMPLE_RATE, subtype="PCM_24")

    samples, sample_rate = audio_io.load(wav_path)

    assert sample_rate == SAMPLE_RATE
    assert len(samples) == SAMPLE_RATE
    assert np.all(samples == 0)


def test_load_stereo_file_downmixes_to_mono_by_default(tmp_path):
    wav_path = tmp_path / "stereo.wav"
    left = np.full(SAMPLE_RATE, 0.5, dtype=np.float32)
    right = np.full(SAMPLE_RATE, -0.5, dtype=np.float32)
    stereo = np.stack([left, right], axis=1)
    sf.write(str(wav_path), stereo, SAMPLE_RATE, subtype="PCM_24")

    samples, _sample_rate = audio_io.load(wav_path)

    assert samples.ndim == 1
    assert np.allclose(samples, 0.0, atol=1e-3)  # moyenne de +0.5 et -0.5


def test_load_stereo_file_keeps_channels_when_mono_false(tmp_path):
    wav_path = tmp_path / "stereo.wav"
    stereo = np.zeros((SAMPLE_RATE, 2), dtype=np.float32)
    sf.write(str(wav_path), stereo, SAMPLE_RATE, subtype="PCM_24")

    samples, _ = audio_io.load(wav_path, mono=False)

    assert samples.ndim == 2
    assert samples.shape[1] == 2


def test_export_segment_writes_expected_duration(tmp_path):
    samples = np.zeros(SAMPLE_RATE * 2, dtype=np.float32)
    destination = tmp_path / "out" / "segment.wav"

    audio_io.export_segment(samples, SAMPLE_RATE, 0.5, 1.5, destination)

    written, sample_rate = sf.read(str(destination))
    assert sample_rate == SAMPLE_RATE
    assert len(written) == SAMPLE_RATE  # 1 seconde


def test_read_track_extracts_tags_and_audio_info(tmp_path):
    from mutagen.flac import FLAC

    path = tmp_path / "03 - Etched Headplate.flac"
    sf.write(str(path), np.zeros(SAMPLE_RATE, dtype="float32"), SAMPLE_RATE, subtype="PCM_16")
    tags = FLAC(str(path))
    tags["artist"] = "Burial"
    tags["album"] = "Untrue"
    tags["title"] = "Etched Headplate"
    tags["tracknumber"] = "3"
    tags.save()

    track = audio_io.read_track(path)

    assert track.artist == "Burial"
    assert track.album == "Untrue"
    assert track.title == "Etched Headplate"
    assert track.track_number == 3
    assert track.sample_rate == SAMPLE_RATE
    assert track.duration_seconds == pytest.approx(1.0, rel=1e-2)


def test_read_track_falls_back_to_filename_without_tags(tmp_path):
    path = tmp_path / "untagged.wav"
    _write_sine(path, duration_seconds=0.5)

    track = audio_io.read_track(path)

    assert track.artist == "Inconnu"
    assert track.album == "Inconnu"
    assert track.title == "untagged"
    assert track.track_number is None


def test_read_track_on_empty_file_falls_back_instead_of_crashing(tmp_path):
    """
    mutagen lève sa propre exception (EmptyChunk) sur un fichier .wav vide au
    lieu de renvoyer "pas de tags" comme sur un fichier juste non-tagué :
    sans ce correctif, une seule piste vide dans un dossier faisait planter
    la lecture de tout l'album (voir gui/workers.tracks_in_folder).
    """
    path = tmp_path / "empty.wav"
    path.write_bytes(b"")

    track = audio_io.read_track(path)

    assert track.artist == "Inconnu"
    assert track.title == "empty"
    assert track.duration_seconds == 0.0
    assert track.sample_rate == 0


def test_export_segment_never_overwrites_an_existing_file(tmp_path):
    samples = np.zeros(SAMPLE_RATE, dtype=np.float32)
    destination = tmp_path / "segment.wav"

    audio_io.export_segment(samples, SAMPLE_RATE, 0.0, 1.0, destination)

    with pytest.raises(FileExistsError):
        audio_io.export_segment(samples, SAMPLE_RATE, 0.0, 1.0, destination)


def test_export_segment_releases_the_name_if_writing_fails(monkeypatch, tmp_path):
    """
    Disque plein (ou toute autre panne d'écriture) pendant l'export : le nom
    réservé ne doit pas rester définitivement "brûlé" par un fichier de 0
    octet — une nouvelle tentative doit pouvoir réutiliser le même nom.
    """
    samples = np.zeros(SAMPLE_RATE, dtype=np.float32)
    destination = tmp_path / "segment.wav"

    real_write = sf.write
    calls = {"n": 0}

    def failing_once(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("No space left on device")
        return real_write(*args, **kwargs)

    monkeypatch.setattr(audio_io.sf, "write", failing_once)

    with pytest.raises(OSError, match="No space left on device"):
        audio_io.export_segment(samples, SAMPLE_RATE, 0.0, 1.0, destination)

    assert not destination.exists()  # le nom a bien été libéré, pas laissé "pris"

    audio_io.export_segment(samples, SAMPLE_RATE, 0.0, 1.0, destination)  # ne lève plus
    assert destination.exists()


def test_export_candidates_recovers_from_a_naming_race(monkeypatch, tmp_path):
    """
    Deux exports simultanés du même nom : si un autre export crée le fichier
    entre le calcul du nom et l'écriture (la vraie situation d'une course),
    export_candidates doit retenter avec le nom suivant plutôt que d'écraser
    ou de planter.
    """
    samples = np.zeros(SAMPLE_RATE, dtype=np.float32)
    track = Track(
        path=tmp_path / "source.wav",
        artist="Burial",
        album="Untrue",
        title="Etched Headplate",
        track_number=3,
        duration_seconds=1.0,
        sample_rate=SAMPLE_RATE,
    )
    candidate = Candidate(type=CandidateType.ONE_SHOT, start_seconds=0.0, end_seconds=0.5, score=1.0)
    destination = tmp_path / "export"
    destination.mkdir()

    real_unique_path = audio_io.unique_path
    call_count = {"n": 0}

    def racy_unique_path(directory, filename):
        call_count["n"] += 1
        path = real_unique_path(directory, filename)
        if call_count["n"] == 1:
            # Simule une autre exportation qui vient de créer ce fichier juste
            # après notre appel à unique_path() mais avant notre écriture.
            path.touch()
        return path

    monkeypatch.setattr(audio_io, "unique_path", racy_unique_path)

    paths = audio_io.export_candidates(samples, SAMPLE_RATE, track, [candidate], destination)

    assert call_count["n"] == 2  # 1er essai en collision, 2e réussi
    assert len(paths) == 1
    assert paths[0].exists()
    assert sf.read(str(paths[0]))[0].shape[0] == SAMPLE_RATE // 2  # vraies données, pas le fichier vide


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
    loop = Candidate(type=CandidateType.LOOP, start_seconds=0.0, end_seconds=1.0, score=1.0, bpm=120, bars=1)
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
