"""
Longitudinal Voice Tracking Module.

Provides personal historical baseline accumulation, statistical Z-score
deviation calculation, and non-clinical technical voice-pattern drift analysis.

CLINICAL & ETHICAL BOUNDARIES:
- This module DOES NOT diagnose, screen, or predict depression, anxiety, PTSD,
  stress disorders, or any other psychiatric/medical condition.
- Any deviation detected is strictly reported as a "technical voice-pattern deviation"
  or "deviation from personal baseline".
- The initial baseline problem is guarded: Z-scores are suppressed or flagged as
  unestablished until a sufficient number of historical sessions are accumulated.
- Zero-variance conditions are guarded with minimum variance floors to prevent division-by-zero.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from typing import Any, Dict, List, Optional
import numpy as np

from config import LongitudinalBaselineConfig


@dataclass
class LongitudinalDeviationResult:
    """Structured result of comparing a single observation against a personal historical baseline."""
    is_baseline_established: bool
    observation_count: int
    min_observations_required: int
    technicalDeviationScore: Optional[float]  # Bounded 0.0 to 1.0 (None if baseline unestablished)
    featureDeviations: Dict[str, Optional[float]]  # Per-feature Z-scores: (current - mean) / std
    baselineMeans: Dict[str, float]
    baselineStdDevs: Dict[str, float]
    significantDeviations: List[str]  # Human-readable deviation messages (|Z| >= threshold)
    status: str  # "baseline_established" | "insufficient_history"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PersonalVoiceBaseline:
    """Manages longitudinal observation history and calculates personal baseline statistics for an individual."""

    def __init__(
        self,
        user_id: str = "default_user",
        min_observations: int = 3,
        min_std_floor: float = 1e-3,
    ):
        self.user_id = user_id
        self.min_observations = min_observations
        self.min_std_floor = min_std_floor
        self.history: List[Dict[str, Any]] = []

    @property
    def observation_count(self) -> int:
        return len(self.history)

    @property
    def is_established(self) -> bool:
        """Baseline is established only after collecting at least min_observations."""
        return self.observation_count >= self.min_observations

    def add_observation(self, features: Dict[str, float], timestamp: Optional[str] = None) -> None:
        """Appends a new observation to history.
        
        IMPORTANT: This must be called AFTER evaluating the observation against the prior baseline,
        to ensure the current observation does not evaluate against itself.
        """
        record = {
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "features": {k: float(v) for k, v in features.items()},
        }
        self.history.append(record)

    def get_baseline_stats(self) -> Dict[str, Dict[str, float]]:
        """Calculates per-feature mean, standard deviation, min, and max across historical observations."""
        if not self.history:
            return {}

        feature_keys = list(self.history[0]["features"].keys())
        stats: Dict[str, Dict[str, float]] = {}

        for key in feature_keys:
            values = [h["features"][key] for h in self.history if key in h["features"]]
            if not values:
                continue

            arr = np.array(values, dtype=np.float64)
            mean_val = float(np.mean(arr))
            # Use sample standard deviation (ddof=1) if N >= 2, else 0.0
            std_val = float(np.std(arr, ddof=1)) if len(arr) >= 2 else 0.0

            stats[key] = {
                "mean": round(mean_val, 4),
                "std": round(std_val, 4),
                "min": round(float(np.min(arr)), 4),
                "max": round(float(np.max(arr)), 4),
                "count": len(arr),
            }

        return stats

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "min_observations": self.min_observations,
            "min_std_floor": self.min_std_floor,
            "observation_count": self.observation_count,
            "is_established": self.is_established,
            "stats": self.get_baseline_stats(),
            "history": self.history,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save_to_file(self, filepath: str) -> None:
        """Saves personal baseline to a local JSON file."""
        dirname = os.path.dirname(os.path.abspath(filepath))
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersonalVoiceBaseline":
        baseline = cls(
            user_id=data.get("user_id", "default_user"),
            min_observations=data.get("min_observations", 3),
            min_std_floor=data.get("min_std_floor", 1e-3),
        )
        baseline.history = data.get("history", [])
        return baseline

    @classmethod
    def load_from_file(cls, filepath: str) -> "PersonalVoiceBaseline":
        """Loads personal baseline from a local JSON file."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Baseline file not found: '{filepath}'")
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


class LongitudinalTracker:
    """Compares current acoustic observations against personal historical baselines.
    
    Adheres strictly to technical, non-clinical deviation metrics.
    """

    def __init__(self, config: Optional[LongitudinalBaselineConfig] = None):
        self.config = config or LongitudinalBaselineConfig()

    def evaluate_observation(
        self,
        current_features: Dict[str, float],
        baseline: PersonalVoiceBaseline,
    ) -> LongitudinalDeviationResult:
        """Compares current observation against personal historical baseline.
        
        CRITICAL ARCHITECTURAL GUARANTEE:
        This evaluation operates strictly on baseline.history as it existed BEFORE this observation.
        The current observation must NOT be added to baseline before calling this method.
        """
        obs_count = baseline.observation_count
        min_required = baseline.min_observations

        # Guard: Initial-baseline problem
        if not baseline.is_established:
            # Baseline is not yet established. Cannot compute meaningful personal Z-scores.
            stats = baseline.get_baseline_stats()
            means = {k: stats[k]["mean"] for k in stats} if stats else {}
            stds = {k: stats[k]["std"] for k in stats} if stats else {}

            return LongitudinalDeviationResult(
                is_baseline_established=False,
                observation_count=obs_count,
                min_observations_required=min_required,
                technicalDeviationScore=None,
                featureDeviations={k: None for k in current_features},
                baselineMeans=means,
                baselineStdDevs=stds,
                significantDeviations=[],
                status=f"insufficient_history: {obs_count}/{min_required} sessions completed for personal baseline",
            )

        # Baseline is established: Calculate feature-by-feature deviation
        stats = baseline.get_baseline_stats()
        z_scores: Dict[str, Optional[float]] = {}
        means: Dict[str, float] = {}
        stds: Dict[str, float] = {}
        significant_devs: List[str] = []
        valid_z_values: List[float] = []

        for key, val in current_features.items():
            if key not in stats:
                z_scores[key] = None
                continue

            mean = stats[key]["mean"]
            raw_std = stats[key]["std"]
            # Guard against zero variance across identical historical runs using calibrated physical minimum floor
            min_std = self.config.feature_min_stds.get(key, baseline.min_std_floor)
            std = max(raw_std, min_std)

            means[key] = mean
            stds[key] = std

            z = (val - mean) / std
            z_scores[key] = round(float(z), 2)
            valid_z_values.append(float(z))

            if abs(z) >= self.config.significance_z_threshold:
                direction = "higher" if z > 0 else "lower"
                significant_devs.append(
                    f"{key} is {direction} than personal baseline (Z = {z:+.2f}, current = {val:.2f}, baseline = {mean:.2f} ± {std:.2f})"
                )

        # Compute bounded composite technical voice-pattern deviation score
        if valid_z_values:
            rms_z = float(np.sqrt(np.mean(np.square(valid_z_values))))
            # Non-linear sigmoid-style scaling: RMS Z of 0 -> 0.0, RMS Z of 2.0 -> 0.5, RMS Z of 4.0 -> 0.8
            dev_score = 1.0 - (1.0 / (1.0 + (rms_z / 2.0) ** 2))
            deviation_score = round(float(dev_score), 2)
        else:
            deviation_score = 0.0

        return LongitudinalDeviationResult(
            is_baseline_established=True,
            observation_count=obs_count,
            min_observations_required=min_required,
            technicalDeviationScore=deviation_score,
            featureDeviations=z_scores,
            baselineMeans=means,
            baselineStdDevs=stds,
            significantDeviations=significant_devs,
            status="baseline_established",
        )

    def evaluate_and_update(
        self,
        current_features: Dict[str, float],
        baseline: PersonalVoiceBaseline,
        timestamp: Optional[str] = None,
    ) -> LongitudinalDeviationResult:
        """Evaluates current observation against prior baseline first, then updates baseline."""
        # 1. Evaluate first (prior history only)
        result = self.evaluate_observation(current_features, baseline)
        # 2. Add current observation to history
        baseline.add_observation(current_features, timestamp=timestamp)
        return result
