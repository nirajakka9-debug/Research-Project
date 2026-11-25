"""
Audio Loader Module.

Handles loading WAV audio files, format validation, mono conversion,
resampling to target rate (16 kHz), peak normalization, and metadata computation.
"""

import os
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
import scipy.io.wavfile as wavfile
import scipy.signal as signal
import soundfile as sf

from config import AudioConfig


@dataclass
class AudioMetaData:
    durationSec: float
    sampleRate: int
    channels: int
    numSamples: int
    signalLevelRms: float
    clippingRatio: float


@dataclass
class ProcessedAudio:
    samples: np.ndarray  # 1D float32 array normalized to [-1.0, 1.0]
    sample_rate: int
    metadata: AudioMetaData


class AudioLoader:
    """Loads, validates, and standardizes WAV audio signals for acoustic analysis."""

    def __init__(self, config: Optional[AudioConfig] = None):
        self.config = config or AudioConfig()

    def load(self, file_path: str) -> ProcessedAudio:
        """Loads WAV audio from disk, converts to mono 16kHz float32, normalizes, and extracts metadata.

        Raises ValueError or FileNotFoundError on unrecoverable input errors.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: '{file_path}'")

        try:
            # Load audio using soundfile (supports wide variety of WAV subtypes & float formats)
            samples, sr = sf.read(file_path, dtype="float32")
        except Exception as e:
            # Fallback to scipy.io.wavfile if soundfile fails
            try:
                sr, samples_int = wavfile.read(file_path)
                if samples_int.dtype == np.int16:
                    samples = samples_int.astype(np.float32) / 32768.0
                elif samples_int.dtype == np.int32:
                    samples = samples_int.astype(np.float32) / 2147483648.0
                elif samples_int.dtype == np.uint8:
                    samples = (samples_int.astype(np.float32) - 128.0) / 128.0
                else:
                    samples = samples_int.astype(np.float32)
            except Exception as inner_e:
                raise ValueError(f"Failed to read WAV audio file '{file_path}': {str(e)} | {str(inner_e)}")

        if samples is None or len(samples) == 0:
            raise ValueError(f"Audio file '{file_path}' contains no audio samples.")

        # Determine original channels
        channels = 1 if samples.ndim == 1 else samples.shape[1]

        # 1. Convert to mono if multichannel
        if samples.ndim > 1:
            samples = np.mean(samples, axis=1)

        original_num_samples = len(samples)
        duration_sec = float(original_num_samples) / float(sr)

        if duration_sec < self.config.min_duration_sec:
            raise ValueError(
                f"Audio duration ({duration_sec:.2f}s) is too short. "
                f"Minimum required duration is {self.config.min_duration_sec}s."
            )

        # Calculate raw signal quality metadata before resampling/normalization
        signal_level_rms = float(np.sqrt(np.mean(samples**2))) if len(samples) > 0 else 0.0
        max_abs = float(np.max(np.abs(samples))) if len(samples) > 0 else 0.0

        if max_abs == 0.0 or np.isnan(signal_level_rms):
            raise ValueError(f"Audio file '{file_path}' contains completely silent or invalid zero signal.")

        clipping_ratio = float(np.sum(np.abs(samples) >= self.config.clip_threshold)) / float(original_num_samples)

        # 2. Resample to target sample rate (default 16000 Hz)
        target_sr = self.config.target_sample_rate
        if sr != target_sr:
            samples = self._resample(samples, sr, target_sr)

        # 3. Peak normalization to 0.95 peak magnitude
        peak = np.max(np.abs(samples))
        if peak > 0:
            samples = samples * (0.95 / peak)

        metadata = AudioMetaData(
            durationSec=round(duration_sec, 3),
            sampleRate=target_sr,
            channels=channels,
            numSamples=len(samples),
            signalLevelRms=round(signal_level_rms, 5),
            clippingRatio=round(clipping_ratio, 5),
        )

        return ProcessedAudio(samples=samples.astype(np.float32), sample_rate=target_sr, metadata=metadata)

    def _resample(self, samples: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Polyphase resample signal to target rate."""
        gcd = np.gcd(orig_sr, target_sr)
        up = target_sr // gcd
        down = orig_sr // gcd
        resampled = signal.resample_poly(samples, up, down)
        return resampled
