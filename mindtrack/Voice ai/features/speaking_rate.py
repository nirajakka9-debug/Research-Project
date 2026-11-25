"""
Speaking Rate Estimation Module.

Computes estimated Speaking Rate in Words Per Minute (WPM) using an acoustic syllabic envelope
intensity peak detection method across active speech segments.

NOTE ON METHODOLOGY:
This component uses a transparent signal-processing approximation (syllables detected via intensity nuclei peaks
in speech segments) rather than full Automatic Speech Recognition (ASR). It is designed to be fully modular
and can be swapped with an ASR-based word transcription engine in future upgrades.
"""

from dataclasses import dataclass
from typing import List, Optional
import numpy as np
import scipy.signal as signal

from config import SpeakingRateConfig
from vad.speech_detector import VADResult


@dataclass
class SpeakingRateMetrics:
    speakingRateWpm: float
    estimatedSyllableCount: int
    syllablesPerSecond: float
    methodology: str = "acoustic_syllabic_envelope_estimate"


class SpeakingRateEstimator:
    """Estimates speaking rate in WPM via energy envelope syllable nucleus detection."""

    def __init__(self, config: Optional[SpeakingRateConfig] = None):
        self.config = config or SpeakingRateConfig()

    def estimate(self, samples: np.ndarray, sample_rate: int, vad_result: VADResult) -> SpeakingRateMetrics:
        """Estimates WPM speaking rate from active speech segments."""
        if vad_result.speechDurationSec <= 0.1:
            return SpeakingRateMetrics(speakingRateWpm=0.0, estimatedSyllableCount=0, syllablesPerSecond=0.0)

        total_syllables = 0

        # Lowpass filter design for intensity envelope extraction (~10 Hz cut-off)
        b, a = signal.butter(2, 10.0 / (sample_rate / 2.0), btype="low")

        min_distance_samples = int((self.config.min_syllable_distance_ms / 1000.0) * sample_rate)

        for seg in vad_result.speech_segments:
            start_sample = int(seg.start_sec * sample_rate)
            end_sample = min(int(seg.end_sec * sample_rate), len(samples))
            seg_samples = samples[start_sample:end_sample]

            if len(seg_samples) < min_distance_samples:
                continue

            # Compute smoothed intensity envelope
            rectified = np.abs(seg_samples)
            envelope = signal.filtfilt(b, a, rectified)

            # Peak detection for syllable nuclei
            peak_threshold = np.mean(envelope) + self.config.energy_peak_prominence * np.std(envelope)
            peaks, _ = signal.find_peaks(
                envelope,
                height=max(peak_threshold, 1e-4),
                distance=min_distance_samples,
            )

            total_syllables += len(peaks)

        syllables_per_sec = total_syllables / vad_result.speechDurationSec
        # Convert syllables per second to estimated words per minute
        estimated_wpm = (syllables_per_sec * 60.0) / self.config.syllable_to_word_ratio

        return SpeakingRateMetrics(
            speakingRateWpm=round(float(estimated_wpm), 1),
            estimatedSyllableCount=total_syllables,
            syllablesPerSecond=round(float(syllables_per_sec), 2),
        )
