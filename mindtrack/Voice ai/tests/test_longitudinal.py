"""
Tests for personal longitudinal baseline tracking and deviation analysis.
"""

import os
import tempfile
import unittest
import numpy as np

from config import LongitudinalBaselineConfig
from models.longitudinal_tracker import (
    LongitudinalDeviationResult,
    LongitudinalTracker,
    PersonalVoiceBaseline,
)


class TestLongitudinalTracker(unittest.TestCase):
    def setUp(self):
        self.config = LongitudinalBaselineConfig(min_observations_for_baseline=3)
        self.tracker = LongitudinalTracker(self.config)

    def test_initial_baseline_guard(self):
        """Initial baseline problem: ensures Z-scores are suppressed until enough sessions exist."""
        baseline = PersonalVoiceBaseline(user_id="test_user", min_observations=3)
        self.assertFalse(baseline.is_established)

        sample_features = {
            "speakingRateWpm": 150.0,
            "totalPauseCount": 4.0,
            "meanPauseDurationMs": 400.0,
            "longestPauseDurationMs": 700.0,
            "speechRatio": 0.75,
            "speechDurationSec": 7.5,
            "silenceDurationSec": 2.5,
            "pitchMeanHz": 180.0,
            "pitchStdDevHz": 22.0,
            "pitchRangeHz": 80.0,
            "energyMeanRms": 0.05,
            "energyStdDev": 0.02,
        }

        # Session 1
        res1 = self.tracker.evaluate_and_update(sample_features, baseline)
        self.assertFalse(res1.is_baseline_established)
        self.assertIsNone(res1.technicalDeviationScore)
        self.assertIn("insufficient_history", res1.status)

        # Session 2
        res2 = self.tracker.evaluate_and_update(sample_features, baseline)
        self.assertFalse(res2.is_baseline_established)
        self.assertIsNone(res2.technicalDeviationScore)

        # Session 3
        res3 = self.tracker.evaluate_and_update(sample_features, baseline)
        self.assertEqual(baseline.observation_count, 3)
        self.assertTrue(baseline.is_established)

    def test_user_example_exact_z_score(self):
        """Verifies the exact user prompt scenario:

        Historical baseline: 150 ± 15 WPM
        Current observation: 112 WPM
        Expected Z-score: (112 - 150) / 15 = -2.53
        """
        baseline = PersonalVoiceBaseline(user_id="user_prompt_spec", min_observations=3)

        # Populate history to yield mean=150.0 and std=15.0 for speakingRateWpm
        # 3 points with mean 150: [135.0, 150.0, 165.0] -> sample std = 15.0
        for wpm in [135.0, 150.0, 165.0]:
            baseline.add_observation({
                "speakingRateWpm": wpm,
                "pitchMeanHz": 180.0,
                "totalPauseCount": 4.0,
                "meanPauseDurationMs": 400.0,
                "longestPauseDurationMs": 700.0,
                "speechRatio": 0.75,
                "speechDurationSec": 7.5,
                "silenceDurationSec": 2.5,
                "pitchStdDevHz": 20.0,
                "pitchRangeHz": 80.0,
                "energyMeanRms": 0.05,
                "energyStdDev": 0.02,
            })

        self.assertTrue(baseline.is_established)
        stats = baseline.get_baseline_stats()
        self.assertAlmostEqual(stats["speakingRateWpm"]["mean"], 150.0, delta=0.1)
        self.assertAlmostEqual(stats["speakingRateWpm"]["std"], 15.0, delta=0.1)

        # Current observation with 112 WPM
        current_observation = {
            "speakingRateWpm": 112.0,
            "pitchMeanHz": 180.0,
            "totalPauseCount": 4.0,
            "meanPauseDurationMs": 400.0,
            "longestPauseDurationMs": 700.0,
            "speechRatio": 0.75,
            "speechDurationSec": 7.5,
            "silenceDurationSec": 2.5,
            "pitchStdDevHz": 20.0,
            "pitchRangeHz": 80.0,
            "energyMeanRms": 0.05,
            "energyStdDev": 0.02,
        }

        eval_result = self.tracker.evaluate_observation(current_observation, baseline)

        self.assertTrue(eval_result.is_baseline_established)
        # Expected Z = (112 - 150) / 15 = -2.5333...
        expected_z = round((112.0 - 150.0) / 15.0, 2)
        self.assertEqual(eval_result.featureDeviations["speakingRateWpm"], expected_z)
        self.assertEqual(expected_z, -2.53)

        # Ensure significant deviation message is properly generated
        self.assertTrue(any("speakingRateWpm is lower than personal baseline" in msg for msg in eval_result.significantDeviations))

    def test_non_contamination_guarantee(self):
        """Ensures the current observation is NOT included in the baseline used to evaluate itself."""
        baseline = PersonalVoiceBaseline(user_id="contamination_test", min_observations=3)
        for _ in range(3):
            baseline.add_observation({"speakingRateWpm": 100.0, "pitchMeanHz": 150.0})

        # Baseline mean is 100.0
        current_obs = {"speakingRateWpm": 200.0, "pitchMeanHz": 150.0}

        # Evaluate WITHOUT updating
        res = self.tracker.evaluate_observation(current_obs, baseline)
        self.assertEqual(baseline.observation_count, 3)
        self.assertEqual(res.baselineMeans["speakingRateWpm"], 100.0)

        # Confirm that observation was not secretly added
        self.assertEqual(len(baseline.history), 3)

    def test_zero_variance_guard(self):
        """Ensures zero variance does not cause division-by-zero or infinite Z-score."""
        baseline = PersonalVoiceBaseline(user_id="zero_variance_test", min_observations=3)
        # 3 identical observations
        for _ in range(3):
            baseline.add_observation({"totalPauseCount": 2.0, "speakingRateWpm": 150.0})

        stats = baseline.get_baseline_stats()
        self.assertEqual(stats["totalPauseCount"]["std"], 0.0)

        # Observation with 4 pauses
        current_obs = {"totalPauseCount": 4.0, "speakingRateWpm": 150.0}
        res = self.tracker.evaluate_observation(current_obs, baseline)

        z = res.featureDeviations["totalPauseCount"]
        self.assertIsNotNone(z)
        self.assertFalse(np.isinf(z))
        self.assertFalse(np.isnan(z))
        # With feature_min_std = 1.0 for totalPauseCount: Z = (4.0 - 2.0) / 1.0 = 2.0
        self.assertEqual(z, 2.0)

    def test_serialization_persistence(self):
        baseline = PersonalVoiceBaseline(user_id="persistence_user", min_observations=3)
        baseline.add_observation({"speakingRateWpm": 140.0, "pitchMeanHz": 170.0})
        baseline.add_observation({"speakingRateWpm": 160.0, "pitchMeanHz": 190.0})
        baseline.add_observation({"speakingRateWpm": 150.0, "pitchMeanHz": 180.0})

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            path = tf.name
        try:
            baseline.save_to_file(path)
            loaded = PersonalVoiceBaseline.load_from_file(path)
            self.assertEqual(loaded.user_id, "persistence_user")
            self.assertEqual(loaded.observation_count, 3)
            self.assertTrue(loaded.is_established)
            stats = loaded.get_baseline_stats()
            self.assertEqual(stats["speakingRateWpm"]["mean"], 150.0)
            self.assertAlmostEqual(stats["speakingRateWpm"]["std"], 10.0, delta=0.01)
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_strictly_non_clinical_terminology(self):
        """Verifies that no clinical or diagnostic labels are present in output strings."""
        baseline = PersonalVoiceBaseline(user_id="ethical_test", min_observations=3)
        for _ in range(3):
            baseline.add_observation({"speakingRateWpm": 150.0, "pitchMeanHz": 180.0})

        # Extreme outlier observation
        current_obs = {"speakingRateWpm": 60.0, "pitchMeanHz": 90.0}
        res = self.tracker.evaluate_observation(current_obs, baseline)

        serialized = str(res.to_dict()).lower()
        forbidden_terms = ["depression", "anxiety", "clinical", "disorder", "mental health", "diagnosis", "bipolar"]
        for term in forbidden_terms:
            self.assertNotIn(term, serialized, f"Forbidden clinical term '{term}' found in longitudinal output!")


if __name__ == "__main__":
    unittest.main()
