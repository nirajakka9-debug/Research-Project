"""
Voice Activity Detection (VAD) and Segmentation Module.

Segments audio frames into speech and silence regions using framed short-time energy
and Zero Crossing Rate (ZCR) with temporal smoothing and pause segmentation.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np

from config import VADConfig


@dataclass
class Segment:
    start_sec: float
    end_sec: float

    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec

    @property
    def duration_ms(self) -> float:
        return (self.end_sec - self.start_sec) * 1000.0


@dataclass
class VADResult:
    frame_decisions: np.ndarray  # Boolean array of speech decisions per frame
    frame_times: np.ndarray      # Timestamp (sec) for center of each frame
    speech_segments: List[Segment]
    pause_segments: List[Segment]
    speechDurationSec: float
    silenceDurationSec: float
    speechRatio: float
    totalPauseCount: int
    meanPauseDurationMs: float
    longestPauseDurationMs: float
    pauseRatePerMin: float


class VoiceActivityDetector:
    """Detects active speech regions and meaningful pauses in single-channel audio."""

    def __init__(self, config: Optional[VADConfig] = None):
        self.config = config or VADConfig()

    def process(self, samples: np.ndarray, sample_rate: int) -> VADResult:
        """Processes audio samples and yields detailed VAD segmentation metrics."""
        if len(samples) == 0:
            raise ValueError("Cannot perform VAD on empty sample array.")

        win_length = int(0.025 * sample_rate)  # 25ms window
        hop_length = int(0.010 * sample_rate)  # 10ms hop step

        if len(samples) < win_length:
            # Handle extremely short audio by using total length as single frame
            win_length = len(samples)
            hop_length = len(samples)

        # 1. Frame slicing & energy calculation
        num_frames = max(1, 1 + (len(samples) - win_length) // hop_length)
        energies = np.zeros(num_frames, dtype=np.float32)
        zcrs = np.zeros(num_frames, dtype=np.float32)
        frame_times = np.zeros(num_frames, dtype=np.float32)

        for i in range(num_frames):
            start_idx = i * hop_length
            end_idx = min(start_idx + win_length, len(samples))
            frame = samples[start_idx:end_idx]

            # RMS energy
            energies[i] = np.sqrt(np.mean(frame**2)) if len(frame) > 0 else 0.0

            # Zero crossing rate
            if len(frame) > 1:
                zcrs[i] = np.sum(np.abs(np.diff(np.signbit(frame)))) / float(len(frame))

            frame_times[i] = (start_idx + (end_idx - start_idx) / 2.0) / float(sample_rate)

        # 2. Principled adaptive relative energy thresholding
        noise_floor = float(np.percentile(energies, self.config.noise_floor_percentile))
        speech_peak = float(np.percentile(energies, self.config.speech_peak_percentile))

        if speech_peak < 1e-5:
            thresh = self.config.min_energy_floor
        else:
            snr_ratio = speech_peak / max(noise_floor, 1e-5)
            if snr_ratio < 3.0:
                # Nearly constant / low dynamic range signal (e.g. continuous tone or loud speech)
                thresh = max(self.config.min_energy_floor, 0.05 * speech_peak)
            else:
                # Dynamic speech signal: sit relative to noise floor
                thresh = max(
                    noise_floor + self.config.relative_energy_threshold * (speech_peak - noise_floor),
                    self.config.min_energy_floor,
                )

        # Primary speech decision: energy >= adaptive threshold
        definite_speech = energies >= thresh

        # Secondary unvoiced consonant extension (Rabiner-Sambur):
        # low-energy frames that have high ZCR (fricatives /s/, /t/, /sh/, /f/)
        unvoiced_speech = (energies >= self.config.unvoiced_energy_factor * thresh) & (
            zcrs >= self.config.unvoiced_zcr_threshold
        )
        raw_speech = definite_speech | unvoiced_speech

        # 3. Temporal smoothing to clean frame fluctuations
        min_speech_frames = max(1, int((self.config.min_speech_duration_ms / 1000.0) / (hop_length / sample_rate)))
        min_pause_frames = max(1, int((self.config.min_pause_duration_ms / 1000.0) / (hop_length / sample_rate)))

        smoothed = np.copy(raw_speech)

        # Fill short silence gaps smaller than min_pause_duration_ms
        silence_count = 0
        for i in range(len(smoothed)):
            if not smoothed[i]:
                silence_count += 1
            else:
                if 0 < silence_count < min_pause_frames and i - silence_count > 0:
                    smoothed[i - silence_count : i] = True
                silence_count = 0

        # Remove isolated speech bursts shorter than min_speech_duration_ms
        speech_count = 0
        for i in range(len(smoothed)):
            if smoothed[i]:
                speech_count += 1
            else:
                if 0 < speech_count < min_speech_frames and i - speech_count >= 0:
                    smoothed[i - speech_count : i] = False
                speech_count = 0

        # 4. Extract contiguous speech and pause segments
        speech_segments: List[Segment] = []
        pause_segments: List[Segment] = []

        in_speech = False
        seg_start = 0.0

        total_audio_duration = len(samples) / float(sample_rate)

        # Check initial segment at 0.0s
        if len(smoothed) > 0 and smoothed[0]:
            in_speech = True
            seg_start = 0.0
        else:
            in_speech = False
            seg_start = 0.0

        for i in range(1, len(smoothed)):
            time_sec = frame_times[i]
            if smoothed[i] and not in_speech:
                # Transition from silence to speech
                p_dur = time_sec - seg_start
                if p_dur >= (self.config.min_pause_duration_ms / 1000.0):
                    pause_segments.append(Segment(seg_start, time_sec))
                in_speech = True
                seg_start = time_sec
            elif not smoothed[i] and in_speech:
                # Transition from speech to silence
                speech_segments.append(Segment(seg_start, time_sec))
                in_speech = False
                seg_start = time_sec

        # Final segment flush
        if in_speech:
            speech_segments.append(Segment(seg_start, total_audio_duration))
        else:
            p_dur = total_audio_duration - seg_start
            if p_dur >= (self.config.min_pause_duration_ms / 1000.0):
                pause_segments.append(Segment(seg_start, total_audio_duration))

        # Summarize durations
        speech_duration_sec = sum(seg.duration_sec for seg in speech_segments)
        silence_duration_sec = max(0.0, total_audio_duration - speech_duration_sec)
        speech_ratio = speech_duration_sec / total_audio_duration if total_audio_duration > 0 else 0.0

        pause_durations_ms = [p.duration_ms for p in pause_segments]
        total_pause_count = len(pause_segments)
        mean_pause_ms = float(np.mean(pause_durations_ms)) if total_pause_count > 0 else 0.0
        longest_pause_ms = float(np.max(pause_durations_ms)) if total_pause_count > 0 else 0.0
        pause_rate_per_min = (total_pause_count / (speech_duration_sec / 60.0)) if speech_duration_sec > 0 else 0.0

        return VADResult(
            frame_decisions=smoothed,
            frame_times=frame_times,
            speech_segments=speech_segments,
            pause_segments=pause_segments,
            speechDurationSec=float(round(speech_duration_sec, 3)),
            silenceDurationSec=float(round(silence_duration_sec, 3)),
            speechRatio=float(round(speech_ratio, 3)),
            totalPauseCount=int(total_pause_count),
            meanPauseDurationMs=float(round(mean_pause_ms, 1)),
            longestPauseDurationMs=float(round(longest_pause_ms, 1)),
            pauseRatePerMin=float(round(pause_rate_per_min, 2)),
        )
