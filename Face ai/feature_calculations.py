"""
feature_calculations.py
-----------------------
Pure mathematical and geometric feature extraction functions for facial behaviour analysis.

Implements five core behavioural features:
1. facialMovementVelocity: Normalized landmark displacement per second.
2. eyeBlinkRatePm: Temporal Eye Aspect Ratio (EAR) blink detection per minute.
3. headPoseJitterStd: OpenCV solvePnP 3D-to-2D head pose angular variability (std dev).
4. smileIntensityProxy: Normalized mouth-width-to-interocular distance ratio.
5. browFurrowProxy: Normalized brow-to-eye vertical distance ratio.

IMPORTANT: All metrics are purely geometric/behavioural proxies.
They do NOT classify emotions, infer mental illnesses, or provide medical diagnoses.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
import numpy as np
import cv2


# Canonical landmark indices in MediaPipe Face Mesh (468/478 format)
# Eyes
RIGHT_EYE_OUTER = 33
RIGHT_EYE_INNER = 133
RIGHT_EYE_TOP1 = 160
RIGHT_EYE_BOTTOM1 = 144
RIGHT_EYE_TOP2 = 158
RIGHT_EYE_BOTTOM2 = 153
RIGHT_EYE_UPPER_CENTER = 159

LEFT_EYE_OUTER = 263
LEFT_EYE_INNER = 362
LEFT_EYE_TOP1 = 385
LEFT_EYE_BOTTOM1 = 380
LEFT_EYE_TOP2 = 387
LEFT_EYE_BOTTOM2 = 373
LEFT_EYE_UPPER_CENTER = 386

# Mouth
MOUTH_LEFT_CORNER = 61      # Subject's right, screen left
MOUTH_RIGHT_CORNER = 291    # Subject's left, screen right
MOUTH_TOP_LIP = 0
MOUTH_BOTTOM_LIP = 17

# Eyebrows
RIGHT_BROW_INNER = 107      # Subject's right, screen left
RIGHT_BROW_MID = 66
LEFT_BROW_INNER = 336       # Subject's left, screen right
LEFT_BROW_MID = 296

# Head pose landmarks
NOSE_TIP = 1
CHIN = 152

# Standard 3D anthropometric face model points (in millimeters)
# Standard camera coordinate convention: X right, Y down, Z forward
# Relative to nose tip (0, 0, 0)
GENERIC_FACE_3D_MODEL = np.array([
    [0.0, 0.0, 0.0],         # Nose tip (landmark 1)
    [0.0, 110.0, -30.0],      # Chin (landmark 152, below nose)
    [-75.0, -50.0, -40.0],    # Right eye outer corner (landmark 33, screen left)
    [75.0, -50.0, -40.0],     # Left eye outer corner (landmark 263, screen right)
    [-40.0, 60.0, -30.0],     # Right mouth corner (landmark 61, screen left)
    [40.0, 60.0, -30.0]       # Left mouth corner (landmark 291, screen right)
], dtype=np.float64)


def sanitize_float(val: Optional[float], decimals: int = 4) -> Optional[float]:
    """Ensures a float is finite and rounded, returning None if NaN, Inf, or None."""
    if val is None:
        return None
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, decimals)
    except (ValueError, TypeError):
        return None


def calculate_interocular_distance(landmarks: np.ndarray) -> float:
    """
    Computes Euclidean distance between outer eye corners (landmarks 33 and 263).
    Used as the standard face-size normalizer.
    """
    p1 = landmarks[RIGHT_EYE_OUTER, :2]
    p2 = landmarks[LEFT_EYE_OUTER, :2]
    dist = float(np.linalg.norm(p1 - p2))
    return dist if dist > 1e-6 else 1e-6


def calculate_eye_aspect_ratio(landmarks: np.ndarray) -> Tuple[float, float, float]:
    """
    Calculates Eye Aspect Ratio (EAR) for both eyes and their mean.
    EAR = (||p_top1 - p_bot1|| + ||p_top2 - p_bot2||) / (2 * ||p_outer - p_inner||)
    Returns: (ear_left, ear_right, ear_mean)
    """
    # Left eye (subject left, screen right)
    left_outer = landmarks[LEFT_EYE_OUTER, :2]
    left_inner = landmarks[LEFT_EYE_INNER, :2]
    left_t1 = landmarks[LEFT_EYE_TOP1, :2]
    left_b1 = landmarks[LEFT_EYE_BOTTOM1, :2]
    left_t2 = landmarks[LEFT_EYE_TOP2, :2]
    left_b2 = landmarks[LEFT_EYE_BOTTOM2, :2]

    left_w = float(np.linalg.norm(left_outer - left_inner))
    left_h1 = float(np.linalg.norm(left_t1 - left_b1))
    left_h2 = float(np.linalg.norm(left_t2 - left_b2))
    ear_left = (left_h1 + left_h2) / (2.0 * max(1e-6, left_w))

    # Right eye (subject right, screen left)
    right_outer = landmarks[RIGHT_EYE_OUTER, :2]
    right_inner = landmarks[RIGHT_EYE_INNER, :2]
    right_t1 = landmarks[RIGHT_EYE_TOP1, :2]
    right_b1 = landmarks[RIGHT_EYE_BOTTOM1, :2]
    right_t2 = landmarks[RIGHT_EYE_TOP2, :2]
    right_b2 = landmarks[RIGHT_EYE_BOTTOM2, :2]

    right_w = float(np.linalg.norm(right_outer - right_inner))
    right_h1 = float(np.linalg.norm(right_t1 - right_b1))
    right_h2 = float(np.linalg.norm(right_t2 - right_b2))
    ear_right = (right_h1 + right_h2) / (2.0 * max(1e-6, right_w))

    ear_mean = (ear_left + ear_right) / 2.0
    return ear_left, ear_right, ear_mean


def count_blinks_from_ear_sequence(
    ear_sequence: List[float],
    threshold: float = 0.21,
    min_closed_frames: int = 1,
    max_closed_frames: int = 25
) -> int:
    """
    Counts distinct blink events across consecutive frames using temporal hysteresis logic.
    - Eye is closed when EAR < threshold.
    - Consecutive closed frames count as exactly ONE blink when the eye reopens.
    - Prolonged closures (> max_closed_frames, e.g. > 800ms) are excluded as non-blink closures.
    """
    blink_count = 0
    closed_frames = 0
    in_blink = False

    for ear in ear_sequence:
        if ear < threshold:
            closed_frames += 1
            in_blink = True
        else:
            if in_blink:
                if min_closed_frames <= closed_frames <= max_closed_frames:
                    blink_count += 1
                closed_frames = 0
                in_blink = False

    # Check if a blink was completing at the very end of the sequence
    if in_blink and min_closed_frames <= closed_frames <= max_closed_frames:
        blink_count += 1

    return blink_count


def calculate_facial_movement_velocity(
    landmarks_per_frame: List[np.ndarray],
    timestamps_sec: List[float]
) -> Optional[float]:
    """
    Computes average displacement per second in normalized face-size units across usable frames.
    Normalized by inter-ocular distance (outer eye corners 33 to 263).
    """
    if len(landmarks_per_frame) < 2 or len(timestamps_sec) < 2:
        return None

    step_velocities: List[float] = []

    for i in range(1, len(landmarks_per_frame)):
        prev_pts = landmarks_per_frame[i - 1]
        curr_pts = landmarks_per_frame[i]
        dt = timestamps_sec[i] - timestamps_sec[i - 1]

        if dt <= 1e-5:
            continue

        face_size_prev = calculate_interocular_distance(prev_pts)
        face_size_curr = calculate_interocular_distance(curr_pts)
        avg_face_size = (face_size_prev + face_size_curr) / 2.0

        if avg_face_size <= 1e-6:
            continue

        # Coordinate Euclidean displacement across all shared landmarks
        diffs = curr_pts[:, :2] - prev_pts[:, :2]
        displacements = np.linalg.norm(diffs, axis=1)
        mean_displacement = float(np.mean(displacements))

        # Normalized displacement per second
        norm_displacement = mean_displacement / avg_face_size
        step_velocity = norm_displacement / dt
        step_velocities.append(step_velocity)

    if not step_velocities:
        return None

    return float(np.mean(step_velocities))


def estimate_head_pose_angles(
    landmarks: np.ndarray,
    img_w: int,
    img_h: int
) -> Optional[Tuple[float, float, float]]:
    """
    Estimates 3D head pose (yaw, pitch, roll in degrees) via OpenCV solvePnP
    using 6 canonical 2D facial landmarks mapped to a generic 3D face model.
    Returns: (yaw, pitch, roll) in degrees.
    """
    # 2D pixel coordinates for [Nose, Chin, Right Eye Outer, Left Eye Outer, Right Mouth, Left Mouth]
    indices = [NOSE_TIP, CHIN, RIGHT_EYE_OUTER, LEFT_EYE_OUTER, MOUTH_LEFT_CORNER, MOUTH_RIGHT_CORNER]
    image_points = np.zeros((6, 2), dtype=np.float64)

    for idx_pos, lm_idx in enumerate(indices):
        if lm_idx >= len(landmarks):
            return None
        image_points[idx_pos, 0] = landmarks[lm_idx, 0] * img_w
        image_points[idx_pos, 1] = landmarks[lm_idx, 1] * img_h

    # Approximate pinhole camera matrix
    focal_length = float(img_w)
    center = (img_w / 2.0, img_h / 2.0)
    camera_matrix = np.array([
        [focal_length, 0.0, center[0]],
        [0.0, focal_length, center[1]],
        [0.0, 0.0, 1.0]
    ], dtype=np.float64)
    dist_coeffs = np.zeros((4, 1), dtype=np.float64)

    success, rvec, tvec = cv2.solvePnP(
        GENERIC_FACE_3D_MODEL,
        image_points,
        camera_matrix,
        dist_coeffs,
        flags=cv2.SOLVEPNP_ITERATIVE
    )

    if not success:
        return None

    # Convert rotation vector to 3x3 rotation matrix
    rmat, _ = cv2.Rodrigues(rvec)

    # Decompose rotation matrix into Euler angles using OpenCV RQDecomp3x3
    angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)
    pitch, yaw, roll = float(angles[0]), float(angles[1]), float(angles[2])

    # Normalize roll to (-90, 90) for frontal camera perspective
    if roll > 90.0:
        roll -= 180.0
    elif roll < -90.0:
        roll += 180.0

    return float(yaw), float(pitch), float(roll)


def calculate_head_pose_jitter(
    landmarks_per_frame: List[np.ndarray],
    img_w: int,
    img_h: int
) -> Dict[str, Optional[float]]:
    """
    Computes angular variability (standard deviation in degrees) of yaw, pitch, roll
    and aggregate jitter across usable frames.
    """
    if len(landmarks_per_frame) < 3:
        return {
            "headPoseJitterStd": None,
            "yawStd": None,
            "pitchStd": None,
            "rollStd": None
        }

    yaws: List[float] = []
    pitches: List[float] = []
    rolls: List[float] = []

    for lm in landmarks_per_frame:
        angles = estimate_head_pose_angles(lm, img_w, img_h)
        if angles is not None:
            yaw, pitch, roll = angles
            yaws.append(yaw)
            pitches.append(pitch)
            rolls.append(roll)

    if len(yaws) < 3:
        return {
            "headPoseJitterStd": None,
            "yawStd": None,
            "pitchStd": None,
            "rollStd": None
        }

    yaw_std = float(np.std(yaws))
    pitch_std = float(np.std(pitches))
    roll_std = float(np.std(rolls))

    # Vector standard deviation (Euclidean norm of component standard deviations)
    aggregate_jitter = float(np.sqrt(yaw_std**2 + pitch_std**2 + roll_std**2))

    return {
        "headPoseJitterStd": sanitize_float(aggregate_jitter, 3),
        "yawStd": sanitize_float(yaw_std, 3),
        "pitchStd": sanitize_float(pitch_std, 3),
        "rollStd": sanitize_float(roll_std, 3)
    }


def calculate_smile_intensity_proxy(
    landmarks: np.ndarray
) -> float:
    """
    Calculates instantaneous normalized mouth-width-to-interocular ratio.
    Mouth corners: 61 to 291; Interocular: 33 to 263.
    """
    left_corner = landmarks[MOUTH_LEFT_CORNER, :2]
    right_corner = landmarks[MOUTH_RIGHT_CORNER, :2]
    mouth_w = float(np.linalg.norm(left_corner - right_corner))
    interocular = calculate_interocular_distance(landmarks)
    return mouth_w / max(1e-6, interocular)


def calculate_brow_furrow_proxy(
    landmarks: np.ndarray
) -> float:
    """
    Calculates instantaneous normalized eyebrow-to-eye vertical distance ratio.
    Eyebrow inner points: 107 (right) and 336 (left).
    Eye upper eyelid centers: 159 (right) and 386 (left).
    Normalized by inter-ocular distance. Lower value indicates stronger brow furrowing / contraction.
    """
    right_brow = landmarks[RIGHT_BROW_INNER, :2]
    right_eye = landmarks[RIGHT_EYE_UPPER_CENTER, :2]
    dist_right = float(np.linalg.norm(right_brow - right_eye))

    left_brow = landmarks[LEFT_BROW_INNER, :2]
    left_eye = landmarks[LEFT_EYE_UPPER_CENTER, :2]
    dist_left = float(np.linalg.norm(left_brow - left_eye))

    avg_brow_dist = (dist_right + dist_left) / 2.0
    interocular = calculate_interocular_distance(landmarks)
    return avg_brow_dist / max(1e-6, interocular)


@dataclass
class ExtractedFeatures:
    """Container for the five facial behaviour features and associated metadata."""
    facialMovementVelocity: Optional[float]
    eyeBlinkRatePm: Optional[float]
    headPoseJitterStd: Optional[float]
    smileIntensityProxy: Optional[float]
    browFurrowProxy: Optional[float]
    auxiliary_metrics: Dict[str, Any] = field(default_factory=dict)
    feature_definitions: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary with guaranteed finite values."""
        return {
            "facialMovementVelocity": sanitize_float(self.facialMovementVelocity),
            "eyeBlinkRatePm": sanitize_float(self.eyeBlinkRatePm),
            "headPoseJitterStd": sanitize_float(self.headPoseJitterStd),
            "smileIntensityProxy": sanitize_float(self.smileIntensityProxy),
            "browFurrowProxy": sanitize_float(self.browFurrowProxy),
            "units": {
                "facialMovementVelocity": "normalized face-units / sec",
                "eyeBlinkRatePm": "blinks / min",
                "headPoseJitterStd": "degrees",
                "smileIntensityProxy": "normalized mouth-to-interocular ratio (dimensionless)",
                "browFurrowProxy": "normalized brow-to-eye distance (dimensionless)"
            },
            "auxiliary_metrics": {
                k: sanitize_float(v) if isinstance(v, (float, np.floating)) else v
                for k, v in self.auxiliary_metrics.items()
            },
            "feature_definitions": dict(self.feature_definitions)
        }


def extract_all_features(
    landmarks_per_frame: List[np.ndarray],
    timestamps_sec: List[float],
    img_w: int,
    img_h: int,
    usable_duration_sec: float,
    coverage: float
) -> ExtractedFeatures:
    """
    Executes full feature extraction pipeline over usable frame landmark sequence.
    Handles short clips, missing frames, and insufficient data cleanly.
    """
    definitions = {
        "facialMovementVelocity": (
            "Average Euclidean displacement across all 468 landmarks normalized by outer-eye "
            "inter-ocular distance per second."
        ),
        "eyeBlinkRatePm": (
            "Extrapolated blinks per minute calculated from consecutive Eye Aspect Ratio (EAR < 0.21) "
            "closure and reopening events over usable recording duration."
        ),
        "headPoseJitterStd": (
            "Vector standard deviation of yaw, pitch, and roll in degrees estimated via OpenCV "
            "solvePnP using 6 facial anchor landmarks mapped to a generic 3D anthropometric face model."
        ),
        "smileIntensityProxy": (
            "Mean ratio of mouth width (corners 61-291) to inter-ocular distance (corners 33-263) "
            "across usable frames."
        ),
        "browFurrowProxy": (
            "Mean vertical distance between inner eyebrow landmarks and upper eyelid centers "
            "normalized by inter-ocular distance. Lower value indicates stronger brow furrowing."
        )
    }

    usable_count = len(landmarks_per_frame)
    if usable_count == 0:
        return ExtractedFeatures(
            facialMovementVelocity=None,
            eyeBlinkRatePm=None,
            headPoseJitterStd=None,
            smileIntensityProxy=None,
            browFurrowProxy=None,
            auxiliary_metrics={"status": "No usable facial landmarks detected"},
            feature_definitions=definitions
        )

    # 1. Facial Movement Velocity
    vel = calculate_facial_movement_velocity(landmarks_per_frame, timestamps_sec)

    # 2. Eye Blink Rate per minute
    # Compute EAR per frame
    ear_sequence: List[float] = []
    for lm in landmarks_per_frame:
        _, _, ear_m = calculate_eye_aspect_ratio(lm)
        ear_sequence.append(ear_m)

    total_blinks = count_blinks_from_ear_sequence(ear_sequence, threshold=0.21)

    # Distinguish zero blinks from unreliable estimation:
    # Requires at least 3.0 seconds of usable duration and >= 35% detection coverage
    if usable_duration_sec >= 3.0 and coverage >= 0.35:
        blink_rate_pm = (total_blinks / usable_duration_sec) * 60.0
    else:
        blink_rate_pm = None

    # 3. Head Pose Jitter
    pose_res = calculate_head_pose_jitter(landmarks_per_frame, img_w, img_h)
    jitter = pose_res["headPoseJitterStd"]

    # 4. Smile Intensity Proxy
    smile_ratios = [calculate_smile_intensity_proxy(lm) for lm in landmarks_per_frame]
    mean_smile = float(np.mean(smile_ratios)) if smile_ratios else None
    peak_smile = float(np.max(smile_ratios)) if smile_ratios else None

    # 5. Brow Furrow Proxy
    brow_ratios = [calculate_brow_furrow_proxy(lm) for lm in landmarks_per_frame]
    mean_brow = float(np.mean(brow_ratios)) if brow_ratios else None
    min_brow = float(np.min(brow_ratios)) if brow_ratios else None

    aux = {
        "total_blinks_detected": total_blinks,
        "ear_mean": sanitize_float(float(np.mean(ear_sequence)) if ear_sequence else None),
        "yaw_std_deg": pose_res.get("yawStd"),
        "pitch_std_deg": pose_res.get("pitchStd"),
        "roll_std_deg": pose_res.get("rollStd"),
        "smile_peak_ratio": sanitize_float(peak_smile),
        "brow_min_ratio": sanitize_float(min_brow)
    }

    return ExtractedFeatures(
        facialMovementVelocity=sanitize_float(vel),
        eyeBlinkRatePm=sanitize_float(blink_rate_pm),
        headPoseJitterStd=sanitize_float(jitter),
        smileIntensityProxy=sanitize_float(mean_smile),
        browFurrowProxy=sanitize_float(mean_brow),
        auxiliary_metrics=aux,
        feature_definitions=definitions
    )
