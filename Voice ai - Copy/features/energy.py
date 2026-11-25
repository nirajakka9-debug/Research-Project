"""
Speech Energy Analysis Module.

Calculates root-mean-square (RMS) energy metrics strictly on active speech segments.
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np

from vad.speech_detector import VADResult


@dataclass
class EnergyMetrics:
    energyMeanRms: float
    energyStdDev: float


class EnergyAnalyzer:
    """Computes RMS energy statistics over voiced/speech regions."""

    def process(self, samples: np.ndarray, sample_rate: int, vad_result: VADResult) -> EnergyMetrics:
        """Calculates energy mean and std deviation over active speech frames."""
        win_length = int(0.025 * sample_rate)  # 25ms
        hop_length = int(0.010 * sample_rate)  # 10ms

        speech_rms_values = []

        for seg in vad_result.speech_segments:
            start_sample = int(seg.start_sec * sample_rate)
            end_sample = min(int(seg.end_sec * sample_rate), len(samples))
            seg_samples = samples[start_sample:end_sample]

            if len(seg_samples) < win_length:
                continue

            num_frames = max(1, 1 + (len(seg_samples) - win_length) // hop_length)
            for i in range(num_frames):
                frame = seg_samples[i * hop_length : i * hop_length + win_length]
                rms = float(np.sqrt(np.mean(frame**2))) if len(frame) > 0 else 0.0
                speech_rms_values.append(rms)

        if len(speech_rms_values) > 0:
            mean_rms = float(np.mean(speech_rms_values))
            std_rms = float(np.std(speech_rms_values))
        else:
            mean_rms = 0.0
            std_rms = 0.0

        return EnergyMetrics(
            energyMeanRms=round(mean_rms, 5),
            energyStdDev=round(std_rms, 5),
        )
