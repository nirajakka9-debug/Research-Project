"""
test_quality.py
----------------
Unit tests for quality assessment and reliability scoring logic.
"""

import numpy as np
import pytest

from quality_assessment import (
    compute_bbox_from_landmarks,
    assess_frame_lighting,
    calculate_quality_score,
    build_quality_report,
    QualityReport
)


def test_bbox_from_landmarks():
    """Verify integer bounding box computation from normalized landmarks."""
    landmarks = np.array([
        [0.2, 0.3, 0.0],
        [0.5, 0.6, 0.0],
        [0.4, 0.7, 0.0]
    ], dtype=np.float32)

    bbox = compute_bbox_from_landmarks(landmarks, img_w=1000, img_h=1000)
    assert bbox == (200, 300, 500, 700)


def test_assess_frame_lighting():
    """Verify luminance and contrast calculations on dark vs bright synthetic frames."""
    dark_frame = np.full((100, 100, 3), 20, dtype=np.uint8)
    bbox = (10, 10, 90, 90)
    lum_dark, con_dark = assess_frame_lighting(dark_frame, bbox)
    assert lum_dark < 30.0
    assert con_dark < 1.0

    bright_frame = np.full((100, 100, 3), 150, dtype=np.uint8)
    lum_bright, con_bright = assess_frame_lighting(bright_frame, bbox)
    assert 140.0 < lum_bright < 160.0


def test_quality_score_zero_coverage():
    """Verify quality score is strictly 0.0 when no face is detected."""
    score = calculate_quality_score(
        coverage=0.0,
        scale_subscore=100.0,
        lighting_subscore=100.0,
        stability_subscore=100.0
    )
    assert score == 0.0


def test_quality_report_no_face_detected():
    """Verify quality report correctly flags full failure when 0 usable frames."""
    report = build_quality_report(
        total_frames=100,
        usable_frames=0,
        fps=30.0,
        luminance_samples=[],
        contrast_samples=[],
        scale_samples=[],
        multi_face_count=0,
        identity_jumps_count=0
    )
    assert report.usable_frames == 0
    assert report.detection_coverage == 0.0
    assert report.quality_score == 0.0
    assert not report.is_reliable
    assert any("No facial landmarks detected" in w for w in report.warnings)


def test_quality_report_high_quality():
    """Verify high quality report with good lighting, scale, and 100% coverage."""
    report = build_quality_report(
        total_frames=150,
        usable_frames=150,
        fps=30.0,
        luminance_samples=[120.0] * 150,
        contrast_samples=[40.0] * 150,
        scale_samples=[0.20] * 150,
        multi_face_count=0,
        identity_jumps_count=0
    )
    assert report.detection_coverage == 1.0
    assert report.quality_score >= 90.0
    assert report.is_reliable
    assert len(report.warnings) == 0


def test_quality_report_multi_face_penalty():
    """Verify penalty and warning when multiple faces are detected."""
    report = build_quality_report(
        total_frames=100,
        usable_frames=80,
        fps=30.0,
        luminance_samples=[110.0] * 80,
        contrast_samples=[35.0] * 80,
        scale_samples=[0.15] * 80,
        multi_face_count=20,  # 20% of frames have multiple faces
        identity_jumps_count=2
    )
    assert report.multi_face_frames == 20
    assert report.identity_switch_warnings == 2
    assert any("Multiple faces detected" in w for w in report.warnings)
    assert any("identity shift" in w for w in report.warnings)
