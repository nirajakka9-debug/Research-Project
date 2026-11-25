"""Audio conversion utilities for MindTrack Voice AI.

Converts non-WAV uploads (MP3, M4A, AAC, OGG, FLAC, WebM) to mono 16 kHz WAV
before passing to the Voice AI pipeline.

Strategy:
1. Try ffmpeg subprocess (fastest, highest quality).
2. Fall back to pydub (also needs ffmpeg under the hood but provides nicer error).
3. If neither works, raise AudioConversionError with clear instructions.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


class AudioConversionError(Exception):
    def __init__(self, message: str, status_code: int = 422):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


FFMPEG_AVAILABLE: bool | None = None  # cached after first check


def _check_ffmpeg() -> bool:
    global FFMPEG_AVAILABLE
    if FFMPEG_AVAILABLE is not None:
        return FFMPEG_AVAILABLE
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5,
        )
        FFMPEG_AVAILABLE = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        FFMPEG_AVAILABLE = False
    return FFMPEG_AVAILABLE


def convert_to_wav(
    input_path: Path,
    target_sr: int = 16000,
) -> Path:
    """Convert audio file to mono WAV at target_sr Hz.

    Returns path to a new temp WAV file.  Caller must delete it after use.
    Raises AudioConversionError on failure.
    """
    suffix = input_path.suffix.lower()
    if suffix == ".wav":
        # Already WAV — return a copy so caller owns a deletable path
        tmp = Path(tempfile.mktemp(suffix=".wav"))
        shutil.copy2(input_path, tmp)
        return tmp

    out_tmp = Path(tempfile.mktemp(suffix=".wav"))

    if _check_ffmpeg():
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-ac", "1",           # mono
            "-ar", str(target_sr),
            "-sample_fmt", "s16",
            "-f", "wav",
            str(out_tmp),
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=120,
                check=False,
            )
            if result.returncode != 0:
                stderr = result.stderr.decode(errors="replace")[:500]
                raise AudioConversionError(
                    f"FFmpeg conversion failed: {stderr}",
                    status_code=422,
                )
            if not out_tmp.is_file() or out_tmp.stat().st_size == 0:
                raise AudioConversionError("FFmpeg produced an empty output file.", status_code=422)
            return out_tmp
        except subprocess.TimeoutExpired:
            out_tmp.unlink(missing_ok=True)
            raise AudioConversionError("Audio conversion timed out (>120 s).", status_code=422)

    # FFmpeg not available — try pydub
    try:
        from pydub import AudioSegment  # type: ignore

        fmt_map = {
            ".mp3": "mp3",
            ".m4a": "mp4",
            ".aac": "aac",
            ".ogg": "ogg",
            ".flac": "flac",
            ".webm": "webm",
        }
        fmt = fmt_map.get(suffix)
        if fmt is None:
            raise AudioConversionError(
                f"Unsupported audio format '{suffix}'. "
                "Supported: WAV, MP3, M4A, AAC, OGG, FLAC, WebM.",
                status_code=415,
            )

        segment = AudioSegment.from_file(str(input_path), format=fmt)
        segment = segment.set_channels(1).set_frame_rate(target_sr).set_sample_width(2)
        segment.export(str(out_tmp), format="wav")
        return out_tmp

    except AudioConversionError:
        raise
    except Exception as exc:
        out_tmp.unlink(missing_ok=True)
        raise AudioConversionError(
            f"Audio conversion failed and FFmpeg is not available. "
            f"Please install FFmpeg (https://ffmpeg.org) for MP3/M4A/AAC/OGG/FLAC/WebM support. "
            f"You can upload WAV files directly without FFmpeg. "
            f"Error detail: {exc}",
            status_code=422,
        ) from exc


def ffmpeg_available() -> bool:
    return _check_ffmpeg()
