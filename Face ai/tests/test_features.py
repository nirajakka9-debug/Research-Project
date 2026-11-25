"""
test_features.py
----------------
Unit tests for geometric and behavioural feature calculations using synthetic coordinates.
Tests:
- Inter-ocular distance normalization
- Eye Aspect Ratio (EAR) calculation
- Temporal blink event counting across consecutive frames
- Facial movement velocity calculation across frames
- Head pose estimation and solvePnP jitter
- Smile intensity proxy
- Brow furrow proxy
- Zero-duration and insufficient-frame edge cases
"""

import numpy as np
import pytest

from feature_calculations import (
    RIGHT_EYE_OUTER,
    RIGHT_EYE_INNER,
    RIGHT_EYE_TOP1,
    RIGHT_EYE_BOTTOM1,
    RIGHT_EYE_TOP2,
    RIGHT_EYE_BOTTOM2,
    LEFT_EYE_OUTER,
    LEFT_EYE_INNER,
    LEFT_EYE_TOP1,
    LEFT_EYE_BOTTOM1,
    LEFT_EYE_TOP2,
    LEFT_EYE_BOTTOM2,
    MOUTH_LEFT_CORNER,
    MOUTH_RIGHT_CORNER,
    RIGHT_BROW_INNER,
    LEFT_BROW_INNER,
    RIGHT_EYE_UPPER_CENTER,
    LEFT_EYE_UPPER_CENTER,
    NOSE_TIP,
    CHIN,
    calculate_interocular_distance,
    calculate_eye_aspect_ratio,
    count_blinks_from_ear_sequence,
    calculate_facial_movement_velocity,
    estimate_head_pose_angles,
    calculate_head_pose_jitter,
    calculate_smile_intensity_proxy,
    calculate_brow_furrow_proxy,
    extract_all_features,
    sanitize_float
)


def create_synthetic_neutral_face(landmarks_count: int = 478) -> np.ndarray:
    """
    Constructs a synthetic 2D/3D facial landmark array representing a standardized frontal face.
    Normalized coordinates in [0.0, 1.0].
    """
    pts = np.zeros((landmarks_count, 3), dtype=np.float32)

    # Eyes
    # Outer eye corners: 33 (right eye outer, screen left at x=0.35), 263 (left eye outer, screen right at x=0.65)
    pts[RIGHT_EYE_OUTER] = [0.35, 0.40, 0.0]
    pts[RIGHT_EYE_INNER] = [0.45, 0.40, 0.0]
    pts[RIGHT_EYE_TOP1] = [0.40, 0.38, 0.0]
    pts[RIGHT_EYE_BOTTOM1] = [0.40, 0.42, 0.0]
    pts[RIGHT_EYE_TOP2] = [0.42, 0.38, 0.0]
    pts[RIGHT_EYE_BOTTOM2] = [0.42, 0.42, 0.0]
    pts[RIGHT_EYE_UPPER_CENTER] = [0.40, 0.38, 0.0]

    pts[LEFT_EYE_INNER] = [0.55, 0.40, 0.0]
    pts[LEFT_EYE_OUTER] = [0.65, 0.40, 0.0]
    pts[LEFT_EYE_TOP1] = [0.60, 0.38, 0.0]
    pts[LEFT_EYE_BOTTOM1] = [0.60, 0.42, 0.0]
    pts[LEFT_EYE_TOP2] = [0.58, 0.38, 0.0]
    pts[LEFT_EYE_BOTTOM2] = [0.58, 0.42, 0.0]
    pts[LEFT_EYE_UPPER_CENTER] = [0.60, 0.38, 0.0]

    # Mouth
    pts[MOUTH_LEFT_CORNER] = [0.42, 0.70, 0.0]   # Subject's right, screen left
    pts[MOUTH_RIGHT_CORNER] = [0.58, 0.70, 0.0]  # Subject's left, screen right

    # Eyebrows
    pts[RIGHT_BROW_INNER] = [0.46, 0.33, 0.0]
    pts[LEFT_BROW_INNER] = [0.54, 0.33, 0.0]

    # Nose and Chin
    pts[NOSE_TIP] = [0.50, 0.52, 0.0]
    pts[CHIN] = [0.50, 0.85, 0.0]

    return pts


def test_interocular_distance():
    """Verify that interocular distance correctly measures outer eye corner distance."""
    face = create_synthetic_neutral_face()
    dist = calculate_interocular_distance(face)
    # x_dist = 0.65 - 0.35 = 0.30
    assert pytest.approx(dist, rel=1e-3) == 0.30


def test_eye_aspect_ratio_open_vs_closed():
    """Verify EAR calculation drops significantly when eye closes."""
    open_face = create_synthetic_neutral_face()
    ear_left, ear_right, ear_mean = calculate_eye_aspect_ratio(open_face)
    assert ear_mean > 0.25

    # Simulate closed eye by bringing upper and lower eyelids together
    closed_face = open_face.copy()
    closed_face[RIGHT_EYE_TOP1, 1] = 0.40
    closed_face[RIGHT_EYE_BOTTOM1, 1] = 0.40
    closed_face[RIGHT_EYE_TOP2, 1] = 0.40
    closed_face[RIGHT_EYE_BOTTOM2, 1] = 0.40

    closed_face[LEFT_EYE_TOP1, 1] = 0.40
    closed_face[LEFT_EYE_BOTTOM1, 1] = 0.40
    closed_face[LEFT_EYE_TOP2, 1] = 0.40
    closed_face[LEFT_EYE_BOTTOM2, 1] = 0.40

    c_left, c_right, c_mean = calculate_eye_aspect_ratio(closed_face)
    assert c_mean < 0.05
    assert c_mean < ear_mean


def test_blink_event_counting_consecutive_frames():
    """
    Verify temporal logic: consecutive closed-eye frames count as ONE blink,
    and reopening produces the blink event.
    """
    # Sequence of EARs:
    # 5 open frames -> 3 closed frames -> 5 open frames -> 4 closed frames -> 5 open frames
    ear_seq = (
        [0.32] * 5 +    # Open
        [0.12] * 3 +    # 1st Blink (3 consecutive closed frames)
        [0.31] * 5 +    # Reopened
        [0.10] * 4 +    # 2nd Blink (4 consecutive closed frames)
        [0.33] * 5      # Reopened
    )
    blinks = count_blinks_from_ear_sequence(ear_seq, threshold=0.21)
    assert blinks == 2, f"Expected 2 blinks, counted {blinks}"


def test_blink_event_prolonged_closure():
    """Verify that prolonged closure (> max_closed_frames) is not counted as a normal blink."""
    ear_seq = (
        [0.30] * 5 +
        [0.10] * 40 +   # Prolonged closure (40 frames > max_closed_frames=25)
        [0.30] * 5
    )
    blinks = count_blinks_from_ear_sequence(ear_seq, threshold=0.21, max_closed_frames=25)
    assert blinks == 0, f"Prolonged eye closure should not count as a normal blink, got {blinks}"


def test_facial_movement_velocity_static_vs_moving():
    """Verify velocity is zero for identical frames and positive for moving landmarks."""
    face1 = create_synthetic_neutral_face()
    face2 = face1.copy()

    timestamps = [0.0, 0.033, 0.066]
    # Static frames
    v_static = calculate_facial_movement_velocity([face1, face2, face1], timestamps)
    assert pytest.approx(v_static, abs=1e-5) == 0.0

    # Moving frames: displace landmarks
    face3 = face1.copy()
    face3[:, :2] += 0.05
    v_moving = calculate_facial_movement_velocity([face1, face3], [0.0, 0.5])
    assert v_moving is not None
    assert v_moving > 0.0


def test_head_pose_jitter_calculation():
    """Verify OpenCV solvePnP head pose estimation on synthetic landmarks."""
    face = create_synthetic_neutral_face()
    angles = estimate_head_pose_angles(face, img_w=640, img_h=480)
    assert angles is not None
    yaw, pitch, roll = angles
    # Should yield reasonable degrees for frontal face
    assert abs(yaw) < 30.0
    assert abs(pitch) < 30.0
    assert abs(roll) < 30.0

    # Test jitter std dev across sequence
    jitter_res = calculate_head_pose_jitter([face, face, face], img_w=640, img_h=480)
    assert jitter_res["headPoseJitterStd"] == 0.0


def test_smile_and_brow_proxies():
    """Verify smile and brow furrow geometric proxies."""
    neutral_face = create_synthetic_neutral_face()
    smile_neutral = calculate_smile_intensity_proxy(neutral_face)
    brow_neutral = calculate_brow_furrow_proxy(neutral_face)

    assert smile_neutral > 0.0
    assert brow_neutral > 0.0

    # Widen mouth (smiling)
    smiling_face = neutral_face.copy()
    smiling_face[MOUTH_LEFT_CORNER, 0] -= 0.04
    smiling_face[MOUTH_RIGHT_CORNER, 0] += 0.04
    smile_intensity = calculate_smile_intensity_proxy(smiling_face)
    assert smile_intensity > smile_neutral

    # Lower eyebrows toward eyes (furrowing)
    furrowed_face = neutral_face.copy()
    furrowed_face[RIGHT_BROW_INNER, 1] += 0.03
    furrowed_face[LEFT_BROW_INNER, 1] += 0.03
    brow_distance = calculate_brow_furrow_proxy(furrowed_face)
    # Lower value means closer to eyes = stronger furrow
    assert brow_distance < brow_neutral


def test_insufficient_frames_and_edge_cases():
    """Verify graceful handling when frames are missing or insufficient."""
    # Zero frames
    features_empty = extract_all_features([], [], 640, 480, 0.0, 0.0)
    assert features_empty.facialMovementVelocity is None
    assert features_empty.eyeBlinkRatePm is None
    assert features_empty.headPoseJitterStd is None
    assert features_empty.smileIntensityProxy is None
    assert features_empty.browFurrowProxy is None

    # 1 single frame: cannot compute velocity or jitter std
    single_face = create_synthetic_neutral_face()
    features_single = extract_all_features([single_face], [0.0], 640, 480, 0.033, 1.0)
    assert features_single.facialMovementVelocity is None
    assert features_single.headPoseJitterStd is None
    assert features_single.eyeBlinkRatePm is None  # < 3.0s duration


def test_sanitize_float_nan_and_inf():
    """Verify that NaN and Inf are cleanly converted to None or finite numbers."""
    assert sanitize_float(None) is None
    assert sanitize_float(float("nan")) is None
    assert sanitize_float(float("inf")) is None
    assert sanitize_float(float("-inf")) is None
    assert sanitize_float(3.14159) == 3.1416
