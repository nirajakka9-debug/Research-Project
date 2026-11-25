"""Centralized configuration and strict path/input validation constants."""

from __future__ import annotations

import os
import re
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
WEB_APP_DIR = BACKEND_DIR.parent
WORKSPACE_ROOT = WEB_APP_DIR.parent.parent

FACE_AI_DIR = Path(os.getenv("MINDTRACK_FACE_AI_DIR", str(WORKSPACE_ROOT / "Face ai"))).resolve()
VOICE_AI_DIR = Path(os.getenv("MINDTRACK_VOICE_AI_DIR", str(WORKSPACE_ROOT / "Voice ai - Copy"))).resolve()

DATA_DIR = Path(os.getenv("MINDTRACK_DATA_DIR", str(BACKEND_DIR / "data"))).resolve()
UPLOAD_FACE_DIR = DATA_DIR / "uploads" / "face"
UPLOAD_VOICE_DIR = DATA_DIR / "uploads" / "voice"
OUTPUTS_DIR = DATA_DIR / "outputs"
FACE_PROFILES_DIR = DATA_DIR / "face_profiles"
VOICE_PROFILES_DIR = DATA_DIR / "voice_profiles"

for _directory in (
    DATA_DIR,
    UPLOAD_FACE_DIR,
    UPLOAD_VOICE_DIR,
    OUTPUTS_DIR,
    FACE_PROFILES_DIR,
    VOICE_PROFILES_DIR,
):
    _directory.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv(
    "MINDTRACK_DATABASE_URL",
    f"sqlite:///{(DATA_DIR / 'mindtrack.db').as_posix()}",
)

SAFE_USER_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
SUPPORTED_AUDIO_EXTENSIONS = {".wav"}

MAX_VIDEO_SIZE_BYTES = 150 * 1024 * 1024  # 150 MB
MAX_AUDIO_SIZE_BYTES = 50 * 1024 * 1024   # 50 MB
DEFAULT_FACE_MAX_DURATION_SEC = 30.0
MAX_FACE_DURATION_SEC = 30.0
MIN_FACE_DURATION_SEC = 1.0

FACE_SUBPROCESS_TIMEOUT_SEC = 180
VOICE_SUBPROCESS_TIMEOUT_SEC = 90

NON_DIAGNOSTIC_NOTICE = (
    "MindTrack is a non-diagnostic wellness research and personal-baseline monitoring tool. "
    "It does NOT detect, diagnose, or classify stress, depression, anxiety, or any medical or "
    "psychiatric condition, and does NOT compute a clinical stress score."
)


def validate_safe_user_id(user_id: str) -> str:
    """Strictly validates participant IDs to prevent path traversal or injection."""
    if not user_id or not isinstance(user_id, str):
        raise ValueError("User ID must be a non-empty string.")
    cleaned = user_id.strip()
    if not SAFE_USER_ID_REGEX.match(cleaned):
        raise ValueError(
            "User ID must be 1-64 characters containing only letters, numbers, underscores, or hyphens."
        )
    return cleaned
