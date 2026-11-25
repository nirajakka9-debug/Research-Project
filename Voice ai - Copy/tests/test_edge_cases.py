"""
Edge case testing for Voice AI V1 Pipeline.
"""

import os
import tempfile
import unittest
import numpy as np
import scipy.io.wavfile as wavfile

from inference.pipeline import VoiceAIPipeline
from utils.synthetic_audio import generate_synthetic_speech_wav


class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.pipeline = VoiceAIPipeline()
        self.sr = 16000

    def test_pure_tone_audio(self):
        """Pipeline must handle a clean single-frequency tone without crashing."""
        dur = 2.0
        t = np.linspace(0, dur, int(dur * self.sr), endpoint=False)
        tone = (0.5 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)

        obs = self.pipeline.process_samples(tone, self.sr)
        self.assertEqual(obs.status, "success")
        self.assertAlmostEqual(obs.features["pitchMeanHz"], 220.0, delta=5.0)
        self.assertGreater(obs.qualityScore, 0.70)

    def test_borderline_short_audio(self):
        """Audio just above minimum duration threshold (0.55s)."""
        dur = 0.55
        t = np.linspace(0, dur, int(dur * self.sr), endpoint=False)
        tone = (0.5 * np.sin(2 * np.pi * 180.0 * t)).astype(np.float32)

        obs = self.pipeline.process_samples(tone, self.sr)
        self.assertEqual(obs.status, "success")
        self.assertAlmostEqual(obs.audio["durationSec"], 0.55, delta=0.05)

    def test_heavy_clipping_audio(self):
        """Severely clipped audio must be processed successfully and receive a low quality score."""
        dur = 2.0
        t = np.linspace(0, dur, int(dur * self.sr), endpoint=False)
        tone = 5.0 * np.sin(2 * np.pi * 180.0 * t)  # 5x amplitude
        clipped = np.clip(tone, -1.0, 1.0).astype(np.float32)

        obs = self.pipeline.process_samples(clipped, self.sr)
        self.assertEqual(obs.status, "success")
        # Clipping ratio should be very high
        self.assertGreater(obs.audio["clippingRatio"], 0.20)
        # Quality score should be heavily penalized (< 0.6)
        self.assertLess(obs.qualityScore, 0.60)

    def test_noisy_audio(self):
        """Audio embedded in white noise."""
        dur = 3.0
        t = np.linspace(0, dur, int(dur * self.sr), endpoint=False)
        speech_part = 0.3 * np.sin(2 * np.pi * 180.0 * t)
        noise = np.random.normal(0, 0.1, len(t))
        noisy_signal = (speech_part + noise).astype(np.float32)

        obs = self.pipeline.process_samples(noisy_signal, self.sr)
        self.assertEqual(obs.status, "success")
        for k, v in obs.features.items():
            self.assertFalse(np.isnan(v), f"Feature {k} returned NaN on noisy audio")
            self.assertFalse(np.isinf(v), f"Feature {k} returned Inf on noisy audio")

    def test_continuous_speech_no_pauses(self):
        """Synthetic speech with zero pauses."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav_path = tf.name
        try:
            generate_synthetic_speech_wav(
                wav_path,
                duration_sec=3.0,
                pause_count=0,
                pause_duration_sec=0.0,
            )
            obs = self.pipeline.process_file(wav_path)
            self.assertEqual(obs.status, "success")
            self.assertEqual(obs.features["totalPauseCount"], 0.0)
            self.assertGreater(obs.features["speechRatio"], 0.85)
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)


if __name__ == "__main__":
    unittest.main()
