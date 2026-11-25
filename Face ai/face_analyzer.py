"""
face_analyzer.py
----------------
Core video processing and facial behaviour analysis engine using MediaPipe FaceLandmarker.

Responsibilities:
- MediaPipe model asset verification and reproducible retrieval
- Video input validation (existence, format, size, readability, duration)
- Frame-by-frame landmark extraction with conservative single-face tracking
- Quality assessment and feature extraction execution
- Privacy-compliant numerical results generation (no raw frames persisted)
"""

import os
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

import cv2
import numpy as np

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from quality_assessment import (
    QualityReport,
    compute_bbox_from_landmarks,
    assess_frame_lighting,
    build_quality_report
)
from feature_calculations import (
    ExtractedFeatures,
    extract_all_features,
    sanitize_float
)

OFFICIAL_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/latest/face_landmarker.task"
)
DEFAULT_MODEL_FILENAME = "face_landmarker.task"
SUPPORTED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


class VideoValidationError(Exception):
    """Raised when an input video fails integrity, format, or duration checks."""
    pass


class ModelAssetError(Exception):
    """Raised when the MediaPipe model asset cannot be found or initialized."""
    pass


@dataclass
class VideoMetadata:
    """Metadata describing the validated video file."""
    filepath: str
    filename: str
    filesize_bytes: int
    duration_sec: float
    total_frames: int
    fps: float
    width: int
    height: int


@dataclass
class AnalysisResult:
    """Complete analysis output containing metadata, quality, and features."""
    metadata: VideoMetadata
    quality: QualityReport
    features: ExtractedFeatures
    processing_time_sec: float
    baseline_comparison: Optional[Any] = None
    calibration_status: Optional[Dict[str, Any]] = None
    disclaimer: str = (
        "NON-DIAGNOSTIC RESEARCH MEASUREMENT: These extracted metrics represent "
        "purely geometric and temporal behavioural features from detected facial landmarks. "
        "They do not assess emotion, identify individuals, infer psychological states, "
        "or provide any medical or psychiatric diagnosis."
    )

    def to_dict(self) -> Dict[str, Any]:
        """Converts result to clean JSON-serializable dictionary."""
        res: Dict[str, Any] = {
            "version": "1.1.0",
            "module": "MindTrack Facial Behaviour Wellness Monitoring",
            "disclaimer": self.disclaimer,
            "processing_time_sec": sanitize_float(self.processing_time_sec, 2),
            "video_metadata": {
                "filename": self.metadata.filename,
                "filesize_bytes": self.metadata.filesize_bytes,
                "duration_sec": sanitize_float(self.metadata.duration_sec, 3),
                "total_frames": self.metadata.total_frames,
                "fps": sanitize_float(self.metadata.fps, 2),
                "resolution": f"{self.metadata.width}x{self.metadata.height}"
            },
            "quality": self.quality.to_dict(),
            "features": self.features.to_dict()
        }
        if self.baseline_comparison is not None:
            if hasattr(self.baseline_comparison, "to_dict"):
                res["baseline_comparison"] = self.baseline_comparison.to_dict()
            else:
                res["baseline_comparison"] = self.baseline_comparison
        if self.calibration_status is not None:
            res["calibration_status"] = self.calibration_status
        return res


def ensure_model_asset(
    model_path: Optional[str] = None,
    auto_download: bool = True
) -> str:
    """
    Verifies that the MediaPipe Face Landmarker model asset exists and is valid.
    Downloads from the official Google MediaPipe repository if missing.
    """
    target_path = Path(model_path) if model_path else Path(__file__).resolve().parent / DEFAULT_MODEL_FILENAME

    if target_path.exists():
        size = target_path.stat().st_size
        if size > 1_000_000:  # Expected ~3.7 MB
            return str(target_path)
        else:
            target_path.unlink()  # Remove corrupted partial download

    if not auto_download:
        raise ModelAssetError(
            f"MediaPipe model asset not found at '{target_path}'. "
            f"Please download it from {OFFICIAL_MODEL_URL} or run setup."
        )

    print(f"[*] Downloading MediaPipe Face Landmarker model asset from official source...")
    try:
        def _report(count, block_size, total_size):
            if total_size > 0:
                percent = min(100.0, count * block_size * 100.0 / total_size)
                sys.stdout.write(f"\r    Downloading: {percent:.1f}%")
                sys.stdout.flush()

        urllib.request.urlretrieve(OFFICIAL_MODEL_URL, str(target_path), reporthook=_report)
        print("\n[*] Model asset downloaded and verified successfully.")
    except Exception as e:
        if target_path.exists():
            target_path.unlink()
        raise ModelAssetError(f"Failed to download MediaPipe model asset: {e}")

    if not target_path.exists() or target_path.stat().st_size < 1_000_000:
        raise ModelAssetError("Downloaded model asset appears corrupt or incomplete.")

    return str(target_path)


def validate_video_file(
    video_path: str,
    max_duration_sec: float = 15.0,
    max_filesize_mb: float = 500.0
) -> VideoMetadata:
    """
    Thoroughly validates file existence, extension, size, readability, and duration.
    Raises VideoValidationError on any non-compliance.
    """
    path = Path(video_path)

    # 1. Existence check
    if not path.is_file():
        raise VideoValidationError(f"Video file does not exist or is not a regular file: '{video_path}'")

    # 2. Format extension check
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise VideoValidationError(
            f"Unsupported video file extension '{path.suffix}'. Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # 3. File size check
    filesize_bytes = path.stat().st_size
    if filesize_bytes <= 0:
        raise VideoValidationError(f"Video file is empty (0 bytes): '{video_path}'")

    filesize_mb = filesize_bytes / (1024 * 1024)
    if filesize_mb > max_filesize_mb:
        raise VideoValidationError(
            f"Video file size ({filesize_mb:.1f} MB) exceeds maximum allowed size ({max_filesize_mb:.1f} MB)"
        )

    # 4. Open with OpenCV and verify readability
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise VideoValidationError(f"OpenCV could not open or decode video stream: '{video_path}'")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Test reading the first frame
    ret, test_frame = cap.read()
    cap.release()

    if not ret or test_frame is None or test_frame.size == 0:
        raise VideoValidationError(f"Video stream cannot be read or contains no valid frames: '{video_path}'")

    # Guard against invalid metadata reported by codecs
    if fps <= 0.0 or np.isnan(fps):
        fps = 30.0  # Safe fallback for frame timing if codec omits FPS

    if total_frames <= 0:
        total_frames = 1

    duration_sec = total_frames / fps

    # 5. Maximum duration validation
    if duration_sec > max_duration_sec:
        raise VideoValidationError(
            f"Video duration ({duration_sec:.2f} s) exceeds configured maximum allowed duration "
            f"({max_duration_sec:.2f} s). Configure --max-duration to allow longer clips."
        )

    return VideoMetadata(
        filepath=str(path.resolve()),
        filename=path.name,
        filesize_bytes=filesize_bytes,
        duration_sec=duration_sec,
        total_frames=total_frames,
        fps=fps,
        width=width,
        height=height
    )


def compute_iou(boxA: Tuple[int, int, int, int], boxB: Tuple[int, int, int, int]) -> float:
    """Computes Intersection over Union between two bounding boxes (x1, y1, x2, y2)."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    inter_w = max(0, xB - xA)
    inter_h = max(0, yB - yA)
    inter_area = inter_w * inter_h

    boxA_area = max(0, boxA[2] - boxA[0]) * max(0, boxA[3] - boxA[1])
    boxB_area = max(0, boxB[2] - boxB[0]) * max(0, boxB[3] - boxB[1])

    union_area = float(boxA_area + boxB_area - inter_area)
    if union_area <= 0:
        return 0.0
    return inter_area / union_area


class FaceBehaviorAnalyzer:
    """
    Performs end-to-end facial tracking and feature extraction on video inputs.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = ensure_model_asset(model_path)
        base_options = python.BaseOptions(model_asset_path=self.model_path)
        # Track up to 2 faces so we can detect multi-face ambiguity
        self.options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
            num_faces=2,
            running_mode=vision.RunningMode.VIDEO
        )

    def analyze_video(
        self,
        video_path: str,
        max_duration_sec: float = 15.0,
        progress_callback: Optional[Any] = None
    ) -> AnalysisResult:
        """
        Analyzes the video file and returns extracted features and quality metrics.
        """
        start_time = time.time()
        metadata = validate_video_file(video_path, max_duration_sec=max_duration_sec)

        cap = cv2.VideoCapture(metadata.filepath)
        if not cap.isOpened():
            raise VideoValidationError(f"Failed to reopen video: {video_path}")

        detector = vision.FaceLandmarker.create_from_options(self.options)

        usable_landmarks: List[np.ndarray] = []
        usable_timestamps: List[float] = []

        luminance_samples: List[float] = []
        contrast_samples: List[float] = []
        scale_samples: List[float] = []

        multi_face_count = 0
        identity_jumps_count = 0
        prev_bbox: Optional[Tuple[int, int, int, int]] = None

        frame_idx = 0
        actual_frames_read = 0

        img_w = metadata.width
        img_h = metadata.height
        frame_area = max(1, img_w * img_h)

        try:
            while True:
                ret, frame_bgr = cap.read()
                if not ret or frame_bgr is None:
                    break

                actual_frames_read += 1
                curr_h, curr_w = frame_bgr.shape[:2]
                img_w, img_h = curr_w, curr_h
                frame_area = max(1, img_w * img_h)

                # Monotonically increasing timestamp in milliseconds
                timestamp_ms = int((frame_idx / max(1.0, metadata.fps)) * 1000)
                timestamp_sec = timestamp_ms / 1000.0

                # Convert OpenCV BGR to MediaPipe RGB Image
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

                detection_result = detector.detect_for_video(mp_image, timestamp_ms)
                detected_faces = detection_result.face_landmarks

                if not detected_faces:
                    # No face in frame
                    pass
                else:
                    # Handle single vs multi face
                    if len(detected_faces) > 1:
                        multi_face_count += 1

                    # Conservative single-face selection:
                    # If we had a previous face, select the detected face with highest IoU / closest center
                    selected_face_landmarks = None
                    selected_bbox = None

                    if prev_bbox is None:
                        # Pick the first/largest detected face
                        candidate = detected_faces[0]
                        coords = np.array([[lm.x, lm.y, lm.z] for lm in candidate], dtype=np.float32)
                        bbox = compute_bbox_from_landmarks(coords, img_w, img_h)
                        selected_face_landmarks = coords
                        selected_bbox = bbox
                    else:
                        best_match_idx = 0
                        best_iou = -1.0
                        for idx, candidate in enumerate(detected_faces):
                            coords = np.array([[lm.x, lm.y, lm.z] for lm in candidate], dtype=np.float32)
                            bbox = compute_bbox_from_landmarks(coords, img_w, img_h)
                            iou = compute_iou(prev_bbox, bbox)
                            if iou > best_iou:
                                best_iou = iou
                                best_match_idx = idx

                        candidate = detected_faces[best_match_idx]
                        selected_face_landmarks = np.array([[lm.x, lm.y, lm.z] for lm in candidate], dtype=np.float32)
                        selected_bbox = compute_bbox_from_landmarks(selected_face_landmarks, img_w, img_h)

                        # Check for abrupt identity jump: center distance > 35% of frame diagonal
                        c_prev = ((prev_bbox[0] + prev_bbox[2]) / 2.0, (prev_bbox[1] + prev_bbox[3]) / 2.0)
                        c_curr = ((selected_bbox[0] + selected_bbox[2]) / 2.0, (selected_bbox[1] + selected_bbox[3]) / 2.0)
                        dist_jump = np.sqrt((c_curr[0] - c_prev[0])**2 + (c_curr[1] - c_prev[1])**2)
                        frame_diag = np.sqrt(img_w**2 + img_h**2)

                        if (dist_jump / frame_diag) > 0.35 and best_iou < 0.1:
                            identity_jumps_count += 1

                    prev_bbox = selected_bbox

                    # Collect metrics
                    usable_landmarks.append(selected_face_landmarks)
                    usable_timestamps.append(timestamp_sec)

                    # Lighting and scale
                    lum, con = assess_frame_lighting(frame_bgr, selected_bbox)
                    luminance_samples.append(lum)
                    contrast_samples.append(con)

                    bbox_w = max(0, selected_bbox[2] - selected_bbox[0])
                    bbox_h = max(0, selected_bbox[3] - selected_bbox[1])
                    scale_samples.append((bbox_w * bbox_h) / frame_area)

                frame_idx += 1
                if progress_callback:
                    progress_callback(frame_idx, metadata.total_frames)

        finally:
            cap.release()
            detector.close()

        total_frames = max(actual_frames_read, metadata.total_frames)
        usable_frames = len(usable_landmarks)
        duration_sec = total_frames / metadata.fps if metadata.fps > 0 else 0.0
        coverage = (usable_frames / total_frames) if total_frames > 0 else 0.0

        # Quality assessment
        quality_report = build_quality_report(
            total_frames=total_frames,
            usable_frames=usable_frames,
            fps=metadata.fps,
            luminance_samples=luminance_samples,
            contrast_samples=contrast_samples,
            scale_samples=scale_samples,
            multi_face_count=multi_face_count,
            identity_jumps_count=identity_jumps_count
        )

        # Feature extraction
        usable_duration_sec = usable_frames / metadata.fps if metadata.fps > 0 else 0.0
        features = extract_all_features(
            landmarks_per_frame=usable_landmarks,
            timestamps_sec=usable_timestamps,
            img_w=img_w,
            img_h=img_h,
            usable_duration_sec=usable_duration_sec,
            coverage=coverage
        )

        processing_time = time.time() - start_time

        return AnalysisResult(
            metadata=metadata,
            quality=quality_report,
            features=features,
            processing_time_sec=processing_time
        )
