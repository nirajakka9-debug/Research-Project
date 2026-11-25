"""
Tests for Voice Activity Detection (VAD) and Segmentation.
"""

import unittest
import numpy as np

from config import VADConfig
from vad.speech_detector import VoiceActivityDetector, VADResult


class TestVoiceActivityDetector(unittest.TestCase):
    def setUp(self):
        self.config = VADConfig(
            min_speech_duration_ms=100.0,
            min_pause_duration_ms=200.0,
        )
        self.vad = VoiceActivityDetector(self.config)
        self.sr = 16000

    def test_continuous_tone_speech(self):
        # 2 seconds of continuous tone (voiced)
        t = np.linspace(0, 2.0, 2 * self.sr, endpoint=False)
        tone = (0.5 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)

        result = self.vad.process(tone, self.sr)
        self.assertIsInstance(result, VADResult)
        self.assertGreater(result.speechRatio, 0.85)
        self.assertEqual(result.totalPauseCount, 0)
        self.assertGreater(result.speechDurationSec, 1.7)

    def test_speech_with_distinct_pauses(self):
        # 1s speech, 0.6s pause, 1s speech, 0.6s pause, 1s speech -> 2 internal pauses
        dur_speech = int(1.0 * self.sr)
        dur_pause = int(0.6 * self.sr)
        t = np.linspace(0, 1.0, dur_speech, endpoint=False)
        speech_part = (0.5 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
        pause_part = np.zeros(dur_pause, dtype=np.float32)

        signal = np.concatenate([speech_part, pause_part, speech_part, pause_part, speech_part])
        result = self.vad.process(signal, self.sr)

        self.assertGreaterEqual(result.totalPauseCount, 2)
        self.assertGreater(result.meanPauseDurationMs, 400.0)
        self.assertLess(result.meanPauseDurationMs, 800.0)
        self.assertAlmostEqual(result.speechDurationSec, 3.0, delta=0.4)
        self.assertAlmostEqual(result.silenceDurationSec, 1.2, delta=0.4)

    def test_short_glitch_silence_smoothed(self):
        # 1s speech, tiny 50ms silence (less than min_pause_duration_ms=200ms), 1s speech
        # The 50ms silence should be smoothed over and NOT counted as a pause.
        dur_speech = int(1.0 * self.sr)
        dur_glitch = int(0.05 * self.sr)
        t = np.linspace(0, 1.0, dur_speech, endpoint=False)
        speech_part = (0.5 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
        glitch_part = np.zeros(dur_glitch, dtype=np.float32)

        signal = np.concatenate([speech_part, glitch_part, speech_part])
        result = self.vad.process(signal, self.sr)

        self.assertEqual(result.totalPauseCount, 0)
        self.assertGreater(result.speechRatio, 0.90)

    def test_empty_samples_raises_value_error(self):
        empty = np.array([], dtype=np.float32)
        with self.assertRaises(ValueError):
            self.vad.process(empty, self.sr)


if __name__ == "__main__":
    unittest.main()
