"""
baseline_manager.py
-------------------
Manages longitudinal personal baseline profiles for the MindTrack facial behaviour research project.

Key Responsibilities:
- Safe, validated local JSON persistence of per-user baseline profiles in 'profiles/'
- Multi-session calibration accumulation (default: at least 5 check-ins required)
- Strict mathematical tracking: sample count, mean, standard deviation per feature
- Missing feature handling: never treats missing features as zero
- Zero / near-zero baseline variance handling
- Statistical comparison for assessment mode: absolute difference, relative change %, standardized z-score
- Careful, research-oriented, non-diagnostic interpretation wording
"""

import json
import math
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from quality_assessment import QualityReport
from feature_calculations import ExtractedFeatures, sanitize_float

DEFAULT_PROFILES_DIR = "profiles"
DEFAULT_MIN_CALIBRATION_CHECKINS = 5
SAFE_USER_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

NON_DIAGNOSTIC_LIMITATION = (
    "Stress inference is not validated. This check-in provides facial-behaviour "
    "measurements and personal-baseline comparisons only."
)

FEATURE_KEYS = [
    "facialMovementVelocity",
    "eyeBlinkRatePm",
    "headPoseJitterStd",
    "smileIntensityProxy",
    "browFurrowProxy"
]

FEATURE_UNITS = {
    "facialMovementVelocity": "face-units / sec",
    "eyeBlinkRatePm": "blinks / min",
    "headPoseJitterStd": "degrees",
    "smileIntensityProxy": "mouth-to-interocular ratio",
    "browFurrowProxy": "brow-to-eye ratio"
}


class BaselineError(Exception):
    """Base exception for baseline profile errors."""
    pass


class InvalidUserIdError(BaselineError):
    """Raised when a user ID contains invalid characters or path traversal sequences."""
    pass


class ProfileNotFoundError(BaselineError):
    """Raised when an assessment is attempted for a user without an existing baseline profile."""
    pass


class IncompatibleProfileError(BaselineError):
    """Raised when a profile file is corrupt or lacks required schema fields."""
    pass


def validate_user_id(user_id: str) -> str:
    """
    Validates and sanitizes a user identifier to prevent path traversal or unsafe file access.
    Only allows alphanumeric characters, underscores, and hyphens (1-64 characters).
    """
    if not user_id or not isinstance(user_id, str):
        raise InvalidUserIdError("User ID must be a non-empty string.")
    
    clean_id = user_id.strip()
    if not SAFE_USER_ID_REGEX.match(clean_id):
        raise InvalidUserIdError(
            f"Invalid user ID '{user_id}'. User IDs must only contain letters, numbers, "
            "underscores, or hyphens (1-64 characters) with no path traversal characters."
        )
    return clean_id


@dataclass
class FeatureStatistic:
    """Statistical summary for a single facial feature across calibration check-ins."""
    count: int = 0
    mean: Optional[float] = None
    std: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "mean": sanitize_float(self.mean, 4),
            "std": sanitize_float(self.std, 4),
            "min": sanitize_float(self.min, 4),
            "max": sanitize_float(self.max, 4)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeatureStatistic":
        return cls(
            count=int(data.get("count", 0)),
            mean=data.get("mean"),
            std=data.get("std"),
            min=data.get("min"),
            max=data.get("max")
        )


@dataclass
class UserBaselineProfile:
    """Per-user longitudinal baseline profile stored as versioned JSON."""
    version: str
    user_id: str
    created_at: str
    updated_at: str
    min_calibration_checkins: int
    total_checkins_recorded: int
    is_calibrated: bool
    feature_stats: Dict[str, FeatureStatistic] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "min_calibration_checkins": self.min_calibration_checkins,
            "total_checkins_recorded": self.total_checkins_recorded,
            "is_calibrated": self.is_calibrated,
            "feature_stats": {k: v.to_dict() for k, v in self.feature_stats.items()},
            "history": list(self.history)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserBaselineProfile":
        if "user_id" not in data or "feature_stats" not in data:
            raise IncompatibleProfileError("Profile JSON is missing required baseline schema fields.")
        
        stats = {
            k: FeatureStatistic.from_dict(v)
            for k, v in data.get("feature_stats", {}).items()
        }
        return cls(
            version=data.get("version", "1.0.0"),
            user_id=data["user_id"],
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            min_calibration_checkins=int(data.get("min_calibration_checkins", DEFAULT_MIN_CALIBRATION_CHECKINS)),
            total_checkins_recorded=int(data.get("total_checkins_recorded", 0)),
            is_calibrated=bool(data.get("is_calibrated", False)),
            feature_stats=stats,
            history=data.get("history", [])
        )


@dataclass
class FeatureComparison:
    """Comparison between a single observed feature and its personal baseline."""
    feature_name: str
    current_value: Optional[float]
    baseline_mean: Optional[float]
    baseline_std: Optional[float]
    baseline_count: int
    units: str
    absolute_difference: Optional[float] = None
    relative_change_pct: Optional[float] = None
    standardized_z: Optional[float] = None
    interpretation: str = "Unavailable"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "current_value": sanitize_float(self.current_value, 4),
            "baseline_mean": sanitize_float(self.baseline_mean, 4),
            "baseline_std": sanitize_float(self.baseline_std, 4),
            "baseline_count": self.baseline_count,
            "units": self.units,
            "absolute_difference": sanitize_float(self.absolute_difference, 4),
            "relative_change_pct": sanitize_float(self.relative_change_pct, 2),
            "standardized_z": sanitize_float(self.standardized_z, 2),
            "interpretation": self.interpretation
        }


@dataclass
class BaselineComparisonReport:
    """Complete personal-baseline comparison results for assessment mode."""
    user_id: str
    is_calibrated: bool
    total_calibration_checkins: int
    min_checkins_required: int
    comparisons: Dict[str, FeatureComparison] = field(default_factory=dict)
    summary_observations: List[str] = field(default_factory=list)
    limitations: str = NON_DIAGNOSTIC_LIMITATION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "is_calibrated": self.is_calibrated,
            "total_calibration_checkins": self.total_calibration_checkins,
            "min_checkins_required": self.min_checkins_required,
            "comparisons": {k: v.to_dict() for k, v in self.comparisons.items()},
            "summary_observations": list(self.summary_observations),
            "limitations": self.limitations
        }


class BaselineManager:
    """
    Handles secure loading, updating, persistence, and comparisons
    for user baseline profiles in a designated directory.
    """

    def __init__(
        self,
        profiles_dir: str = DEFAULT_PROFILES_DIR,
        min_calibration_checkins: int = DEFAULT_MIN_CALIBRATION_CHECKINS
    ):
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.min_calibration_checkins = max(1, int(min_calibration_checkins))

    def get_profile_path(self, user_id: str) -> Path:
        """Computes the safe filesystem path for a user's profile."""
        clean_id = validate_user_id(user_id)
        return self.profiles_dir / f"{clean_id}.json"

    def profile_exists(self, user_id: str) -> bool:
        """Checks if a baseline profile exists for the given user ID."""
        try:
            return self.get_profile_path(user_id).is_file()
        except InvalidUserIdError:
            return False

    def load_profile(self, user_id: str) -> UserBaselineProfile:
        """Loads and deserializes an existing user baseline profile."""
        path = self.get_profile_path(user_id)
        if not path.is_file():
            raise ProfileNotFoundError(f"Baseline profile for user '{user_id}' does not exist at '{path}'.")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return UserBaselineProfile.from_dict(data)
        except json.JSONDecodeError as e:
            raise IncompatibleProfileError(f"Corrupt profile file for user '{user_id}': {e}")
        except Exception as e:
            raise IncompatibleProfileError(f"Failed to load profile for user '{user_id}': {e}")

    def save_profile(self, profile: UserBaselineProfile) -> Path:
        """Persists the user baseline profile to disk as formatted JSON."""
        path = self.get_profile_path(profile.user_id)
        data = profile.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return path

    def create_or_load_profile(self, user_id: str) -> UserBaselineProfile:
        """Loads existing profile or initializes a fresh profile structure."""
        if self.profile_exists(user_id):
            return self.load_profile(user_id)

        clean_id = validate_user_id(user_id)
        now_iso = datetime.now(timezone.utc).isoformat()
        initial_stats = {key: FeatureStatistic() for key in FEATURE_KEYS}

        profile = UserBaselineProfile(
            version="1.0.0",
            user_id=clean_id,
            created_at=now_iso,
            updated_at=now_iso,
            min_calibration_checkins=self.min_calibration_checkins,
            total_checkins_recorded=0,
            is_calibrated=False,
            feature_stats=initial_stats,
            history=[]
        )
        return profile

    def add_calibration_checkin(
        self,
        user_id: str,
        features: ExtractedFeatures,
        quality: QualityReport,
        video_filename: str
    ) -> Tuple[UserBaselineProfile, bool]:
        """
        Adds a new valid check-in observation to the user's baseline profile.
        Strictly prevents missing features from being recorded as zero.
        Recomputes sample count, mean, standard deviation, min, max.
        Returns: (updated_profile, was_added: bool)
        """
        profile = self.create_or_load_profile(user_id)

        # Check if the check-in meets suitability criteria
        is_suitable = quality.quality_score >= 40.0 and quality.detection_coverage >= 0.50 and quality.usable_frames >= 15
        if not is_suitable:
            raise BaselineError(
                f"Recording quality is insufficient for baseline calibration "
                f"(quality score: {quality.quality_score:.1f}, coverage: {quality.detection_coverage*100:.1f}%). "
                "Calibration requires reliable facial tracking to avoid corrupting the baseline."
            )

        f_dict = features.to_dict()
        now_iso = datetime.now(timezone.utc).isoformat()

        # Record raw observation in history
        checkin_record = {
            "timestamp": now_iso,
            "filename": video_filename,
            "quality_score": quality.quality_score,
            "coverage": quality.detection_coverage,
            "usable_frames": quality.usable_frames,
            "features": {
                k: f_dict.get(k) for k in FEATURE_KEYS
            }
        }
        profile.history.append(checkin_record)
        profile.total_checkins_recorded = len(profile.history)
        profile.updated_at = now_iso

        # Update per-feature statistics across all historical observations
        # NEVER treat missing features (None) as zero!
        for key in FEATURE_KEYS:
            valid_values = [
                h["features"][key]
                for h in profile.history
                if h["features"].get(key) is not None
            ]
            count = len(valid_values)
            if count == 0:
                profile.feature_stats[key] = FeatureStatistic(count=0)
            elif count == 1:
                val = float(valid_values[0])
                profile.feature_stats[key] = FeatureStatistic(
                    count=1,
                    mean=val,
                    std=0.0,
                    min=val,
                    max=val
                )
            else:
                mean_val = float(sum(valid_values) / count)
                # Sample variance / std dev (Bessel's correction N-1)
                variance = sum((v - mean_val) ** 2 for v in valid_values) / (count - 1)
                std_val = float(math.sqrt(max(0.0, variance)))
                profile.feature_stats[key] = FeatureStatistic(
                    count=count,
                    mean=mean_val,
                    std=std_val,
                    min=float(min(valid_values)),
                    max=float(max(valid_values))
                )

        profile.is_calibrated = profile.total_checkins_recorded >= profile.min_calibration_checkins
        self.save_profile(profile)
        return profile, True

    def compare_checkin_with_baseline(
        self,
        profile: UserBaselineProfile,
        features: ExtractedFeatures,
        quality: QualityReport
    ) -> BaselineComparisonReport:
        """
        Compares a check-in against an established or in-progress baseline profile.
        Calculates absolute differences, relative changes (%), and standardized deviations (z).
        Generates research-oriented, non-diagnostic longitudinal interpretations.
        """
        f_dict = features.to_dict()
        comparisons: Dict[str, FeatureComparison] = {}
        observations: List[str] = []

        is_calibrated = profile.is_calibrated
        total_checkins = profile.total_checkins_recorded

        if not quality.is_reliable:
            observations.append(
                "Recording quality limits interpretation: low face detection coverage or lighting instability detected."
            )

        if not is_calibrated:
            observations.append(
                f"Preliminary personal baseline: based on {total_checkins} of "
                f"{profile.min_calibration_checkins} required calibration check-ins."
            )

        for key in FEATURE_KEYS:
            curr_val = f_dict.get(key)
            stat = profile.feature_stats.get(key, FeatureStatistic())
            units = FEATURE_UNITS.get(key, "")

            # If current feature was not detected / unavailable
            if curr_val is None:
                comparisons[key] = FeatureComparison(
                    feature_name=key,
                    current_value=None,
                    baseline_mean=stat.mean,
                    baseline_std=stat.std,
                    baseline_count=stat.count,
                    units=units,
                    interpretation="Feature unavailable in this recording"
                )
                continue

            # If baseline has insufficient observations for this specific feature
            if stat.count < 1 or stat.mean is None:
                comparisons[key] = FeatureComparison(
                    feature_name=key,
                    current_value=curr_val,
                    baseline_mean=None,
                    baseline_std=None,
                    baseline_count=stat.count,
                    units=units,
                    interpretation="Insufficient baseline data"
                )
                continue

            # Absolute difference
            abs_diff = curr_val - stat.mean

            # Relative change where mathematically meaningful
            # Guard against division by near-zero baseline mean
            if abs(stat.mean) > 1e-4:
                rel_change = (abs_diff / stat.mean) * 100.0
            else:
                rel_change = None

            # Standardized z-score
            # Guard against zero or near-zero baseline variance
            std_val = stat.std if stat.std is not None else 0.0
            if stat.count >= 2 and std_val > 1e-4:
                z_score = abs_diff / std_val
            else:
                z_score = None

            # Non-diagnostic interpretation
            if z_score is not None:
                if abs(z_score) <= 1.2:
                    interp = "Within the observed personal baseline"
                elif z_score > 1.2:
                    interp = "Higher than the observed personal baseline"
                    observations.append(
                        f"{key} is higher than observed baseline (+{abs_diff:.3f} {units}, z = +{z_score:.2f})."
                    )
                else:
                    interp = "Lower than the observed personal baseline"
                    observations.append(
                        f"{key} is lower than observed baseline ({abs_diff:.3f} {units}, z = {z_score:.2f})."
                    )
            elif stat.count >= 2 and std_val <= 1e-4:
                # Near-zero variance
                if abs(abs_diff) < 1e-4:
                    interp = "Within the observed personal baseline (zero baseline variance)"
                elif abs_diff > 0:
                    interp = "Higher than the observed personal baseline (zero baseline variance)"
                    observations.append(f"{key} is higher than invariant baseline (+{abs_diff:.3f} {units}).")
                else:
                    interp = "Lower than the observed personal baseline (zero baseline variance)"
                    observations.append(f"{key} is lower than invariant baseline ({abs_diff:.3f} {units}).")
            else:
                interp = "Single baseline observation (variance not yet established)"

            comparisons[key] = FeatureComparison(
                feature_name=key,
                current_value=curr_val,
                baseline_mean=stat.mean,
                baseline_std=stat.std,
                baseline_count=stat.count,
                units=units,
                absolute_difference=abs_diff,
                relative_change_pct=rel_change,
                standardized_z=z_score,
                interpretation=interp
            )

        if not observations:
            observations.append(
                "All available facial-behaviour measurements are within the observed personal baseline."
            )

        return BaselineComparisonReport(
            user_id=profile.user_id,
            is_calibrated=is_calibrated,
            total_calibration_checkins=total_checkins,
            min_checkins_required=profile.min_calibration_checkins,
            comparisons=comparisons,
            summary_observations=observations,
            limitations=NON_DIAGNOSTIC_LIMITATION
        )
