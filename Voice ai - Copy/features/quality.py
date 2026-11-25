"""
Audio Quality Scoring Module.

Calculates a transparent composite quality score between 0.0 and 1.0 based on
measurable physical acoustic properties (clipping, speech ratio, SNR, voiced content, signal level).
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np

from config import QualityConfig
from preprocessing.audio_loader import AudioMetaData
from vad.speech_detector import VADResult


@dataclass
class QualityMetrics:
    qualityScore: float
    clippingPenalty: float
    speechRatioScore: float
    voicedContentScore: float
    signalLevelScore: float


class QualityScorer:
    """Computes a transparent composite quality score for input speech recordings."""

    def __init__(self, config: Optional[QualityConfig] = None):
        self.config = config or QualityConfig()

    def score(
        self,
        metadata: AudioMetaData,
        vad_result: VADResult,
        voiced_ratio: float,
    ) -> QualityMetrics:
        """Calculates composite quality score (0.0 to 1.0)."""
        # 1. Clipping penalty (0.0 clipping -> 1.0 score; >2% clipping -> severe penalty)
        clip_ratio = metadata.clippingRatio
        if clip_ratio <= 0.001:
            clipping_score = 1.0
        elif clip_ratio <= self.config.max_clipping_ratio:
            clipping_score = 1.0 - (clip_ratio / self.config.max_clipping_ratio) * 0.5
        else:
            clipping_score = max(0.0, 0.5 - (clip_ratio - self.config.max_clipping_ratio) * 5.0)

        # 2. Speech ratio score (penalize 0 speech or 100% continuous un-paused noise)
        sr = vad_result.speechRatio
        min_opt, max_opt = self.config.optimal_speech_ratio_range
        if min_opt <= sr <= max_opt:
            speech_score = 1.0
        elif sr < min_opt:
            speech_score = max(0.0, sr / min_opt)
        else:
            speech_score = max(0.2, 1.0 - (sr - max_opt) / (1.0 - max_opt))

        # 3. Voiced content score (ratio of voiced frames in speech segments)
        voiced_score = min(1.0, max(0.0, voiced_ratio))

        # 4. Signal level / RMS score
        rms = metadata.signalLevelRms
        if 0.01 <= rms <= 0.5:
            signal_score = 1.0
        elif rms < 0.01:
            signal_score = max(0.1, rms / 0.01)
        else:
            signal_score = max(0.5, 1.0 - (rms - 0.5))

        # Composite weighted score
        composite = (
            0.30 * clipping_score
            + 0.30 * speech_score
            + 0.20 * voiced_score
            + 0.20 * signal_score
        )

        final_score = float(np.clip(composite, 0.0, 1.0))

        return QualityMetrics(
            qualityScore=round(final_score, 2),
            clippingPenalty=round(1.0 - clipping_score, 3),
            speechRatioScore=round(speech_score, 2),
            voicedContentScore=round(voiced_score, 2),
            signalLevelScore=round(signal_score, 2),
        )
