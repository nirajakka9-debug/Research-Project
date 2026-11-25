"""
Voice Pattern Analysis Module.

Provides a modular statistical deviation model to evaluate acoustic feature vectors
against historical user baselines or reference distributions.

NOTE ON CLINICAL BOUNDARIES:
This component calculates a non-clinical *technical voice-pattern deviation score*.
It measures statistical acoustic drift and DOES NOT perform medical or psychological diagnosis.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np

from config import LongitudinalBaselineConfig


@dataclass
class VoicePatternResult:
    technicalDeviationScore: float  # Bounded score 0.0 to 1.0 representing acoustic drift
    featureDeviations: Dict[str, float]  # Individual Z-score deviations per feature
    significantDeviations: List[str]    # Features with |Z| > 1.5


class BaseVoicePatternAnalyzer(ABC):
    """Abstract interface for voice pattern deviation analysis."""

    @abstractmethod
    def analyze(
        self,
        features: Dict[str, float],
        custom_baseline: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> VoicePatternResult:
        pass


class StatisticalVoicePatternAnalyzer(BaseVoicePatternAnalyzer):
    """Statistical Z-score deviation model.

    Evaluates feature vectors against either a historical personal baseline (mean & std_dev per feature)
    or a default reference baseline.
    """

    def __init__(self, config: Optional[LongitudinalBaselineConfig] = None):
        self.config = config or LongitudinalBaselineConfig()

    def analyze(
        self,
        features: Dict[str, float],
        custom_baseline: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> VoicePatternResult:
        """Calculates normalized Z-score feature deviations and composite technical deviation score.

        custom_baseline format example:
        {
            "speakingRateWpm": {"mean": 145.0, "std": 12.0},
            "pitchMeanHz": {"mean": 195.0, "std": 15.0},
            ...
        }
        """
        z_scores: Dict[str, float] = {}
        significant_devs: List[str] = []

        for key, val in features.items():
            if custom_baseline and key in custom_baseline:
                mean = custom_baseline[key].get("mean", self.config.feature_means.get(key, val))
                std = custom_baseline[key].get("std", self.config.feature_std_devs.get(key, 1.0))
            else:
                mean = self.config.feature_means.get(key, val)
                std = self.config.feature_std_devs.get(key, 1.0)

            # Prevent division by zero
            if std <= 1e-6:
                std = 1.0

            z = (val - mean) / std
            z_scores[key] = round(float(z), 2)

            if abs(z) >= 1.5:
                direction = "higher" if z > 0 else "lower"
                significant_devs.append(f"{key} is {direction} than baseline (Z = {z:.2f})")

        # Root-Mean-Square (RMS) Z-score across features
        z_values = list(z_scores.values())
        if len(z_values) > 0:
            rms_z = float(np.sqrt(np.mean(np.square(z_values))))
        else:
            rms_z = 0.0

        # Map RMS Z-score to a bounded 0.0 - 1.0 technical deviation score using sigmoid scaling
        # RMS Z of 0.0 -> score ~0.0; RMS Z of 2.0 -> score ~0.5; RMS Z of 4.0+ -> score ~0.9+
        deviation_score = 1.0 - (1.0 / (1.0 + (rms_z / 2.0) ** 2))

        return VoicePatternResult(
            technicalDeviationScore=round(float(deviation_score), 2),
            featureDeviations=z_scores,
            significantDeviations=significant_devs,
        )
