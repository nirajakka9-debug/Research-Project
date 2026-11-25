"""Safe subprocess adapter for the standalone Face ai Python analyzer."""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import UploadFile

from ..config import (
    DEFAULT_FACE_MAX_DURATION_SEC,
    FACE_AI_DIR,
    FACE_PROFILES_DIR,
    FACE_SUBPROCESS_TIMEOUT_SEC,
    MAX_FACE_DURATION_SEC,
    MAX_VIDEO_SIZE_BYTES,
    MIN_FACE_DURATION_SEC,
    OUTPUTS_DIR,
    SUPPORTED_VIDEO_EXTENSIONS,
    UPLOAD_FACE_DIR,
    validate_safe_user_id,
)

VALID_FACE_MODES = {"single", "calibrate", "assess"}


class FaceAnalysisError(Exception):
    """Structured error raised during facial video validation or analysis."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _extract_error_message(stderr_text: str, stdout_text: str, returncode: int) -> str:
    combined = "\n".join(part for part in (stderr_text, stdout_text) if part).strip()
    if not combined:
        return f"Facial analysis exited with code {returncode}."

    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    for marker in ("[ERROR]", "[NOTICE]", "[UNEXPECTED ERROR]"):
        for idx, line in enumerate(lines):
            if marker in line:
                tail = " ".join(lines[idx : idx + 3])
                return tail.replace(marker, "").strip()
    return lines[-1]


async def save_validated_video_upload(upload: UploadFile) -> tuple[Path, str]:
    """Validates filename extension & streaming size, storing to a generated UUID path."""
    original_name = Path(upload.filename or "recording.mp4").name
    ext = Path(original_name).suffix.lower()
    if ext not in SUPPORTED_VIDEO_EXTENSIONS:
        raise FaceAnalysisError(
            f"Unsupported video format '{ext or 'unknown'}'. Supported formats: {', '.join(sorted(SUPPORTED_VIDEO_EXTENSIONS))}.",
            status_code=400,
        )

    safe_path = UPLOAD_FACE_DIR / f"face_{uuid.uuid4().hex}{ext}"
    total_bytes = 0
    try:
        with open(safe_path, "wb") as out_file:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_VIDEO_SIZE_BYTES:
                    raise FaceAnalysisError(
                        f"Video exceeds maximum allowed file size ({MAX_VIDEO_SIZE_BYTES // (1024 * 1024)} MB).",
                        status_code=413,
                    )
                out_file.write(chunk)
        if total_bytes == 0:
            raise FaceAnalysisError("Uploaded video file is empty (0 bytes).", status_code=400)
        return safe_path, original_name
    except Exception:
        safe_path.unlink(missing_ok=True)
        raise


def run_face_analyzer(
    video_path: Path,
    user_id: str,
    mode: str = "single",
    max_duration: float = DEFAULT_FACE_MAX_DURATION_SEC,
    update_baseline: bool = False,
) -> Dict[str, Any]:
    """Executes Face ai/main.py in an isolated subprocess without shell interpolation."""
    face_main = FACE_AI_DIR / "main.py"
    if not face_main.is_file():
        raise FaceAnalysisError(
            f"Face AI module not found at '{face_main}'.",
            status_code=503,
        )

    try:
        clean_user_id = validate_safe_user_id(user_id)
    except ValueError as exc:
        raise FaceAnalysisError(str(exc), status_code=400) from exc

    if mode not in VALID_FACE_MODES:
        raise FaceAnalysisError(
            f"Invalid operational mode '{mode}'. Choose from: {', '.join(sorted(VALID_FACE_MODES))}.",
            status_code=400,
        )

    if max_duration < MIN_FACE_DURATION_SEC or max_duration > MAX_FACE_DURATION_SEC:
        raise FaceAnalysisError(
            f"max_duration must be between {MIN_FACE_DURATION_SEC:.0f} and {MAX_FACE_DURATION_SEC:.0f} seconds.",
            status_code=400,
        )

    output_json_path = OUTPUTS_DIR / f"face_out_{uuid.uuid4().hex}.json"

    cmd = [
        sys.executable,
        str(face_main),
        "--video",
        str(video_path),
        "--mode",
        mode,
        "--max-duration",
        f"{max_duration:.1f}",
        "--profiles-dir",
        str(FACE_PROFILES_DIR),
        "--output",
        str(output_json_path),
    ]

    if mode in {"calibrate", "assess"}:
        cmd.extend(["--user-id", clean_user_id])
    if mode == "assess" and update_baseline:
        cmd.append("--update-baseline")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(FACE_AI_DIR),
            shell=False,
            capture_output=True,
            text=True,
            timeout=FACE_SUBPROCESS_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output_json_path.unlink(missing_ok=True)
        raise FaceAnalysisError(
            f"Facial video analysis timed out after {FACE_SUBPROCESS_TIMEOUT_SEC}s.",
            status_code=504,
        ) from exc
    except OSError as exc:
        output_json_path.unlink(missing_ok=True)
        raise FaceAnalysisError(
            f"Failed to start Face AI process: {exc}",
            status_code=500,
        ) from exc

    try:
        if proc.returncode != 0:
            msg = _extract_error_message(proc.stderr, proc.stdout, proc.returncode)
            status = 400 if proc.returncode == 1 else 500
            raise FaceAnalysisError(msg, status_code=status)

        if not output_json_path.is_file():
            raise FaceAnalysisError(
                "Face AI completed without generating structured JSON output.",
                status_code=500,
            )

        with open(output_json_path, "r", encoding="utf-8") as fh:
            payload: Dict[str, Any] = json.load(fh)
        payload["operational_mode"] = mode
        if mode in {"calibrate", "assess"}:
            payload["user_id"] = clean_user_id
        return payload
    finally:
        output_json_path.unlink(missing_ok=True)


def read_face_baseline(user_id: str) -> Dict[str, Any]:
    """Reads the per-user facial baseline profile JSON if present."""
    clean_id = validate_safe_user_id(user_id)
    profile_path = FACE_PROFILES_DIR / f"{clean_id}.json"
    if not profile_path.is_file():
        return {
            "exists": False,
            "user_id": clean_id,
            "is_calibrated": False,
            "total_checkins_recorded": 0,
            "min_calibration_checkins": 5,
            "feature_stats": {},
            "history": [],
        }
    with open(profile_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    data["exists"] = True
    return data


def reset_face_baseline(user_id: str) -> bool:
    """Deletes a user's facial baseline JSON file."""
    clean_id = validate_safe_user_id(user_id)
    profile_path = FACE_PROFILES_DIR / f"{clean_id}.json"
    if profile_path.is_file():
        profile_path.unlink()
        return True
    return False
