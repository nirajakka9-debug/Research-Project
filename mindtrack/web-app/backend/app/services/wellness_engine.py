"""Transparent multimodal wellness summary and longitudinal helper engine.

Strictly adheres to non-diagnostic research boundaries:
- Never invents missing modality values or replaces omitted modalities with 0.
- Never fabricates a stress score, probability, or clinical label.
- Explicitly labels the multimodal fusion layer as an exploratory research framework.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional

from ..config import NON_DIAGNOSTIC_NOTICE
from ..models import (
    CheckinSessionModel,
    FaceFeatureModel,
    QuestionnaireResponseModel,
    VoiceFeatureModel,
)

ALL_MODALITIES = ("QUESTIONNAIRE", "FACE", "VOICE")


def compute_questionnaire_summary(q: Optional[QuestionnaireResponseModel]) -> Optional[Dict[str, Any]]:
    if q is None:
        return None
    phq2_total = (
        q.phq2_anhedonia + q.phq2_depressed_mood
        if q.phq2_anhedonia is not None and q.phq2_depressed_mood is not None
        else None
    )
    gad2_total = (
        q.gad2_nervousness + q.gad2_worrying
        if q.gad2_nervousness is not None and q.gad2_worrying is not None
        else None
    )
    return {
        "phq2Anhedonia": q.phq2_anhedonia,
        "phq2DepressedMood": q.phq2_depressed_mood,
        "phq2Total": phq2_total,
        "gad2Nervousness": q.gad2_nervousness,
        "gad2Worrying": q.gad2_worrying,
        "gad2Total": gad2_total,
        "dailyAffectMood": q.daily_affect_mood,
        "dailyAffectEnergy": q.daily_affect_energy,
        "dailyAffectStress": q.daily_affect_stress,
        "sleepQuality": q.sleep_quality,
        "reflectionNote": q.reflection_note,
    }


def compute_questionnaire_baseline_stats(
    checkins: List[CheckinSessionModel],
) -> Dict[str, Any]:
    """Computes empirical personal baseline statistics for questionnaire self-report scales."""
    fields = {
        "dailyAffectMood": [],
        "dailyAffectEnergy": [],
        "dailyAffectStress": [],
        "phq2Total": [],
        "gad2Total": [],
    }
    for session in checkins:
        q = session.questionnaire
        if q is None:
            continue
        fields["dailyAffectMood"].append(float(q.daily_affect_mood))
        fields["dailyAffectEnergy"].append(float(q.daily_affect_energy))
        fields["dailyAffectStress"].append(float(q.daily_affect_stress))
        if q.phq2_anhedonia is not None and q.phq2_depressed_mood is not None:
            fields["phq2Total"].append(float(q.phq2_anhedonia + q.phq2_depressed_mood))
        if q.gad2_nervousness is not None and q.gad2_worrying is not None:
            fields["gad2Total"].append(float(q.gad2_nervousness + q.gad2_worrying))

    stats: Dict[str, Dict[str, Any]] = {}
    for key, values in fields.items():
        n = len(values)
        if n == 0:
            stats[key] = {"count": 0, "mean": None, "std": None}
        elif n == 1:
            stats[key] = {"count": 1, "mean": round(values[0], 3), "std": 0.0}
        else:
            mean = sum(values) / n
            var = sum((v - mean) ** 2 for v in values) / (n - 1)
            stats[key] = {"count": n, "mean": round(mean, 3), "std": round(math.sqrt(max(0.0, var)), 3)}
    return stats


def build_transparent_wellness_summary(
    available_modalities: List[str],
    questionnaire: Optional[QuestionnaireResponseModel],
    face: Optional[FaceFeatureModel],
    voice: Optional[VoiceFeatureModel],
) -> Dict[str, Any]:
    """Builds a transparent, non-diagnostic per-check-in multimodal summary."""
    missing = [m for m in ALL_MODALITIES if m not in available_modalities]
    observations: List[str] = []

    q_summary = compute_questionnaire_summary(questionnaire)
    if q_summary:
        observations.append(
            f"Self-report affect recorded (Mood {q_summary['dailyAffectMood']}/5, "
            f"Energy {q_summary['dailyAffectEnergy']}/5, Perceived Stress {q_summary['dailyAffectStress']}/5)."
        )

    face_summary: Optional[Dict[str, Any]] = None
    if face is not None:
        face_raw = json.loads(face.raw_json)
        face_comp = face_raw.get("baseline_comparison")
        face_cal = face_raw.get("calibration_status")
        face_summary = {
            "mode": face.mode,
            "qualityScore": face.quality_score,
            "isReliable": face.is_reliable,
            "isSuitableForBaseline": face.is_suitable_for_baseline,
            "features": {
                "facialMovementVelocity": face.facial_movement_velocity,
                "eyeBlinkRatePm": face.eye_blink_rate_pm,
                "headPoseJitterStd": face.head_pose_jitter_std,
                "smileIntensityProxy": face.smile_intensity_proxy,
                "browFurrowProxy": face.brow_furrow_proxy,
            },
            "baselineComparison": face_comp,
            "calibrationStatus": face_cal,
        }
        if face.is_reliable is False:
            observations.append(
                f"Facial recording quality was low ({face.quality_score}/100); interpret facial features cautiously."
            )
        elif face_comp and face_comp.get("summary_observations"):
            observations.extend(face_comp["summary_observations"][:2])
        else:
            observations.append(
                f"Facial behaviour measurements extracted ({face.usable_frames}/{face.total_frames} tracked frames)."
            )

    voice_summary: Optional[Dict[str, Any]] = None
    if voice is not None:
        voice_raw = json.loads(voice.raw_json)
        vp = voice_raw.get("voicePattern")
        voice_summary = {
            "mode": voice.mode,
            "qualityScore": voice.quality_score,
            "features": voice_raw.get("features", {}),
            "voicePattern": vp,
            "qualityWarnings": voice_raw.get("qualityWarnings", []),
        }
        if vp and vp.get("significantDeviations"):
            observations.extend(vp["significantDeviations"][:2])
        else:
            observations.append(
                f"Voice acoustic measurements extracted (Quality {voice.quality_score:.2f}/1.00, "
                f"{voice.speaking_rate_wpm:.1f} WPM)."
            )

    if missing:
        observations.append(
            f"Omitted modalities ({', '.join(missing)}) are stored as missing (null), never imputed as zero."
        )

    return {
        "fusionModelStatus": "UNVALIDATED_RESEARCH_FRAMEWORK",
        "fusionModelNotice": (
            "No validated multimodal AI fusion model or composite clinical stress score is active. "
            "Modalities are presented side by side with personal-baseline comparisons where available."
        ),
        "stressScore": None,
        "availableModalities": available_modalities,
        "missingModalities": missing,
        "questionnaire": q_summary,
        "face": face_summary,
        "voice": voice_summary,
        "crossModalityObservations": observations,
        "disclaimer": NON_DIAGNOSTIC_NOTICE,
    }
