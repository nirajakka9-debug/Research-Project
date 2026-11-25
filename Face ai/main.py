"""
main.py
-------
Command-line interface for the MindTrack Facial Behaviour Longitudinal Wellness Monitoring module.

Usage:
    # 1. Calibration mode: Add check-in to personal baseline history
    python main.py --video videos/checkin1.mp4 --user-id demo_user --mode calibrate

    # 2. Assessment mode: Compare check-in against existing personal baseline
    python main.py --video videos/checkin2.mp4 --user-id demo_user --mode assess --output outputs/assessment.json

    # 3. Assessment with explicit baseline update:
    python main.py --video videos/checkin2.mp4 --user-id demo_user --mode assess --update-baseline

    # 4. Single-recording generic feature extraction (backward compatible):
    python main.py --video sample_synthetic.mp4

    python main.py --help
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

from face_analyzer import (
    FaceBehaviorAnalyzer,
    VideoValidationError,
    ModelAssetError,
    AnalysisResult
)
from baseline_manager import (
    BaselineManager,
    BaselineError,
    InvalidUserIdError,
    ProfileNotFoundError,
    IncompatibleProfileError,
    BaselineComparisonReport,
    validate_user_id,
    NON_DIAGNOSTIC_LIMITATION,
    DEFAULT_PROFILES_DIR,
    DEFAULT_MIN_CALIBRATION_CHECKINS,
    FEATURE_KEYS,
    FEATURE_UNITS
)


def format_val(val: Optional[float], decimals: int = 3, suffix: str = "") -> str:
    """Formats a float or None for clean terminal display."""
    if val is None:
        return "Unavailable (insufficient data)"
    return f"{val:.{decimals}f} {suffix}".strip()


def print_wellness_report(
    result: AnalysisResult,
    mode: str,
    user_id: Optional[str] = None,
    calibration_info: Optional[Dict[str, Any]] = None,
    comparison: Optional[BaselineComparisonReport] = None
) -> None:
    """
    Renders the structured MindTrack Longitudinal Wellness Monitoring Report
    containing Sections A through E.
    """
    meta = result.metadata
    q = result.quality
    f = result.features

    print("\n" + "=" * 76)
    print("      MINDTRACK: FACIAL BEHAVIOUR LONGITUDINAL WELLNESS CHECK-IN      ")
    print("=" * 76)

    # Header context
    mode_label = mode.upper()
    user_label = user_id if user_id else "None (Single Session)"
    print(f"  Mode: {mode_label:<18} | Participant / User ID: {user_label}")
    print(f"  File: {meta.filename:<18} | Processed: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 76)

    # ---------------------------------------------------------
    # A. CHECK-IN QUALITY
    # ---------------------------------------------------------
    print("\n[A] CHECK-IN QUALITY")
    print(f"    - Recording Duration      : {meta.duration_sec:.2f} s ({meta.total_frames} total frames @ {meta.fps:.1f} FPS)")
    print(f"    - Usable Tracked Frames   : {q.usable_frames} of {meta.total_frames} ({q.detection_coverage * 100.0:.1f}% coverage)")
    print(f"    - Face Region Lighting    : Lum {q.avg_luminance:.1f} / 255, Contrast {q.avg_contrast:.1f}")
    print(f"    - Mean Face Scale         : {q.avg_face_scale * 100.0:.1f}% of frame area")
    print(f"    - Tracking Quality Score  : {q.quality_score:.1f} / 100.0")

    reliability_str = "RELIABLE" if q.is_reliable else "LOW RELIABILITY"
    print(f"    - Tracking Reliability    : {reliability_str}")

    suitable_str = "YES (Suitable for personal baseline)" if q.is_suitable_for_baseline else "NO (Quality limits baseline suitability)"
    print(f"    - Baseline Suitability    : {suitable_str}")

    if q.warnings:
        print("    - Quality Warnings        :")
        for w in q.warnings:
            print(f"      * [!] {w}")

    # ---------------------------------------------------------
    # B. FACIAL BEHAVIOURAL OBSERVATIONS
    # ---------------------------------------------------------
    print("\n[B] FACIAL BEHAVIOURAL OBSERVATIONS")
    print("    Measured instantaneous geometric and temporal parameters:")
    print("    ------------------------------------------------------------------------")

    # 1. Facial Movement Velocity
    v_status = "Available" if f.facialMovementVelocity is not None else "Unavailable (requires >= 2 usable frames)"
    print(f"    1. Facial Movement Velocity : {format_val(f.facialMovementVelocity, 4, 'face-units/s')}")
    print(f"       Status: {v_status}")

    # 2. Eye Blink Rate
    b_count = f.auxiliary_metrics.get("total_blinks_detected", 0)
    b_status = f"Available ({b_count} blinks detected)" if f.eyeBlinkRatePm is not None else "Unavailable (requires >= 3.0s usable duration)"
    print(f"    2. Eye-Blink Rate           : {format_val(f.eyeBlinkRatePm, 1, 'blinks/min')}")
    print(f"       Status: {b_status}")

    # 3. Head Pose Variability
    yaw_s = format_val(f.auxiliary_metrics.get("yaw_std_deg"), 1, "deg")
    pitch_s = format_val(f.auxiliary_metrics.get("pitch_std_deg"), 1, "deg")
    roll_s = format_val(f.auxiliary_metrics.get("roll_std_deg"), 1, "deg")
    h_status = "Available" if f.headPoseJitterStd is not None else "Unavailable (requires >= 3 usable frames)"
    print(f"    3. Head-Pose Variability    : {format_val(f.headPoseJitterStd, 2, 'deg')} (aggregate std dev)")
    print(f"       Components: yaw={yaw_s}, pitch={pitch_s}, roll={roll_s}")
    print(f"       Status: {h_status}")

    # 4. Smile Intensity Proxy
    s_peak = format_val(f.auxiliary_metrics.get("smile_peak_ratio"), 3)
    s_status = "Available" if f.smileIntensityProxy is not None else "Unavailable"
    print(f"    4. Smile-Intensity Proxy    : {format_val(f.smileIntensityProxy, 3, '(mouth/interocular)')}")
    print(f"       Peak Ratio: {s_peak} | Status: {s_status}")

    # 5. Brow Furrow Proxy
    br_min = format_val(f.auxiliary_metrics.get("brow_min_ratio"), 3)
    br_status = "Available" if f.browFurrowProxy is not None else "Unavailable"
    print(f"    5. Brow-Furrow Proxy        : {format_val(f.browFurrowProxy, 3, '(brow-eye/interocular)')}")
    print(f"       Minimum Distance Ratio: {br_min} | Status: {br_status}")
    print("    ------------------------------------------------------------------------")

    # ---------------------------------------------------------
    # C. PERSONAL BASELINE COMPARISON
    # ---------------------------------------------------------
    print("\n[C] PERSONAL BASELINE COMPARISON")

    if mode == "calibrate":
        if calibration_info:
            tot = calibration_info.get("total_checkins", 0)
            req = calibration_info.get("min_required", 5)
            is_cal = calibration_info.get("is_calibrated", False)
            status_desc = "ESTABLISHED" if is_cal else f"IN PROGRESS ({tot}/{req} check-ins recorded)"
            print(f"    - Calibration Status      : {status_desc}")
            print(f"    - Total Check-ins Stored  : {tot} (minimum required for baseline: {req})")
            if not is_cal:
                rem = max(0, req - tot)
                print(f"    - Calibration Requirement : {rem} more valid check-in(s) needed before baseline is considered established.")
            else:
                print(f"    - Baseline Stability      : Minimum calibration observations fulfilled. Baseline profile updated.")
            print(f"    - Profile Storage Path    : {calibration_info.get('profile_path', 'profiles/')}")
        else:
            print("    Calibration session recorded.")

    elif mode == "assess" and comparison:
        cal_str = "ESTABLISHED" if comparison.is_calibrated else f"PRELIMINARY ({comparison.total_calibration_checkins}/{comparison.min_checkins_required} check-ins)"
        print(f"    - Personal Baseline Status: {cal_str}")
        print(f"    - Calibration Check-ins   : {comparison.total_calibration_checkins} session(s)")
        print("\n    Feature-by-Feature Baseline Comparison:")
        print("    " + "-" * 72)
        print(f"    {'Feature':<25} | {'Observed':<10} | {'Base Mean':<10} | {'Base SD':<8} | {'Diff':<8} | {'z-score':<8}")
        print("    " + "-" * 72)

        for k in FEATURE_KEYS:
            comp = comparison.comparisons.get(k)
            if not comp:
                continue
            cur_s = f"{comp.current_value:.3f}" if comp.current_value is not None else "N/A"
            mean_s = f"{comp.baseline_mean:.3f}" if comp.baseline_mean is not None else "N/A"
            std_s = f"{comp.baseline_std:.3f}" if comp.baseline_std is not None else "N/A"
            diff_s = f"{comp.absolute_difference:+.3f}" if comp.absolute_difference is not None else "N/A"
            z_s = f"{comp.standardized_z:+.2f}" if comp.standardized_z is not None else "N/A"

            print(f"    {k:<25} | {cur_s:<10} | {mean_s:<10} | {std_s:<8} | {diff_s:<8} | {z_s:<8}")
            print(f"      -> Interpretation: {comp.interpretation}")

        print("    " + "-" * 72)

    else:
        print("    Personal baseline comparison not active. Run in --mode calibrate or --mode assess with --user-id.")

    # ---------------------------------------------------------
    # D. WELLNESS-RELATED INTERPRETATION
    # ---------------------------------------------------------
    print("\n[D] WELLNESS-RELATED INTERPRETATION")
    if comparison and comparison.summary_observations:
        for obs in comparison.summary_observations:
            print(f"    - {obs}")
        print("    - Note: These longitudinal measurements reflect physical, cognitive, and environmental")
        print("      influences and must be evaluated alongside contextual self-reports.")
    elif mode == "calibrate":
        print("    - Check-in recorded toward establishing the participant's empirical facial behaviour baseline.")
        print("    - Once established, future check-ins will evaluate relative deviations from this reference.")
    else:
        print("    - Single-session check-in. Without a personal baseline, longitudinal deviations cannot be determined.")

    # ---------------------------------------------------------
    # E. STRESS AND MENTAL WELLNESS LIMITATIONS
    # ---------------------------------------------------------
    print("\n[E] STRESS AND MENTAL WELLNESS LIMITATIONS")
    print(f"    RESEARCH NOTICE: {NON_DIAGNOSTIC_LIMITATION}")
    print("    - This system does NOT detect, diagnose, or classify stress, depression, anxiety,")
    print("      or any psychiatric illness.")
    print("    - No stress score, stress percentage, probability, or clinical label is computed.")
    print("    - Facial behaviour variations can occur due to lighting, fatigue, speaking, or physiological")
    print("      factors and do not constitute proof of emotional or psychological state.")
    print("=" * 76 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MindTrack: Non-Diagnostic Facial Behaviour Wellness Monitoring Module (Terminal Only).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Calibrate personal baseline (run at least 5 times across distinct check-ins):
  python main.py --video videos/checkin1.mp4 --user-id demo_user --mode calibrate

  # Assess a check-in against the user's established baseline:
  python main.py --video videos/checkin2.mp4 --user-id demo_user --mode assess --output outputs/assessment.json

  # Assess and optionally incorporate the check-in into baseline history:
  python main.py --video videos/checkin2.mp4 --user-id demo_user --mode assess --update-baseline

  # Single recording generic check-in:
  python main.py --video sample_synthetic.mp4
        """
    )
    parser.add_argument(
        "--video", "-v",
        required=True,
        type=str,
        help="Path to the input video file (e.g. mp4, avi, mov, mkv, webm)."
    )
    parser.add_argument(
        "--user-id", "-u",
        required=False,
        type=str,
        default=None,
        help="Participant / User identifier for personal baseline profile (alphanumeric, '_', '-')."
    )
    parser.add_argument(
        "--mode", "-m",
        required=False,
        type=str,
        choices=["calibrate", "assess", "single"],
        default=None,
        help="Operational mode: 'calibrate' (accumulate baseline), 'assess' (compare to baseline), or 'single'."
    )
    parser.add_argument(
        "--output", "-o",
        required=False,
        type=str,
        default=None,
        help="Optional path to export full assessment / check-in results in JSON format."
    )
    parser.add_argument(
        "--max-duration",
        required=False,
        type=float,
        default=15.0,
        help="Maximum allowable video duration in seconds (default: 15.0 s)."
    )
    parser.add_argument(
        "--min-checkins",
        required=False,
        type=int,
        default=DEFAULT_MIN_CALIBRATION_CHECKINS,
        help=f"Minimum calibration check-ins required to establish baseline (default: {DEFAULT_MIN_CALIBRATION_CHECKINS})."
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="In assessment mode, explicitly append this check-in to the baseline profile after assessment."
    )
    parser.add_argument(
        "--profiles-dir",
        required=False,
        type=str,
        default=DEFAULT_PROFILES_DIR,
        help="Directory to store persistent user baseline profiles (default: profiles/)."
    )
    parser.add_argument(
        "--model-path",
        required=False,
        type=str,
        default=None,
        help="Optional custom path to the MediaPipe Face Landmarker model asset (.task)."
    )

    args = parser.parse_args()

    # Determine operational mode
    if args.mode is not None:
        effective_mode = args.mode
    elif args.user_id is not None:
        effective_mode = "assess"
    else:
        effective_mode = "single"

    # Validate user ID when mode requires it
    if effective_mode in ["calibrate", "assess"]:
        if not args.user_id:
            sys.stderr.write(
                f"\n[ERROR] Operational mode '{effective_mode}' requires a user ID.\n"
                f"Please provide --user-id <id> (e.g. --user-id demo_user).\n"
            )
            return 1
        try:
            clean_user_id = validate_user_id(args.user_id)
        except InvalidUserIdError as ie:
            sys.stderr.write(f"\n[ERROR] Invalid User ID: {ie}\n")
            return 1
    else:
        clean_user_id = None

    # Baseline manager initialization
    baseline_mgr = BaselineManager(
        profiles_dir=args.profiles_dir,
        min_calibration_checkins=args.min_checkins
    )

    # In assessment mode, check if baseline profile exists beforehand
    if effective_mode == "assess":
        if not baseline_mgr.profile_exists(clean_user_id):
            sys.stderr.write(
                f"\n[NOTICE] No baseline profile found for user '{clean_user_id}'.\n"
                f"Assessment mode compares new recordings against an established personal baseline.\n"
                f"Please first run in calibration mode to establish a baseline:\n"
                f"    python main.py --video \"{args.video}\" --user-id {clean_user_id} --mode calibrate\n"
            )
            return 1

    # Progress reporting function
    last_print = 0.0

    def progress_callback(current: int, total: int):
        nonlocal last_print
        now = time.time()
        if now - last_print > 0.3 or current == total:
            last_print = now
            pct = (current / max(1, total)) * 100.0
            sys.stdout.write(f"\r[*] Analyzing video: {current}/{total} frames ({pct:.1f}%)")
            sys.stdout.flush()

    try:
        analyzer = FaceBehaviorAnalyzer(model_path=args.model_path)
        print(f"[*] Validating and analyzing video: {args.video}")
        result = analyzer.analyze_video(
            video_path=args.video,
            max_duration_sec=args.max_duration,
            progress_callback=progress_callback
        )
        print("\n[*] Video analysis completed.")

        calibration_info: Optional[Dict[str, Any]] = None
        comparison_report: Optional[BaselineComparisonReport] = None

        # Mode: Calibrate
        if effective_mode == "calibrate":
            try:
                updated_profile, _ = baseline_mgr.add_calibration_checkin(
                    user_id=clean_user_id,
                    features=result.features,
                    quality=result.quality,
                    video_filename=result.metadata.filename
                )
                calibration_info = {
                    "user_id": clean_user_id,
                    "total_checkins": updated_profile.total_checkins_recorded,
                    "min_required": updated_profile.min_calibration_checkins,
                    "is_calibrated": updated_profile.is_calibrated,
                    "profile_path": str(baseline_mgr.get_profile_path(clean_user_id))
                }
                result.calibration_status = calibration_info
            except BaselineError as be:
                sys.stderr.write(f"\n[WARNING] Baseline calibration skipped: {be}\n")
                calibration_info = {
                    "user_id": clean_user_id,
                    "error": str(be)
                }
                result.calibration_status = calibration_info

        # Mode: Assess
        elif effective_mode == "assess":
            profile = baseline_mgr.load_profile(clean_user_id)
            comparison_report = baseline_mgr.compare_checkin_with_baseline(
                profile=profile,
                features=result.features,
                quality=result.quality
            )
            result.baseline_comparison = comparison_report

            # Optional: update baseline if user explicitly requested
            if args.update_baseline and result.quality.is_suitable_for_baseline:
                baseline_mgr.add_calibration_checkin(
                    user_id=clean_user_id,
                    features=result.features,
                    quality=result.quality,
                    video_filename=result.metadata.filename
                )
                print(f"[*] Baseline updated with new observation (--update-baseline).")

        # Print the complete wellness report
        print_wellness_report(
            result=result,
            mode=effective_mode,
            user_id=clean_user_id,
            calibration_info=calibration_info,
            comparison=comparison_report
        )

        # Export JSON if requested
        if args.output:
            out_path = Path(args.output).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2)
            print(f"[*] Exported wellness check-in results to JSON: {out_path}")

        return 0

    except VideoValidationError as ve:
        sys.stderr.write(f"\n[ERROR] Video Validation Failed: {ve}\n")
        return 1
    except ModelAssetError as me:
        sys.stderr.write(f"\n[ERROR] Model Asset Error: {me}\n")
        return 2
    except BaselineError as be:
        sys.stderr.write(f"\n[ERROR] Baseline Profile Error: {be}\n")
        return 1
    except KeyboardInterrupt:
        sys.stderr.write("\n[ABORTED] Processing interrupted by user.\n")
        return 130
    except Exception as e:
        sys.stderr.write(f"\n[UNEXPECTED ERROR] {e}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
