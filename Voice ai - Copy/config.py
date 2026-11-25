"""
Centralized Configuration for Voice AI System (V1).

Defines audio processing standards, VAD thresholds, acoustic analysis limits,
quality evaluation weights, and statistical baseline reference parameters.
"""

from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass
class AudioConfig:
    target_sample_rate: int = 16000
    target_channels: int = 1
    min_duration_sec: float = 0.5
    frame_length_sec: float = 0.025  # 25 ms window
    frame_step_sec: float = 0.010    # 10 ms hop
    clip_threshold: float = 0.99     # Normalized sample magnitude threshold for clipping detection


@dataclass
class VADConfig:
    speech_peak_percentile: float = 90.0        # Upper percentile for active speech peak energy
    noise_floor_percentile: float = 10.0        # Lower percentile for background noise floor estimation
    relative_energy_threshold: float = 0.035    # Dynamic range fraction between noise floor and speech peak (~-29 dB)
    min_energy_floor: float = 0.0005            # Minimum absolute RMS floor to prevent gating on machine epsilon
    min_speech_duration_ms: float = 100.0       # Minimum duration to count as active speech segment
    min_pause_duration_ms: float = 200.0        # Minimum silence duration to qualify as a meaningful pause
    unvoiced_energy_factor: float = 0.40        # Energy fraction for unvoiced consonant boundary inclusion
    unvoiced_zcr_threshold: float = 0.15        # Minimum ZCR to classify unvoiced consonant at word boundary


@dataclass
class PitchConfig:
    min_f0_hz: float = 75.0          # Lower bound of human vocal fundamental frequency
    max_f0_hz: float = 400.0         # Upper bound of human vocal fundamental frequency
    voicing_threshold: float = 0.35  # Unbiased autocorrelation peak threshold for voiced frames
    octave_cost: float = 0.03        # Penalty per octave favoring true fundamental period (Praat formulation)
    median_filter_length: int = 5    # Running median filter window size for outlier rejection


@dataclass
class SpeakingRateConfig:
    min_syllable_distance_ms: float = 120.0  # Minimum gap between syllable energy peaks (~8.3 syllables/sec max, ~330 WPM ceiling)
    syllable_to_word_ratio: float = 1.5      # Average syllables per word in standard speech
    energy_peak_prominence: float = 0.15     # Relative peak prominence for syllable nucleus detection


@dataclass
class QualityConfig:
    min_acceptable_snr_db: float = 5.0
    optimal_speech_ratio_range: Tuple[float, float] = (0.4, 0.9)
    max_clipping_ratio: float = 0.02


@dataclass
class LongitudinalBaselineConfig:
    """Non-clinical reference baseline parameters and thresholds for longitudinal tracking.
    
    Used as an engineering reference fallback when insufficient historical observations
    exist for an individual's personal baseline.
    """
    min_observations_for_baseline: int = 3  # Minimum past sessions required to establish personal baseline
    min_feature_std: float = 1e-3           # Minimum std dev floor to prevent division by zero or near-zero variance
    significance_z_threshold: float = 1.5   # |Z| threshold to flag a feature-level deviation

    feature_means: Dict[str, float] = field(default_factory=lambda: {
        "speakingRateWpm": 150.0,
        "totalPauseCount": 5.0,
        "meanPauseDurationMs": 400.0,
        "longestPauseDurationMs": 800.0,
        "speechRatio": 0.70,
        "speechDurationSec": 5.0,
        "silenceDurationSec": 2.0,
        "pitchMeanHz": 180.0,
        "pitchStdDevHz": 25.0,
        "pitchRangeHz": 100.0,
        "energyMeanRms": 0.05,
        "energyStdDev": 0.02,
    })

    feature_std_devs: Dict[str, float] = field(default_factory=lambda: {
        "speakingRateWpm": 30.0,
        "totalPauseCount": 3.0,
        "meanPauseDurationMs": 150.0,
        "longestPauseDurationMs": 350.0,
        "speechRatio": 0.15,
        "speechDurationSec": 2.5,
        "silenceDurationSec": 1.5,
        "pitchMeanHz": 40.0,
        "pitchStdDevHz": 12.0,
        "pitchRangeHz": 40.0,
        "energyMeanRms": 0.03,
        "energyStdDev": 0.015,
    })

    # Physical minimum standard deviation floors to guard against zero/near-zero variance
    feature_min_stds: Dict[str, float] = field(default_factory=lambda: {
        "speakingRateWpm": 5.0,
        "totalPauseCount": 1.0,
        "meanPauseDurationMs": 50.0,
        "longestPauseDurationMs": 50.0,
        "speechRatio": 0.05,
        "speechDurationSec": 0.5,
        "silenceDurationSec": 0.5,
        "pitchMeanHz": 5.0,
        "pitchStdDevHz": 2.0,
        "pitchRangeHz": 5.0,
        "energyMeanRms": 0.005,
        "energyStdDev": 0.002,
    })


@dataclass
class SystemConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    vad: VADConfig = field(default_factory=VADConfig)
    pitch: PitchConfig = field(default_factory=PitchConfig)
    speaking_rate: SpeakingRateConfig = field(default_factory=SpeakingRateConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    baseline: LongitudinalBaselineConfig = field(default_factory=LongitudinalBaselineConfig)
