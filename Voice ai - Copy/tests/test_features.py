"""
Tests for acoustic feature extraction components.
"""

import unittest
import numpy as np

from config import PitchConfig, QualityConfig, SpeakingRateConfig, SystemConfig
from features.energy import EnergyAnalyzer
from features.feature_extractor import FeatureExtractor
from features.pauses import PauseAnalyzer
from features.pitch import PitchEstimator
from features.quality import QualityScorer
from features.speaking_rate import SpeakingRateEstimator
from preprocessing.audio_loader import AudioMetaData, ProcessedAudio
from vad.speech_detector import VoiceActivityDetector


class TestAcousticFeatures(unittest.TestCase):
    def setUp(self):
        self.config = SystemConfig()
        self.sr = 16000

    def _generate_synthetic_tone(self, freq_hz: float, duration_sec: float = 2.0, volume: float = 0.5):
        t = np.linspace(0, duration_sec, int(duration_sec * self.sr), endpoint=False)
        return (volume * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)

    def test_pitch_estimation_accuracy(self):
        # 180 Hz sine wave
        target_f0 = 180.0
        samples = self._generate_synthetic_tone(target_f0, duration_sec=2.0)
        vad = VoiceActivityDetector(self.config.vad)
        vad_res = vad.process(samples, self.sr)

        estimator = PitchEstimator(self.config.pitch)
        metrics = estimator.estimate(samples, self.sr, vad_res)

        self.assertAlmostEqual(metrics.pitchMeanHz, target_f0, delta=5.0)
        self.assertGreater(metrics.voicedRatio, 0.70)
        self.assertGreater(metrics.voicedFramesCount, 50)

    def test_energy_analyzer(self):
        vol = 0.4
        samples = self._generate_synthetic_tone(200.0, duration_sec=1.5, volume=vol)
        vad = VoiceActivityDetector(self.config.vad)
        vad_res = vad.process(samples, self.sr)

        energy = EnergyAnalyzer().process(samples, self.sr, vad_res)
        # RMS of sine with amplitude A is A / sqrt(2) ~ 0.4 / 1.414 ~ 0.2828
        expected_rms = vol / np.sqrt(2)
        self.assertAlmostEqual(energy.energyMeanRms, expected_rms, delta=0.03)

    def test_speaking_rate_estimator_label_and_output(self):
        estimator = SpeakingRateEstimator(self.config.speaking_rate)
        samples = self._generate_synthetic_tone(200.0, duration_sec=2.0)
        vad = VoiceActivityDetector(self.config.vad)
        vad_res = vad.process(samples, self.sr)

        metrics = estimator.estimate(samples, self.sr, vad_res)
        self.assertIn("estimate", metrics.methodology.lower())
        self.assertIsInstance(metrics.speakingRateWpm, float)
        self.assertGreaterEqual(metrics.speakingRateWpm, 0.0)

    def test_quality_scorer(self):
        scorer = QualityScorer(self.config.quality)
        vad = VoiceActivityDetector(self.config.vad)
        # 1.5s tone + 0.5s pause -> 75% speech ratio (optimal for speech evaluation)
        speech_part = self._generate_synthetic_tone(200.0, duration_sec=1.5, volume=0.5)
        pause_part = np.zeros(int(0.5 * self.sr), dtype=np.float32)
        samples = np.concatenate([speech_part, pause_part])
        vad_res = vad.process(samples, self.sr)

        # High quality clean audio
        clean_meta = AudioMetaData(
            durationSec=2.0, sampleRate=16000, channels=1, numSamples=32000,
            signalLevelRms=0.35, clippingRatio=0.0,
        )
        clean_res = scorer.score(clean_meta, vad_res, voiced_ratio=0.85)
        self.assertGreaterEqual(clean_res.qualityScore, 0.85)

        # Bad clipped audio
        clipped_meta = AudioMetaData(
            durationSec=2.0, sampleRate=16000, channels=1, numSamples=32000,
            signalLevelRms=0.9, clippingRatio=0.15,
        )
        bad_res = scorer.score(clipped_meta, vad_res, voiced_ratio=0.85)
        self.assertLess(bad_res.qualityScore, clean_res.qualityScore)

    def test_feature_extractor_master_output_schema(self):
        extractor = FeatureExtractor(self.config)
        samples = self._generate_synthetic_tone(190.0, duration_sec=2.0, volume=0.5)
        meta = AudioMetaData(
            durationSec=2.0, sampleRate=16000, channels=1, numSamples=len(samples),
            signalLevelRms=0.35, clippingRatio=0.0,
        )
        processed = ProcessedAudio(samples=samples, sample_rate=self.sr, metadata=meta)
        vad_res = VoiceActivityDetector(self.config.vad).process(samples, self.sr)

        result = extractor.extract(processed, vad_res)

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
            self.assertIn(k, result.features)
            val = result.features[k]
            self.assertFalse(np.isnan(val), f"Feature {k} is NaN")
            self.assertFalse(np.isinf(val), f"Feature {k} is Inf")
            self.assertIsInstance(val, float)

        self.assertEqual(len(result.feature_vector), len(expected_keys))


if __name__ == "__main__":
    unittest.main()
