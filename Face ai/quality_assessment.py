"""
quality_assessment.py
---------------------
Computes quantitative video and facial tracking quality metrics for the
facial-behaviour analysis pipeline.

Evaluates:
- Detection coverage (usable frames / total frames)
- Face bounding box scale adequacy relative to frame
- Lighting luminance and contrast across detected face regions
- Tracking continuity and single-face identity consistency
- Overall quality score scaled from 0 to 100
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import numpy as np


@dataclass
class QualityReport:
    """Encapsulates all quality metrics and reliability assessments."""
    total_frames: int
    usable_frames: int
    fps: float
    duration_sec: float
    detection_coverage: float
    quality_score: float
    is_reliable: bool
    is_suitable_for_baseline: bool = False
    multi_face_frames: int = 0
    identity_switch_warnings: int = 0
    avg_face_scale: float = 0.0
    avg_luminance: float = 0.0
    avg_contrast: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a clean dictionary representation with guaranteed finite numbers."""
        def _sanitize(val: Any) -> Any:
            if isinstance(val, (float, np.floating)):
                if np.isnan(val) or np.isinf(val):
                    return None
                return round(float(val), 4)
            return val

        return {
            "total_frames": self.total_frames,
            "usable_frames": self.usable_frames,
            "fps": _sanitize(self.fps),
            "duration_sec": _sanitize(self.duration_sec),
            "detection_coverage": _sanitize(self.detection_coverage),
            "quality_score": _sanitize(self.quality_score),
            "is_reliable": bool(self.is_reliable),
            "is_suitable_for_baseline": bool(self.is_suitable_for_baseline),
            "multi_face_frames": self.multi_face_frames,
            "identity_switch_warnings": self.identity_switch_warnings,
            "avg_face_scale": _sanitize(self.avg_face_scale),
            "avg_luminance": _sanitize(self.avg_luminance),
            "avg_contrast": _sanitize(self.avg_contrast),
            "warnings": list(self.warnings),
        }


def compute_bbox_from_landmarks(
    landmarks_norm: np.ndarray,
    img_w: int,
    img_h: int
) -> Tuple[int, int, int, int]:
    """
    Computes an integer bounding box (x_min, y_min, x_max, y_max)
    from normalized landmark coordinates [N, 2 or 3].
    """
    xs = landmarks_norm[:, 0] * img_w
    ys = landmarks_norm[:, 1] * img_h
    x_min = max(0, int(np.floor(np.min(xs))))
    y_min = max(0, int(np.floor(np.min(ys))))
    x_max = min(img_w, int(np.ceil(np.max(xs))))
    y_max = min(img_h, int(np.ceil(np.max(ys))))
    return (x_min, y_min, x_max, y_max)


def assess_frame_lighting(
    frame_bgr: np.ndarray,
    bbox: Tuple[int, int, int, int]
) -> Tuple[float, float]:
    """
    Measures luminance (mean grayscale) and contrast (std dev of grayscale)
    within the facial bounding box.
    """
    x_min, y_min, x_max, y_max = bbox
    if x_max <= x_min or y_max <= y_min:
        return 0.0, 0.0

    face_crop = frame_bgr[y_min:y_max, x_min:x_max]
    if face_crop.size == 0:
        return 0.0, 0.0

    # Grayscale conversion: Y = 0.299 R + 0.587 G + 0.114 B
    # OpenCV BGR: 0.114*B + 0.587*G + 0.299*R
    b = face_crop[:, :, 0].astype(np.float32)
    g = face_crop[:, :, 1].astype(np.float32)
    r = face_crop[:, :, 2].astype(np.float32)
    gray = 0.114 * b + 0.587 * g + 0.299 * r

    luminance = float(np.mean(gray))
    contrast = float(np.std(gray))
    return luminance, contrast


def calculate_quality_score(
    coverage: float,
    scale_subscore: float,
    lighting_subscore: float,
    stability_subscore: float
) -> float:
    """
    Aggregates subscores into a single quality score between 0.0 and 100.0.
    Coverage is heavily weighted (45%), followed by stability (25%),
    lighting (15%), and resolution/scale (15%).
    """
    if coverage <= 0.0:
        return 0.0

    raw_score = (
        0.45 * (coverage * 100.0) +
        0.25 * stability_subscore +
        0.15 * lighting_subscore +
        0.15 * scale_subscore
    )

    # If coverage is below 30%, tracking is severely compromised: cap the score.
    if coverage < 0.30:
        raw_score = min(raw_score, coverage * 100.0)

    return float(np.clip(round(raw_score, 1), 0.0, 100.0))


def build_quality_report(
    total_frames: int,
    usable_frames: int,
    fps: float,
    luminance_samples: List[float],
    contrast_samples: List[float],
    scale_samples: List[float],
    multi_face_count: int,
    identity_jumps_count: int,
    user_warnings: Optional[List[str]] = None
) -> QualityReport:
    """
    Constructs a comprehensive QualityReport from aggregated frame measurements.
    """
    warnings: List[str] = list(user_warnings or [])

    fps_val = float(fps) if fps > 0.0 else 0.0
    total = max(0, int(total_frames))
    usable = max(0, int(usable_frames))
    duration_sec = (total / fps_val) if (fps_val > 0.0 and total > 0) else 0.0
    coverage = (usable / total) if total > 0 else 0.0

    # Lighting subscore
    if luminance_samples:
        avg_lum = float(np.mean(luminance_samples))
        avg_con = float(np.mean(contrast_samples))
        # Ideal luminance between 80 and 175
        if 80.0 <= avg_lum <= 175.0:
            lum_penalty = 0.0
        elif avg_lum < 80.0:
            lum_penalty = (80.0 - avg_lum) * 1.2
        else:
            lum_penalty = (avg_lum - 175.0) * 1.2

        con_score = np.clip((avg_con / 35.0) * 100.0, 0.0, 100.0)
        lum_score = np.clip(100.0 - lum_penalty, 0.0, 100.0)
        lighting_subscore = 0.6 * lum_score + 0.4 * con_score
    else:
        avg_lum = 0.0
        avg_con = 0.0
        lighting_subscore = 0.0

    # Scale subscore (ideal face area between 5% and 50% of frame)
    if scale_samples:
        avg_scale = float(np.mean(scale_samples))
        if 0.05 <= avg_scale <= 0.55:
            scale_subscore = 100.0
        elif avg_scale < 0.05:
            scale_subscore = max(0.0, (avg_scale / 0.05) * 100.0)
        else:
            scale_subscore = max(0.0, 100.0 - (avg_scale - 0.55) * 200.0)
    else:
        avg_scale = 0.0
        scale_subscore = 0.0

    # Stability subscore (penalize multiple faces and identity jumps)
    stability_subscore = 100.0
    if total > 0:
        multi_face_fraction = multi_face_count / total
        if multi_face_fraction > 0.05:
            penalty = multi_face_fraction * 80.0
            stability_subscore = max(0.0, stability_subscore - penalty)
            warnings.append(
                f"Multiple faces detected in {multi_face_count} frames ({multi_face_fraction*100:.1f}%). "
                "Conservative single-face tracking policy applied."
            )

        if identity_jumps_count > 0:
            jump_penalty = min(50.0, identity_jumps_count * 15.0)
            stability_subscore = max(0.0, stability_subscore - jump_penalty)
            warnings.append(
                f"Potential face tracking identity shift / abrupt position jump detected ({identity_jumps_count} events)."
            )

    if usable == 0:
        warnings.append("No facial landmarks detected across the entire video.")
    elif coverage < 0.50:
        warnings.append(
            f"Low face detection coverage ({coverage * 100:.1f}%). Features may be less reliable."
        )

    if avg_lum > 0.0 and avg_lum < 40.0:
        warnings.append("Video has low lighting (mean face luminance < 40), which may degrade tracking precision.")
    elif avg_lum > 220.0:
        warnings.append("Video has severe overexposure (mean face luminance > 220).")

    quality_score = calculate_quality_score(
        coverage=coverage,
        scale_subscore=scale_subscore,
        lighting_subscore=lighting_subscore,
        stability_subscore=stability_subscore
    )

    is_reliable = (coverage >= 0.50) and (usable >= 15) and (quality_score >= 40.0)
    is_suitable_for_baseline = is_reliable and (quality_score >= 45.0) and (identity_jumps_count <= 2)

    return QualityReport(
        total_frames=total,
        usable_frames=usable,
        fps=fps_val,
        duration_sec=duration_sec,
        detection_coverage=coverage,
        quality_score=quality_score,
        is_reliable=is_reliable,
        is_suitable_for_baseline=is_suitable_for_baseline,
        multi_face_frames=multi_face_count,
        identity_switch_warnings=identity_jumps_count,
        avg_face_scale=avg_scale,
        avg_luminance=avg_lum,
        avg_contrast=avg_con,
        warnings=warnings
    )
