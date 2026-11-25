"""Isolated runner executed via subprocess to invoke Voice ai - Copy without altering original files."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe MindTrack Voice AI runner")
    parser.add_argument("--voice-ai-dir", required=True)
    parser.add_argument("--wav", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--mode", choices=["single", "calibrate", "assess"], required=True)
    parser.add_argument("--profile-path", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args()

    voice_dir = Path(args.voice_ai_dir).resolve()
    sys.path.insert(0, str(voice_dir))

    from inference.pipeline import VoiceAIPipeline  # type: ignore
    from models.longitudinal_tracker import PersonalVoiceBaseline  # type: ignore

    pipeline = VoiceAIPipeline()
    profile_path = Path(args.profile_path)
    personal_baseline = None
    update_flag = False

    if args.mode == "assess":
        if not profile_path.is_file():
            sys.stderr.write(
                f"No voice baseline profile found for user '{args.user_id}'. "
                "Please record at least 3 calibration sessions first or use Single Analysis mode.\n"
            )
            return 2
        personal_baseline = PersonalVoiceBaseline.load_from_file(str(profile_path))
        update_flag = bool(args.update_baseline)
    elif args.mode == "calibrate":
        if profile_path.is_file():
            personal_baseline = PersonalVoiceBaseline.load_from_file(str(profile_path))
        else:
            personal_baseline = PersonalVoiceBaseline(user_id=args.user_id, min_observations=3)
        update_flag = True

    try:
        obs = pipeline.process_file(
            args.wav,
            personal_baseline=personal_baseline,
            update_baseline=update_flag,
        )
    except Exception as exc:
        sys.stderr.write(f"Voice processing failed: {exc}\n")
        return 1

    if personal_baseline is not None and update_flag:
        personal_baseline.save_to_file(str(profile_path))

    result = obs.to_dict()
    result["operational_mode"] = args.mode
    result["user_id"] = args.user_id

    # Compute transparent quality warnings based directly on measured Voice AI audio/feature metrics
    warnings = []
    audio_meta = result.get("audio", {})
    feats = result.get("features", {})
    clip_ratio = float(audio_meta.get("clippingRatio") or 0.0)
    rms = float(audio_meta.get("signalLevelRms") or 0.0)
    speech_ratio = float(feats.get("speechRatio") or 0.0)
    quality_score = float(result.get("qualityScore") or 0.0)

    if clip_ratio > 0.02:
        warnings.append(f"Audio clipping detected ({clip_ratio * 100:.1f}% of samples near full scale).")
    if rms < 0.01:
        warnings.append("Low input microphone signal level (RMS < 0.01); move closer to the microphone.")
    if speech_ratio < 0.30:
        warnings.append(f"Low active speech ratio ({speech_ratio * 100:.1f}%); recording contains mostly silence or pauses.")
    if quality_score < 0.55:
        warnings.append("Overall acoustic quality score is low (< 0.55); interpret measurements cautiously.")

    result["qualityWarnings"] = warnings
    result["limitations"] = (
        "NON-DIAGNOSTIC ACOUSTIC MEASUREMENT: Voice AI computes rule-based DSP acoustic features "
        "(speaking rate, pauses, pitch, RMS energy) and statistical deviations. It does NOT detect "
        "emotion, stress levels, or mental illness."
    )
    if personal_baseline is not None:
        result["calibrationStatus"] = {
            "user_id": args.user_id,
            "observation_count": personal_baseline.observation_count,
            "min_observations_required": personal_baseline.min_observations,
            "is_established": personal_baseline.is_established,
        }

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
