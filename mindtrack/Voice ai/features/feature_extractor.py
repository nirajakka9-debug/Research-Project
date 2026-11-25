"""
Feature Extractor Master Module.

Coordinates sub-analyzers (pitch, energy, pauses, speaking rate, quality)
and formats structured acoustic feature dictionaries and numerical feature vectors.
"""

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional
import numpy as np

from config import SystemConfig
from preprocessing.audio_loader import AudioMetaData, ProcessedAudio
from vad.speech_detector import VADResult

from .energy import EnergyAnalyzer, EnergyMetrics
from .pauses import PauseAnalyzer, PauseMetrics
from .pitch import PitchEstimator, PitchMetrics
from .quality import QualityMetrics, QualityScorer
from .speaking_rate import SpeakingRateEstimator, SpeakingRateMetrics


@dataclass
class FeatureExtractionResult:
    features: Dict[str, float]
    feature_vector: List[float]
    feature_names: List[str]
    qualityMetrics: QualityMetrics
    pitchMetrics: PitchMetrics
    energyMetrics: EnergyMetrics
    pauseMetrics: PauseMetrics
    speakingRateMetrics: SpeakingRateMetrics


class FeatureExtractor:
    """Master orchestrator for all acoustic feature extraction algorithms."""

    def __init__(self, config: Optional[SystemConfig] = None):
        self.config = config or SystemConfig()
        self.pitch_estimator = PitchEstimator(self.config.pitch)
        self.energy_analyzer = EnergyAnalyzer()
        self.pause_analyzer = PauseAnalyzer()
        self.speaking_rate_estimator = SpeakingRateEstimator(self.config.speaking_rate)
        self.quality_scorer = QualityScorer(self.config.quality)

    def extract(self, audio: ProcessedAudio, vad_result: VADResult) -> FeatureExtractionResult:
        """Extracts complete set of acoustic features from preprocessed audio and VAD result."""

        # 1. Pitch estimation
        pitch_metrics = self.pitch_estimator.estimate(audio.samples, audio.sample_rate, vad_result)

        # 2. Energy analysis
        energy_metrics = self.energy_analyzer.process(audio.samples, audio.sample_rate, vad_result)

        # 3. Pause analysis
        pause_metrics = self.pause_analyzer.process(vad_result)

        # 4. Speaking rate estimation
        rate_metrics = self.speaking_rate_estimator.estimate(audio.samples, audio.sample_rate, vad_result)

        # 5. Quality scoring
        quality_metrics = self.quality_scorer.score(
            metadata=audio.metadata,
            vad_result=vad_result,
            voiced_ratio=pitch_metrics.voicedRatio,
        )

        # Build primary features dictionary according to required schema
        features_dict: Dict[str, float] = {
            "speakingRateWpm": float(round(rate_metrics.speakingRateWpm, 1)),
            "totalPauseCount": float(int(pause_metrics.totalPauseCount)),
            "meanPauseDurationMs": float(round(pause_metrics.meanPauseDurationMs, 1)),
            "longestPauseDurationMs": float(round(pause_metrics.longestPauseDurationMs, 1)),
            "speechRatio": float(round(pause_metrics.speechRatio, 3)),
            "speechDurationSec": float(round(pause_metrics.speechDurationSec, 3)),
            "silenceDurationSec": float(round(pause_metrics.silenceDurationSec, 3)),
            "pitchMeanHz": float(round(pitch_metrics.pitchMeanHz, 2)),
            "pitchStdDevHz": float(round(pitch_metrics.pitchStdDevHz, 2)),
            "pitchRangeHz": float(round(pitch_metrics.pitchRangeHz, 2)),
            "energyMeanRms": float(round(energy_metrics.energyMeanRms, 5)),
            "energyStdDev": float(round(energy_metrics.energyStdDev, 5)),
        }

        # Validate that no feature contains NaN or Infinity
        for k, v in features_dict.items():
            if np.isnan(v) or np.isinf(v):
                raise ValueError(f"Feature '{k}' computed an invalid numerical value: {v}")

        # Ordered vector keys matching dictionary
        feature_names = list(features_dict.keys())
        feature_vector = [features_dict[name] for name in feature_names]

        return FeatureExtractionResult(
            features=features_dict,
            feature_vector=feature_vector,
            feature_names=feature_names,
            qualityMetrics=quality_metrics,
            pitchMetrics=pitch_metrics,
            energyMetrics=energy_metrics,
            pauseMetrics=pause_metrics,
            speakingRateMetrics=rate_metrics,
        )
