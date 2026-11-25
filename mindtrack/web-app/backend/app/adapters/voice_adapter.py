"""Safe subprocess adapter for the standalone Voice ai - Copy acoustic pipeline."""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import UploadFile

from ..config import (
    MAX_AUDIO_SIZE_BYTES,
    OUTPUTS_DIR,
    SUPPORTED_AUDIO_EXTENSIONS,
    UPLOAD_VOICE_DIR,
    VOICE_AI_DIR,
    VOICE_PROFILES_DIR,
    VOICE_SUBPROCESS_TIMEOUT_SEC,
    validate_safe_user_id,
)

VALID_VOICE_MODES = {"single", "calibrate", "assess"}
VOICE_RUNNER_PATH = Path(__file__).resolve().parent / "voice_runner.py"


class VoiceAnalysisError(Exception):
    """Structured error raised during voice audio validation or analysis."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


async def save_validated_audio_upload(upload: UploadFile) -> tuple[Path, str]:
    """Validates .wav extension & streaming size, storing to a generated UUID path."""
    original_name = Path(upload.filename or "recording.wav").name
    ext = Path(original_name).suffix.lower()
    if ext not in SUPPORTED_AUDIO_EXTENSIONS:
        raise VoiceAnalysisError(
            f"Unsupported audio format '{ext or 'unknown'}'. Voice AI natively supports WAV (.wav) recordings.",
            status_code=400,
        )

    safe_path = UPLOAD_VOICE_DIR / f"voice_{uuid.uuid4().hex}.wav"
    total_bytes = 0
    try:
        with open(safe_path, "wb") as out_file:
            while True:
                chunk = await upload.read(512 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_AUDIO_SIZE_BYTES:
                    raise VoiceAnalysisError(
                        f"Audio file exceeds maximum allowed size ({MAX_AUDIO_SIZE_BYTES // (1024 * 1024)} MB).",
                        status_code=413,
                    )
                out_file.write(chunk)
        if total_bytes == 0:
            raise VoiceAnalysisError("Uploaded audio file is empty (0 bytes).", status_code=400)
        return safe_path, original_name
    except Exception:
        safe_path.unlink(missing_ok=True)
        raise


def run_voice_analyzer(
    wav_path: Path,
    user_id: str,
    mode: str = "single",
    update_baseline: bool = False,
) -> Dict[str, Any]:
    """Executes the Voice ai - Copy pipeline safely via voice_runner.py subprocess."""
    if not (VOICE_AI_DIR / "inference" / "pipeline.py").is_file():
        raise VoiceAnalysisError(
            f"Voice AI module not found at '{VOICE_AI_DIR}'.",
            status_code=503,
        )

    try:
        clean_user_id = validate_safe_user_id(user_id)
    except ValueError as exc:
        raise VoiceAnalysisError(str(exc), status_code=400) from exc

    if mode not in VALID_VOICE_MODES:
        raise VoiceAnalysisError(
            f"Invalid voice operational mode '{mode}'. Choose from: {', '.join(sorted(VALID_VOICE_MODES))}.",
            status_code=400,
        )

    profile_path = VOICE_PROFILES_DIR / f"{clean_user_id}.json"
    output_json_path = OUTPUTS_DIR / f"voice_out_{uuid.uuid4().hex}.json"

    cmd = [
        sys.executable,
        str(VOICE_RUNNER_PATH),
        "--voice-ai-dir",
        str(VOICE_AI_DIR),
        "--wav",
        str(wav_path),
        "--user-id",
        clean_user_id,
        "--mode",
        mode,
        "--profile-path",
        str(profile_path),
        "--output",
        str(output_json_path),
    ]
    if update_baseline:
        cmd.append("--update-baseline")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(VOICE_AI_DIR),
            shell=False,
            capture_output=True,
            text=True,
            timeout=VOICE_SUBPROCESS_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output_json_path.unlink(missing_ok=True)
        raise VoiceAnalysisError(
            f"Voice analysis timed out after {VOICE_SUBPROCESS_TIMEOUT_SEC}s.",
            status_code=504,
        ) from exc
    except OSError as exc:
        output_json_path.unlink(missing_ok=True)
        raise VoiceAnalysisError(
            f"Failed to start Voice AI process: {exc}",
            status_code=500,
        ) from exc

    try:
        if proc.returncode != 0:
            err_msg = (proc.stderr or proc.stdout or "").strip() or f"Voice AI exited with code {proc.returncode}."
            status = 400 if proc.returncode in (1, 2) else 500
            raise VoiceAnalysisError(err_msg, status_code=status)

        if not output_json_path.is_file():
            raise VoiceAnalysisError(
                "Voice AI completed without producing structured JSON output.",
                status_code=500,
            )

        with open(output_json_path, "r", encoding="utf-8") as fh:
            payload: Dict[str, Any] = json.load(fh)
        return payload
    finally:
        output_json_path.unlink(missing_ok=True)


def read_voice_baseline(user_id: str) -> Dict[str, Any]:
    """Reads the per-user voice baseline JSON if present."""
    clean_id = validate_safe_user_id(user_id)
    profile_path = VOICE_PROFILES_DIR / f"{clean_id}.json"
    if not profile_path.is_file():
        return {
            "exists": False,
            "user_id": clean_id,
            "is_established": False,
            "observation_count": 0,
            "min_observations": 3,
            "stats": {},
            "history": [],
        }
    with open(profile_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    data["exists"] = True
    return data


def reset_voice_baseline(user_id: str) -> bool:
    """Deletes a user's voice baseline JSON file."""
    clean_id = validate_safe_user_id(user_id)
    profile_path = VOICE_PROFILES_DIR / f"{clean_id}.json"
    if profile_path.is_file():
        profile_path.unlink()
        return True
    return False
