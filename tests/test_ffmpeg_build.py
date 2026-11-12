"""
Verification tests for lightweight audio-only FFmpeg/FFprobe builds
against all real invocations used in SP Audiobook Player.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest


FFMPEG_RELEASE_DIR = Path(r"C:\Users\user\Desktop\python\SPAudioFFmpeg\release")
FFMPEG_EXE = FFMPEG_RELEASE_DIR / "ffmpeg.exe"
FFPROBE_EXE = FFMPEG_RELEASE_DIR / "ffprobe.exe"

pytestmark = pytest.mark.skipif(
    not (FFMPEG_EXE.exists() and FFPROBE_EXE.exists()),
    reason=f"Lightweight FFmpeg build not found in {FFMPEG_RELEASE_DIR}",
)


def _clean_windows_env() -> dict:
    """Return an environment without MSYS2/custom PATH to verify zero external DLL dependencies."""
    sys_root = os.environ.get("SystemRoot", r"C:\Windows")
    return {
        "SystemRoot": sys_root,
        "WINDIR": sys_root,
        "PATH": "",
        "TEMP": os.environ.get("TEMP", ""),
        "TMP": os.environ.get("TMP", ""),
    }


def _run(cmd, timeout=15, clean_env=True):
    env = _clean_windows_env() if clean_env else None
    return subprocess.run(
        [str(c) for c in cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )


@pytest.fixture(scope="module")
def sample_audio_files(tmp_path_factory):
    """Generate synthetic stereo WAV and chaptered MKA/OGG files using the tested ffmpeg.exe."""
    tmp = tmp_path_factory.mktemp("ffmpeg_samples")

    # 1. Stereo 1-second 440Hz WAV via lavfi or raw PCM?
    # Note: lavfi may be disabled in --disable-everything builds, so generate a valid PCM WAV in Python!
    import math
    import struct
    import wave

    wav_path = tmp / "sample_stereo.wav"
    sample_rate = 48000
    duration_sec = 1.0
    n_frames = int(sample_rate * duration_sec)
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_frames):
            val = int(16000 * math.sin(2 * math.pi * 440.0 * i / sample_rate))
            frames.extend(struct.pack("<hh", val, val))
        wf.writeframes(bytes(frames))

    # 2. Convert WAV -> OGG/Opus (used to test ffprobe & transmux fallback)
    opus_path = tmp / "sample.opus"
    res = _run([
        FFMPEG_EXE, "-y", "-v", "error",
        "-i", wav_path,
        "-c:a", "libopus", "-b:a", "48k",
        opus_path,
    ])
    assert res.returncode == 0, f"Failed to create sample opus: {res.stderr}"

    return {
        "tmp": tmp,
        "wav": wav_path,
        "opus": opus_path,
    }


def test_standalone_without_msys_in_path():
    """Both executables must start with empty PATH (no hidden MSYS2 DLL dependencies)."""
    for exe in (FFMPEG_EXE, FFPROBE_EXE):
        res = _run([exe, "-version"], clean_env=True)
        assert res.returncode == 0, f"{exe.name} failed with empty PATH: {res.stderr}"


def test_opus_converter_check_ffmpeg():
    """Exact check from opus_converter.py:_check_ffmpeg()."""
    res = _run([FFMPEG_EXE, "-codecs"])
    assert res.returncode == 0
    assert "libopus" in res.stdout


def test_required_decoders_and_demuxers_present():
    """Verify decoders and demuxers for all formats supported by the player and converter."""
    dec_res = _run([FFMPEG_EXE, "-decoders"])
    assert dec_res.returncode == 0
    for decoder in ("mp3", "aac", "flac", "alac", "vorbis", "opus", "libopus", "wmav2", "ape", "pcm_s16le", "mjpeg", "png"):
        assert decoder in dec_res.stdout, f"Missing decoder: {decoder}"

    demux_res = _run([FFMPEG_EXE, "-demuxers"])
    assert demux_res.returncode == 0
    for demuxer in ("mp3", "mov", "ogg", "flac", "matroska", "asf", "wav", "ape", "aac"):
        assert demuxer in demux_res.stdout, f"Missing demuxer: {demuxer}"


def test_scanner_ffprobe_chapters(sample_audio_files):
    """Exact command from scanner.py:_extract_chapters()."""
    cmd = [
        FFPROBE_EXE,
        "-v", "error",
        "-show_chapters",
        "-of", "json",
        sample_audio_files["opus"],
    ]
    res = _run(cmd)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert "chapters" in data
    assert isinstance(data["chapters"], list)


def test_scanner_ffprobe_file_analysis(sample_audio_files):
    """Exact command from scanner.py:_analyze_file_with_ffprobe()."""
    cmd = [
        FFPROBE_EXE,
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name:format=duration,bit_rate",
        "-of", "json",
        sample_audio_files["opus"],
    ]
    res = _run(cmd)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["streams"][0]["codec_name"] == "opus"
    assert float(data["format"]["duration"]) > 0.5


def test_opus_converter_ffprobe_queries(sample_audio_files):
    """Exact commands from opus_converter.py (_get_audio_duration, _get_audio_channels, _get_audio_bitrate)."""
    wav = sample_audio_files["wav"]

    res_dur = _run([FFPROBE_EXE, "-v", "error", "-show_entries", "format=duration", "-of", "json", wav])
    assert res_dur.returncode == 0
    assert float(json.loads(res_dur.stdout)["format"]["duration"]) == pytest.approx(1.0, abs=0.05)

    res_ch = _run([FFPROBE_EXE, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels", "-of", "json", wav])
    assert res_ch.returncode == 0
    assert int(json.loads(res_ch.stdout)["streams"][0]["channels"]) == 2

    res_br = _run([FFPROBE_EXE, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=bit_rate", "-of", "json", wav])
    assert res_br.returncode == 0
    assert int(json.loads(res_br.stdout)["streams"][0]["bit_rate"]) > 0


def test_opus_converter_downmix_and_stereo_encode(sample_audio_files, tmp_path):
    """Exact conversion commands from opus_converter.py:_convert_file() (downmix pan & stereo)."""
    wav = sample_audio_files["wav"]

    # 1. Downmix to mono using pan filter
    out_mono = tmp_path / "converted_mono.opus"
    cmd_mono = [
        FFMPEG_EXE, "-y", "-v", "error",
        "-i", wav,
        "-map", "0:a",
        "-map_metadata", "0",
        "-af", "pan=mono|c0=0.5*c0+0.5*c1",
        "-c:a", "libopus",
        "-b:a", "48k",
        "-vbr", "on",
        "-compression_level", "10",
        "-application", "audio",
        out_mono,
    ]
    res_mono = _run(cmd_mono)
    assert res_mono.returncode == 0, f"Downmix encode failed: {res_mono.stderr}"
    assert out_mono.exists() and out_mono.stat().st_size > 0

    ch_check = _run([FFPROBE_EXE, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels", "-of", "json", out_mono])
    assert json.loads(ch_check.stdout)["streams"][0]["channels"] == 1

    # 2. Keep stereo
    out_stereo = tmp_path / "converted_stereo.opus"
    cmd_stereo = [
        FFMPEG_EXE, "-y", "-v", "error",
        "-i", wav,
        "-map", "0:a",
        "-map_metadata", "0",
        "-c:a", "libopus",
        "-b:a", "64k",
        "-vbr", "on",
        "-compression_level", "10",
        "-application", "audio",
        out_stereo,
    ]
    res_stereo = _run(cmd_stereo)
    assert res_stereo.returncode == 0, f"Stereo encode failed: {res_stereo.stderr}"
    assert out_stereo.exists() and out_stereo.stat().st_size > 0


def test_bass_player_transmux_fallback(sample_audio_files, tmp_path):
    """Exact fallback transmux command from bass_player.py:load()."""
    out_opus = tmp_path / "transmuxed.opus"
    cmd = [
        FFMPEG_EXE,
        "-y",
        "-v", "error",
        "-i", sample_audio_files["opus"],
        "-c:a", "copy",
        out_opus,
    ]
    res = _run(cmd)
    assert res.returncode == 0, f"Transmux failed: {res.stderr}"
    assert out_opus.exists() and out_opus.stat().st_size > 0
