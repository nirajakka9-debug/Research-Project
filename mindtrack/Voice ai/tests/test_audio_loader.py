"""
Tests for AudioLoader module.
"""

import os
import tempfile
import unittest
import numpy as np
import scipy.io.wavfile as wavfile

from config import AudioConfig
from preprocessing.audio_loader import AudioLoader, ProcessedAudio


class TestAudioLoader(unittest.TestCase):
    def setUp(self):
        self.config = AudioConfig(target_sample_rate=16000, min_duration_sec=0.5)
        self.loader = AudioLoader(self.config)

    def test_load_valid_wav(self):
        # 1-second 16kHz sine tone
        sr = 16000
        t = np.linspace(0, 1.0, sr, endpoint=False)
        tone = (0.5 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav_path = tf.name
        try:
            wavfile.write(wav_path, sr, tone)
            audio = self.loader.load(wav_path)
            self.assertIsInstance(audio, ProcessedAudio)
            self.assertEqual(audio.sample_rate, 16000)
            self.assertAlmostEqual(audio.metadata.durationSec, 1.0, delta=0.05)
            self.assertEqual(audio.metadata.channels, 1)
            self.assertLessEqual(np.max(np.abs(audio.samples)), 1.0)
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def test_stereo_to_mono_conversion(self):
        sr = 16000
        t = np.linspace(0, 1.0, sr, endpoint=False)
        left = (0.4 * np.sin(2 * np.pi * 300 * t) * 32767).astype(np.int16)
        right = (0.4 * np.sin(2 * np.pi * 600 * t) * 32767).astype(np.int16)
        stereo = np.column_stack([left, right])

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav_path = tf.name
        try:
            wavfile.write(wav_path, sr, stereo)
            audio = self.loader.load(wav_path)
            self.assertEqual(audio.metadata.channels, 2)
            self.assertEqual(audio.samples.ndim, 1)  # Converted to 1D mono
            self.assertEqual(audio.sample_rate, 16000)
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def test_resampling_from_44100(self):
        sr = 44100
        t = np.linspace(0, 1.0, sr, endpoint=False)
        tone = (0.5 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav_path = tf.name
        try:
            wavfile.write(wav_path, sr, tone)
            audio = self.loader.load(wav_path)
            self.assertEqual(audio.sample_rate, 16000)
            self.assertAlmostEqual(len(audio.samples), 16000, delta=100)
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def test_rejects_too_short_audio(self):
        sr = 16000
        short_samples = (np.random.randn(int(0.2 * sr)) * 1000).astype(np.int16)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav_path = tf.name
        try:
            wavfile.write(wav_path, sr, short_samples)
            with self.assertRaises(ValueError) as ctx:
                self.loader.load(wav_path)
            self.assertIn("too short", str(ctx.exception).lower())
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def test_rejects_complete_silence(self):
        sr = 16000
        silence = np.zeros(sr, dtype=np.int16)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav_path = tf.name
        try:
            wavfile.write(wav_path, sr, silence)
            with self.assertRaises(ValueError) as ctx:
                self.loader.load(wav_path)
            self.assertIn("silent", str(ctx.exception).lower())
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def test_detects_clipping(self):
        sr = 16000
        # Audio clipped at 100%
        clipped = np.full(sr, 32767, dtype=np.int16)
        # Add a few alternating values so it's not totally flat zero RMS
        clipped[::2] = -32767

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav_path = tf.name
        try:
            wavfile.write(wav_path, sr, clipped)
            audio = self.loader.load(wav_path)
            self.assertGreater(audio.metadata.clippingRatio, 0.90)
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)


if __name__ == "__main__":
    unittest.main()
