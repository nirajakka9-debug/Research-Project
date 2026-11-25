"""
Voice AI Master Inference Pipeline.

Integrates Audio Preprocessing, Voice Activity Detection, Acoustic Feature Extraction,
and Statistical Voice Pattern Analysis into a unified, reproducible Voice Observation.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
import numpy as np

from config import SystemConfig
from features.feature_extractor import FeatureExtractionResult, FeatureExtractor
from models.longitudinal_tracker import (
    LongitudinalDeviationResult,
    LongitudinalTracker,
    PersonalVoiceBaseline,
)
from models.pattern_analyzer import StatisticalVoicePatternAnalyzer
from preprocessing.audio_loader import AudioLoader, AudioMetaData, ProcessedAudio
from vad.speech_detector import VoiceActivityDetector


@dataclass
class VoiceObservation:
    timestamp: str
    audio: Dict[str, Any]
    qualityScore: float
    features: Dict[str, float]
    featureVector: List[float]
    voicePattern: Optional[Dict[str, Any]] = None
    status: str = "success"

    def to_dict(self) -> Dict[str, Any]:
        """Converts observation to a clean dictionary matching longitudinal specification."""
        d = {
            "timestamp": self.timestamp,
            "status": self.status,
            "audio": {
                "durationSec": self.audio.get("durationSec"),
                "sampleRate": self.audio.get("sampleRate"),
                "channels": self.audio.get("channels"),
                "signalLevelRms": self.audio.get("signalLevelRms"),
                "clippingRatio": self.audio.get("clippingRatio"),
            },
            "qualityScore": self.qualityScore,
            "features": self.features,
        }
        if self.voicePattern is not None:
            d["voicePattern"] = self.voicePattern
        return d

    def to_json(self, indent: int = 2) -> str:
        """Serializes observation to structured JSON string ready for longitudinal persistence."""
        return json.dumps(
            self.to_dict(),
            indent=indent,
            default=lambda o: float(o) if hasattr(o, "__float__") else str(o),
        )


class VoiceAIPipeline:
    """End-to-end Voice AI processing pipeline designed for longitudinal voice tracking."""

    def __init__(self, config: Optional[SystemConfig] = None):
        self.config = config or SystemConfig()
        self.loader = AudioLoader(self.config.audio)
        self.vad = VoiceActivityDetector(self.config.vad)
        self.extractor = FeatureExtractor(self.config)
        self.ref_analyzer = StatisticalVoicePatternAnalyzer(self.config.baseline)
        self.longitudinal_tracker = LongitudinalTracker(self.config.baseline)

    def process_file(
        self,
        file_path: str,
        personal_baseline: Optional[PersonalVoiceBaseline] = None,
        update_baseline: bool = False,
        custom_baseline: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> VoiceObservation:
        """Processes a WAV audio file into a structured longitudinal Voice Observation.
        
        Args:
            file_path: Path to the WAV audio recording.
            personal_baseline: Optional PersonalVoiceBaseline instance for longitudinal tracking.
            update_baseline: If True and personal_baseline is provided, updates baseline AFTER evaluating.
            custom_baseline: Optional dictionary of mean/std deviations for ad-hoc reference analysis.
        """
        processed_audio = self.loader.load(file_path)
        return self._process_audio(
            processed_audio=processed_audio,
            personal_baseline=personal_baseline,
            update_baseline=update_baseline,
            custom_baseline=custom_baseline,
        )

    def process_samples(
        self,
        samples: np.ndarray,
        sample_rate: int,
        personal_baseline: Optional[PersonalVoiceBaseline] = None,
        update_baseline: bool = False,
    ) -> VoiceObservation:
        """Processes in-memory float32 audio samples directly without reading from disk."""
        # Normalize and compute basic metadata
        peak = float(np.max(np.abs(samples))) if len(samples) > 0 else 0.0
        norm_samples = samples * (0.95 / peak) if peak > 0 else samples
        duration_sec = len(samples) / float(sample_rate)
        rms = float(np.sqrt(np.mean(samples**2))) if len(samples) > 0 else 0.0
        clip_ratio = float(np.sum(np.abs(samples) >= 0.99)) / float(len(samples)) if len(samples) > 0 else 0.0

        metadata = AudioMetaData(
            durationSec=round(duration_sec, 3),
            sampleRate=sample_rate,
            channels=1,
            numSamples=len(samples),
            signalLevelRms=round(rms, 5),
            clippingRatio=round(clip_ratio, 5),
        )
        processed_audio = ProcessedAudio(
            samples=norm_samples.astype(np.float32),
            sample_rate=sample_rate,
            metadata=metadata,
        )
        return self._process_audio(
            processed_audio=processed_audio,
            personal_baseline=personal_baseline,
            update_baseline=update_baseline,
        )

    def _process_audio(
        self,
        processed_audio: ProcessedAudio,
        personal_baseline: Optional[PersonalVoiceBaseline] = None,
        update_baseline: bool = False,
        custom_baseline: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> VoiceObservation:
        """Internal execution pipeline orchestrating VAD, feature extraction, and baseline evaluation."""
        timestamp = datetime.now(timezone.utc).isoformat()

        # 1. Voice activity & pause detection
        vad_result = self.vad.process(processed_audio.samples, processed_audio.sample_rate)

        # 2. Acoustic feature extraction
        extraction_result = self.extractor.extract(processed_audio, vad_result)

        # 3. Deviation analysis (Longitudinal personal baseline takes precedence)
        voice_pattern: Optional[Dict[str, Any]] = None

        if personal_baseline is not None:
            # Evaluate against personal historical baseline BEFORE adding current observation
            dev_result: LongitudinalDeviationResult = self.longitudinal_tracker.evaluate_observation(
                extraction_result.features,
                personal_baseline,
            )

            voice_pattern = {
                "baselineType": "personal_longitudinal",
                "isBaselineEstablished": dev_result.is_baseline_established,
                "observationCount": dev_result.observation_count,
                "minObservationsRequired": dev_result.min_observations_required,
                "technicalDeviationScore": dev_result.technicalDeviationScore,
                "featureDeviations": dev_result.featureDeviations,
                "significantDeviations": dev_result.significantDeviations,
                "status": dev_result.status,
            }

            if update_baseline:
                # Add observation to personal history AFTER evaluation has completed
                personal_baseline.add_observation(extraction_result.features, timestamp=timestamp)

        else:
            # Fallback to reference distribution analysis
            pattern_result = self.ref_analyzer.analyze(
                extraction_result.features,
                custom_baseline=custom_baseline,
            )
            voice_pattern = {
                "baselineType": "reference_engineering_distribution",
                "technicalDeviationScore": pattern_result.technicalDeviationScore,
                "featureDeviations": pattern_result.featureDeviations,
                "significantDeviations": pattern_result.significantDeviations,
            }

        audio_meta = asdict(processed_audio.metadata)

        return VoiceObservation(
            timestamp=timestamp,
            status="success",
            audio=audio_meta,
            qualityScore=extraction_result.qualityMetrics.qualityScore,
            features=extraction_result.features,
            featureVector=extraction_result.feature_vector,
            voicePattern=voice_pattern,
        )
