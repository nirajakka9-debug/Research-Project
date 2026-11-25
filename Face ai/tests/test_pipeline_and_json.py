"""
test_pipeline_and_json.py
-------------------------
Integration and serialization tests.
Tests:
- JSON serialization with null feature values
- Verification of no NaN or Infinity in exported JSON
- Pipeline execution on a synthetic blank video (no-face case)
- Full round-trip JSON serialization and validation
"""

import json
import math
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from face_analyzer import (
    FaceBehaviorAnalyzer,
    AnalysisResult,
    VideoMetadata
)
from quality_assessment import QualityReport
from feature_calculations import ExtractedFeatures


def test_json_serialization_with_null_and_infinite_values():
    """Verify that JSON serialization works cleanly when features are null and handles NaNs safely."""
    meta = VideoMetadata(
        filepath="dummy.mp4",
        filename="dummy.mp4",
        filesize_bytes=1024,
        duration_sec=5.0,
        total_frames=150,
        fps=30.0,
        width=640,
        height=480
    )

    quality = QualityReport(
        total_frames=150,
        usable_frames=0,
        fps=30.0,
        duration_sec=5.0,
        detection_coverage=0.0,
        quality_score=0.0,
        is_reliable=False,
        warnings=["No face detected"]
    )

    features = ExtractedFeatures(
        facialMovementVelocity=None,
        eyeBlinkRatePm=None,
        headPoseJitterStd=None,
        smileIntensityProxy=None,
        browFurrowProxy=None,
        auxiliary_metrics={
            "potential_nan": float("nan"),
            "potential_inf": float("inf"),
            "valid_metric": 42.0
        }
    )

    result = AnalysisResult(
        metadata=meta,
        quality=quality,
        features=features,
        processing_time_sec=0.15
    )

    result_dict = result.to_dict()
    # Serialize to JSON string
    json_str = json.dumps(result_dict)

    # Verify no raw NaN or Infinity appears in standard JSON format
    assert "NaN" not in json_str
    assert "Infinity" not in json_str

    # Parse back from JSON
    parsed = json.loads(json_str)
    assert parsed["features"]["facialMovementVelocity"] is None
    assert parsed["features"]["eyeBlinkRatePm"] is None
    assert parsed["features"]["headPoseJitterStd"] is None
    assert parsed["features"]["smileIntensityProxy"] is None
    assert parsed["features"]["browFurrowProxy"] is None
    assert parsed["quality"]["quality_score"] == 0.0
    assert parsed["features"]["auxiliary_metrics"]["potential_nan"] is None
    assert parsed["features"]["auxiliary_metrics"]["potential_inf"] is None
    assert parsed["features"]["auxiliary_metrics"]["valid_metric"] == 42.0


def test_blank_video_pipeline_execution():
    """
    Creates a real blank synthetic MP4 video file and runs FaceBehaviorAnalyzer end-to-end.
    Confirms that when no face is present:
    - total_frames are counted
    - usable_frames == 0
    - coverage == 0.0
    - quality_score == 0.0
    - all features are None
    - JSON export succeeds without errors
    """
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        tmp_video_path = f.name
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_json_path = f.name

    fps = 30.0
    width, height = 320, 240
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(tmp_video_path, fourcc, fps, (width, height))

    # Write 30 blank dark frames (1.0 second of video)
    for _ in range(30):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        out.write(frame)
    out.release()

    try:
        analyzer = FaceBehaviorAnalyzer()
        res = analyzer.analyze_video(tmp_video_path, max_duration_sec=5.0)

        assert res.metadata.total_frames == 30
        assert res.quality.usable_frames == 0
        assert res.quality.detection_coverage == 0.0
        assert res.quality.quality_score == 0.0
        assert not res.quality.is_reliable

        # All features must be None (not fabricated)
        assert res.features.facialMovementVelocity is None
        assert res.features.eyeBlinkRatePm is None
        assert res.features.headPoseJitterStd is None
        assert res.features.smileIntensityProxy is None
        assert res.features.browFurrowProxy is None

        # Verify JSON export
        res_dict = res.to_dict()
        with open(tmp_json_path, "w", encoding="utf-8") as jf:
            json.dump(res_dict, jf, indent=2)

        with open(tmp_json_path, "r", encoding="utf-8") as jf:
            loaded = json.load(jf)

        assert loaded["quality"]["usable_frames"] == 0
        assert loaded["features"]["facialMovementVelocity"] is None
        assert "disclaimer" in loaded

    finally:
        Path(tmp_video_path).unlink(missing_ok=True)
        Path(tmp_json_path).unlink(missing_ok=True)
