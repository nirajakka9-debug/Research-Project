"""
Pause Analysis Module.

Extracts meaningful pause metrics from VAD segmentation results.
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np

from vad.speech_detector import VADResult


@dataclass
class PauseMetrics:
    totalPauseCount: int
    meanPauseDurationMs: float
    longestPauseDurationMs: float
    speechRatio: float
    speechDurationSec: float
    silenceDurationSec: float


class PauseAnalyzer:
    """Extracts structured pause and silence metrics from Voice Activity Detector results."""

    def process(self, vad_result: VADResult) -> PauseMetrics:
        """Translates VAD pause segments into standardized pause metrics."""
        return PauseMetrics(
            totalPauseCount=vad_result.totalPauseCount,
            meanPauseDurationMs=vad_result.meanPauseDurationMs,
            longestPauseDurationMs=vad_result.longestPauseDurationMs,
            speechRatio=vad_result.speechRatio,
            speechDurationSec=vad_result.speechDurationSec,
            silenceDurationSec=vad_result.silenceDurationSec,
        )
