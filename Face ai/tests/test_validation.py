"""
test_validation.py
------------------
Unit tests for input video file validation logic.
Tests missing paths, unsupported formats, empty files, unreadable codecs, and duration limits.
"""

import tempfile
from pathlib import Path
import cv2
import numpy as np
import pytest

from face_analyzer import validate_video_file, VideoValidationError


def test_missing_video_path():
    """Verify that a nonexistent video file path raises VideoValidationError."""
    with pytest.raises(VideoValidationError, match="does not exist"):
        validate_video_file("nonexistent_video_file_xyz_123.mp4")


def test_unsupported_file_extension():
    """Verify that non-video extensions (e.g. .txt, .png) raise VideoValidationError."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"sample text")
        tmp_name = f.name

    try:
        with pytest.raises(VideoValidationError, match="Unsupported video file extension"):
            validate_video_file(tmp_name)
    finally:
        Path(tmp_name).unlink(missing_ok=True)


def test_empty_video_file():
    """Verify that an empty (0 bytes) video file raises VideoValidationError."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        tmp_name = f.name

    try:
        with pytest.raises(VideoValidationError, match="empty \\(0 bytes\\)"):
            validate_video_file(tmp_name)
    finally:
        Path(tmp_name).unlink(missing_ok=True)


def test_unreadable_corrupt_video():
    """Verify that a non-decodable binary file named as .mp4 raises VideoValidationError."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"corrupted binary header that is not a real video")
        tmp_name = f.name

    try:
        with pytest.raises(VideoValidationError, match="cannot be read or contains no valid frames|could not open"):
            validate_video_file(tmp_name)
    finally:
        Path(tmp_name).unlink(missing_ok=True)


def test_duration_limit_exceeded():
    """Verify that a video exceeding max_duration_sec raises VideoValidationError."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        tmp_name = f.name

    # Create a 2-second synthetic video (60 frames at 30 fps)
    fps = 30.0
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(tmp_name, fourcc, fps, (320, 240))
    for _ in range(60):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        out.write(frame)
    out.release()

    try:
        # Should succeed when max_duration is 5.0s
        meta = validate_video_file(tmp_name, max_duration_sec=5.0)
        assert meta.total_frames == 60
        assert meta.fps == 30.0

        # Should fail when max_duration is 1.0s
        with pytest.raises(VideoValidationError, match="exceeds configured maximum allowed duration"):
            validate_video_file(tmp_name, max_duration_sec=1.0)
    finally:
        Path(tmp_name).unlink(missing_ok=True)
