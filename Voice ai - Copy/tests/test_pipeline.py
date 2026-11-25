"""
End-to-end Pipeline tests including real speech inference.
"""

import json
import os
import tempfile
import unittest

from inference.pipeline import VoiceAIPipeline, VoiceObservation
from utils.synthetic_audio import generate_synthetic_speech_wav


class TestEndToEndPipeline(unittest.TestCase):
    def setUp(self):
        self.pipeline = VoiceAIPipeline()
        self.real_wav_path = os.path.join("test_data", "real_speech.wav")

    def test_synthetic_speech_end_to_end(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav_path = tf.name
        try:
            generate_synthetic_speech_wav(
                wav_path,
                duration_sec=5.0,
                pitch_hz=175.0,
                syllables_per_sec=3.5,
                pause_count=2,
                pause_duration_sec=0.4,
            )

            obs = self.pipeline.process_file(wav_path)
            self.assertIsInstance(obs, VoiceObservation)
            self.assertEqual(obs.status, "success")
            self.assertGreaterEqual(obs.qualityScore, 0.70)

            # Check JSON serialization
            json_str = obs.to_json()
            parsed = json.loads(json_str)

            self.assertIn("timestamp", parsed)
            self.assertIn("audio", parsed)
            self.assertIn("qualityScore", parsed)
            self.assertIn("features", parsed)

            features = parsed["features"]
            expected_keys = [
                "speakingRateWpm",
                "totalPauseCount",
                "meanPauseDurationMs",
                "longestPauseDurationMs",
                "speechRatio",
                "speechDurationSec",
                "silenceDurationSec",
                "pitchMeanHz",
                "pitchStdDevHz",
                "pitchRangeHz",
                "energyMeanRms",
                "energyStdDev",
            ]
            for k in expected_keys:
                self.assertIn(k, features)
                self.assertIsInstance(features[k], (int, float))

        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def test_real_speech_inference(self):
        """Runs the complete Voice AI pipeline on real human speech recording."""
        if not os.path.exists(self.real_wav_path):
            self.skipTest(f"Real audio file '{self.real_wav_path}' not found.")

        obs = self.pipeline.process_file(self.real_wav_path)

        self.assertEqual(obs.status, "success")
        self.assertAlmostEqual(obs.audio["durationSec"], 14.84, delta=0.2)
        self.assertEqual(obs.audio["sampleRate"], 16000)
        self.assertGreater(obs.qualityScore, 0.80)

        # Real speech acoustic measurements check
        f = obs.features
        self.assertGreater(f["speakingRateWpm"], 80.0)  # Human speech rate range
        self.assertLess(f["speakingRateWpm"], 250.0)
        self.assertGreater(f["pitchMeanHz"], 85.0)     # Human vocal range
        self.assertLess(f["pitchMeanHz"], 300.0)
        self.assertGreater(f["speechDurationSec"], 5.0)
        self.assertGreater(f["totalPauseCount"], 0)
        self.assertGreater(f["energyMeanRms"], 0.01)


if __name__ == "__main__":
    unittest.main()
