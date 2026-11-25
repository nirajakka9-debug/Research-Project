"""
Sensitivity and monotonicity verification tests.

Verifies that modifying acoustic parameters in the input signal produces
predictable, physically consistent shifts in the extracted feature measurements.
"""

import os
import tempfile
import unittest

from inference.pipeline import VoiceAIPipeline
from utils.synthetic_audio import generate_synthetic_speech_wav


class TestAcousticSensitivity(unittest.TestCase):
    def setUp(self):
        self.pipeline = VoiceAIPipeline()

    def test_pitch_sensitivity(self):
        """Higher input pitch must yield higher pitchMeanHz."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf1, \
             tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf2:
            wav_low = tf1.name
            wav_high = tf2.name

        try:
            generate_synthetic_speech_wav(wav_low, duration_sec=4.0, pitch_hz=140.0)
            generate_synthetic_speech_wav(wav_high, duration_sec=4.0, pitch_hz=260.0)

            obs_low = self.pipeline.process_file(wav_low)
            obs_high = self.pipeline.process_file(wav_high)

            f_low = obs_low.features["pitchMeanHz"]
            f_high = obs_high.features["pitchMeanHz"]

            self.assertGreater(f_high, f_low + 70.0, f"Expected pitch {f_high} to be significantly higher than {f_low}")
        finally:
            for p in [wav_low, wav_high]:
                if os.path.exists(p):
                    os.remove(p)

    def test_speaking_rate_sensitivity(self):
        """Faster syllable rate must yield higher speakingRateWpm."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf1, \
             tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf2:
            wav_slow = tf1.name
            wav_fast = tf2.name

        try:
            generate_synthetic_speech_wav(wav_slow, duration_sec=5.0, syllables_per_sec=2.0)
            generate_synthetic_speech_wav(wav_fast, duration_sec=5.0, syllables_per_sec=5.5)

            obs_slow = self.pipeline.process_file(wav_slow)
            obs_fast = self.pipeline.process_file(wav_fast)

            wpm_slow = obs_slow.features["speakingRateWpm"]
            wpm_fast = obs_fast.features["speakingRateWpm"]

            self.assertGreater(wpm_fast, wpm_slow + 30.0, f"Expected fast WPM ({wpm_fast}) to be higher than slow WPM ({wpm_slow})")
        finally:
            for p in [wav_slow, wav_fast]:
                if os.path.exists(p):
                    os.remove(p)

    def test_pause_structure_sensitivity(self):
        """Adding pauses must increase totalPauseCount and decrease speechRatio."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf1, \
             tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf2:
            wav_few = tf1.name
            wav_many = tf2.name

        try:
            generate_synthetic_speech_wav(wav_few, duration_sec=6.0, pause_count=1, pause_duration_sec=0.4)
            generate_synthetic_speech_wav(wav_many, duration_sec=6.0, pause_count=4, pause_duration_sec=0.8)

            obs_few = self.pipeline.process_file(wav_few)
            obs_many = self.pipeline.process_file(wav_many)

            self.assertGreater(obs_many.features["totalPauseCount"], obs_few.features["totalPauseCount"])
            self.assertGreater(obs_many.features["meanPauseDurationMs"], obs_few.features["meanPauseDurationMs"])
            self.assertLess(obs_many.features["speechRatio"], obs_few.features["speechRatio"])
        finally:
            for p in [wav_few, wav_many]:
                if os.path.exists(p):
                    os.remove(p)

    def test_energy_sensitivity(self):
        """Higher recording volume must yield higher unnormalized signalLevelRms."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf1, \
             tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf2:
            wav_quiet = tf1.name
            wav_loud = tf2.name

        try:
            generate_synthetic_speech_wav(wav_quiet, duration_sec=4.0, volume=0.1)
            generate_synthetic_speech_wav(wav_loud, duration_sec=4.0, volume=0.8)

            obs_quiet = self.pipeline.process_file(wav_quiet)
            obs_loud = self.pipeline.process_file(wav_loud)

            # Raw unnormalized signalLevelRms should reflect the 8x volume difference
            self.assertGreater(obs_loud.audio["signalLevelRms"], obs_quiet.audio["signalLevelRms"] * 4.0)
            self.assertGreater(obs_loud.audio["signalLevelRms"], 0.05)
            self.assertLess(obs_quiet.audio["signalLevelRms"], 0.03)
        finally:
            for p in [wav_quiet, wav_loud]:
                if os.path.exists(p):
                    os.remove(p)


if __name__ == "__main__":
    unittest.main()
