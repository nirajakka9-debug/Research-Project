"""
Fundamental Frequency (Pitch / F0) Estimation Module.

Uses normalized autocorrelation on active speech frames to track human pitch (75 Hz - 400 Hz),
ignoring unvoiced frames and silence gaps.
"""

from dataclasses import dataclass
from typing import List, Optional
import numpy as np
import scipy.signal as signal

from config import PitchConfig
from vad.speech_detector import VADResult


@dataclass
class PitchMetrics:
    pitchMeanHz: float
    pitchStdDevHz: float
    pitchRangeHz: float
    voicedFramesCount: int
    voicedRatio: float
    f0_series: List[float]


class PitchEstimator:
    """Extracts fundamental frequency (F0) prosodic statistics from speech regions.
    
    Uses Boersma's window-unbiased normalized autocorrelation (Praat methodology)
    with local peak finding, octave-cost candidate scoring, sub-sample parabolic
    interpolation, and running median filter outlier rejection.
    """

    def __init__(self, config: Optional[PitchConfig] = None):
        self.config = config or PitchConfig()

    def estimate(self, samples: np.ndarray, sample_rate: int, vad_result: VADResult) -> PitchMetrics:
        """Estimates voiced pitch statistics across speech segments."""
        min_lag = int(sample_rate / self.config.max_f0_hz)  # max f0 -> min lag
        max_lag = int(sample_rate / self.config.min_f0_hz)  # min f0 -> max lag

        win_length = int(0.040 * sample_rate)  # 40ms window
        hop_length = int(0.010 * sample_rate)  # 10ms hop

        # Precompute window autocorrelation to unbias window taper (Boersma method)
        w = np.hanning(win_length)
        n = win_length
        fft_w = np.fft.rfft(w, n=2 * n)
        ac_w = np.fft.irfft(np.abs(fft_w) ** 2)[:n]

        f0_estimates: List[float] = []
        total_speech_frames = 0

        num_frames = max(1, 1 + (len(samples) - win_length) // hop_length)

        for i in range(num_frames):
            start_idx = i * hop_length
            end_idx = min(start_idx + win_length, len(samples))
            frame_center_sec = (start_idx + (end_idx - start_idx) / 2.0) / float(sample_rate)

            # Check if current frame lies within active speech segment according to VAD
            is_speech = any(seg.start_sec <= frame_center_sec <= seg.end_sec for seg in vad_result.speech_segments)
            if not is_speech:
                continue

            total_speech_frames += 1
            frame = samples[start_idx:end_idx]

            if len(frame) < win_length:
                continue

            # Remove DC offset & apply window
            frame_zero_mean = frame - np.mean(frame)
            windowed = frame_zero_mean * w

            # Compute autocorrelation using FFT
            fft_res = np.fft.rfft(windowed, n=2 * n)
            power_spectrum = np.abs(fft_res) ** 2
            ac_x = np.fft.irfft(power_spectrum)[:n]

            # Boersma unbiased normalized autocorrelation (eliminates window taper lag bias)
            unbiased_ac = ac_x / np.maximum(ac_w, 1e-6)
            if unbiased_ac[0] <= 0:
                continue
            norm_autocorr = unbiased_ac / unbiased_ac[0]

            # Search strictly interior local peaks within lag range
            search_region = norm_autocorr[min_lag : min(max_lag + 1, len(norm_autocorr))]
            if len(search_region) < 3:
                continue

            peaks, props = signal.find_peaks(search_region, height=self.config.voicing_threshold)
            if len(peaks) == 0:
                continue

            # Score candidates using Praat octave cost:
            # score = peak_height - octave_cost * log2(lag / min_lag)
            scores = [
                h - self.config.octave_cost * np.log2((min_lag + p) / min_lag)
                for p, h in zip(peaks, props["peak_heights"])
            ]
            best_idx = np.argmax(scores)
            best_p = peaks[best_idx]

            best_lag = float(min_lag + best_p)

            # Parabolic interpolation for sub-sample precision
            if 0 < best_p < len(search_region) - 1:
                y1 = search_region[best_p - 1]
                y2 = search_region[best_p]
                y3 = search_region[best_p + 1]
                denom = 2 * (2 * y2 - y1 - y3)
                if abs(denom) > 1e-6:
                    delta = (y1 - y3) / denom
                    best_lag += delta

            f0 = float(sample_rate) / float(best_lag)

            # Confirm pitch falls strictly in valid range
            if self.config.min_f0_hz <= f0 <= self.config.max_f0_hz:
                f0_estimates.append(float(round(f0, 2)))

        # Apply running median filter to clean isolated pitch outliers
        med_k = self.config.median_filter_length
        if med_k % 2 == 0:
            med_k += 1
        if len(f0_estimates) >= med_k:
            f0_estimates = list(signal.medfilt(f0_estimates, kernel_size=med_k))

        voiced_count = len(f0_estimates)
        voiced_ratio = (voiced_count / total_speech_frames) if total_speech_frames > 0 else 0.0

        if voiced_count > 0:
            pitch_mean = float(np.mean(f0_estimates))
            pitch_std = float(np.std(f0_estimates))
            pitch_range = float(np.ptp(f0_estimates))  # peak to peak max-min
        else:
            pitch_mean = 0.0
            pitch_std = 0.0
            pitch_range = 0.0

        return PitchMetrics(
            pitchMeanHz=round(pitch_mean, 2),
            pitchStdDevHz=round(pitch_std, 2),
            pitchRangeHz=round(pitch_range, 2),
            voicedFramesCount=voiced_count,
            voicedRatio=round(voiced_ratio, 3),
            f0_series=[round(float(x), 2) for x in f0_estimates],
        )

