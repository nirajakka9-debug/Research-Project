"""
Synthetic Audio Generator for Automated Unit Testing and Verification.

Generates realistic harmonic speech-like WAV recordings (formant sweep synthesis,
glottal pulse modulation, pitch inflections, speech bursts, and silence gaps)
to verify audio pipeline metrics across diverse acoustic variations.
"""

from typing import Optional
import numpy as np
import scipy.io.wavfile as wavfile
import scipy.signal as signal


def generate_synthetic_speech_wav(
    output_path: str,
    duration_sec: float = 6.0,
    sample_rate: int = 16000,
    pitch_hz: float = 180.0,
    syllables_per_sec: float = 4.0,
    pause_count: int = 2,
    pause_duration_sec: float = 0.5,
    volume: float = 0.5,
    clip: bool = False,
    silence_only: bool = False,
) -> str:
    """Generates a synthetic speech-like WAV file and saves it to output_path."""
    total_samples = int(duration_sec * sample_rate)

    if silence_only:
        audio = np.zeros(total_samples, dtype=np.float32)
        if volume > 0:
            audio += np.random.normal(0, 1e-5, total_samples).astype(np.float32)
        wavfile.write(output_path, sample_rate, (audio * 32767).astype(np.int16))
        return output_path

    t = np.linspace(0, duration_sec, total_samples, endpoint=False)

    # Base pitch with slight vibrato / intonation curve
    f0_t = pitch_hz + 15.0 * np.sin(2 * np.pi * 0.8 * t)

    # Phase accumulation for glottal source
    phase = 2 * np.pi * np.cumsum(f0_t) / sample_rate
    # Harmonic glottal pulse train (fundamental + harmonics)
    glottal_source = (
        np.sin(phase)
        + 0.5 * np.sin(2 * phase)
        + 0.25 * np.sin(3 * phase)
        + 0.125 * np.sin(4 * phase)
    )

    # Formant filter simulation (F1 = 500 Hz, F2 = 1500 Hz resonant filters)
    b_f1, a_f1 = signal.iirpeak(500.0 / (sample_rate / 2.0), Q=5.0)
    b_f2, a_f2 = signal.iirpeak(1500.0 / (sample_rate / 2.0), Q=5.0)

    formant_speech = signal.filtfilt(b_f1, a_f1, glottal_source) + 0.5 * signal.filtfilt(b_f2, a_f2, glottal_source)

    # Syllable intensity envelope modulation
    syllable_envelope = 0.5 * (1.0 + np.sin(2 * np.pi * syllables_per_sec * t))

    audio = formant_speech * syllable_envelope * volume

    # Insert explicit silence pauses
    if pause_count > 0 and pause_duration_sec > 0:
        pause_samples = int(pause_duration_sec * sample_rate)
        segment_len = total_samples // (pause_count + 1)
        for i in range(1, pause_count + 1):
            p_start = i * segment_len
            p_end = min(p_start + pause_samples, total_samples)
            audio[p_start:p_end] = 0.0

    # Apply clipping if requested
    if clip:
        audio = np.clip(audio * 3.0, -1.0, 1.0)

    # Convert to 16-bit PCM WAV
    audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16)
    wavfile.write(output_path, sample_rate, audio_int16)
    return output_path
