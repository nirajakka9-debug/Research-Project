"""
Voice AI System CLI Runner (V1).

Usage:
  python main.py <path_to_recording.wav>
  python main.py --dir <path_to_directory>
  python main.py --demo

Options:
  --save-json <path>  Optionally save the observation JSON output to a file.
  --demo              Synthesize test speech WAV files and run pipeline verification.
"""

import argparse
import os
import sys
from typing import Any, Dict, List, Optional

from inference.pipeline import VoiceAIPipeline
from models.longitudinal_tracker import PersonalVoiceBaseline
from utils.synthetic_audio import generate_synthetic_speech_wav


def print_human_summary(file_path: str, observation) -> None:
    """Prints a clear, structured natural language summary of the voice observation."""
    print("=" * 65)
    print("                 VOICE AI V1 OBSERVATION SUMMARY                 ")
    print("=" * 65)
    print(f"File Path      : {file_path}")
    print(f"Timestamp      : {observation.timestamp}")
    print(f"Quality Score  : {observation.qualityScore:.2f} / 1.00")
    print("-" * 65)
    print("AUDIO METADATA:")
    print(f"  Duration     : {observation.audio['durationSec']} sec")
    print(f"  Sample Rate  : {observation.audio['sampleRate']} Hz")
    print(f"  Channels     : {observation.audio['channels']} (mono processed)")
    print(f"  Signal RMS   : {observation.audio['signalLevelRms']}")
    print(f"  Clipping     : {observation.audio['clippingRatio'] * 100:.2f}%")
    print("-" * 65)
    print("EXTRACTED ACOUSTIC FEATURES:")
    f = observation.features
    print(f"  Speaking Rate (Estimated) : {f['speakingRateWpm']} WPM")
    print(f"  Total Pause Count        : {int(f['totalPauseCount'])}")
    print(f"  Mean Pause Duration      : {f['meanPauseDurationMs']} ms")
    print(f"  Longest Pause Duration   : {f['longestPauseDurationMs']} ms")
    print(f"  Speech Ratio             : {f['speechRatio'] * 100:.1f}%")
    print(f"  Speech Duration          : {f['speechDurationSec']} sec")
    print(f"  Silence Duration         : {f['silenceDurationSec']} sec")
    print(f"  Pitch Mean (F0)          : {f['pitchMeanHz']} Hz")
    print(f"  Pitch Std Dev            : {f['pitchStdDevHz']} Hz")
    print(f"  Pitch Range              : {f['pitchRangeHz']} Hz")
    print(f"  Energy Mean (RMS)        : {f['energyMeanRms']}")
    print(f"  Energy Std Dev           : {f['energyStdDev']}")
    print("-" * 65)
    print("LONGITUDINAL / TECHNICAL VOICE-PATTERN DEVIATION:")
    vp = observation.voicePattern
    if vp:
        b_type = vp.get("baselineType", "reference")
        print(f"  Baseline Type            : {b_type}")
        if "isBaselineEstablished" in vp:
            print(f"  Baseline Established     : {vp['isBaselineEstablished']} (Sessions: {vp.get('observationCount')}/{vp.get('minObservationsRequired')})")
        score = vp.get("technicalDeviationScore")
        score_str = f"{score:.2f}" if score is not None else "N/A (insufficient baseline sessions)"
        print(f"  Technical Deviation Score: {score_str}")
        devs = vp.get("significantDeviations", [])
        if devs:
            print("  Deviations from Baseline :")
            for dev in devs:
                print(f"    - {dev}")
        else:
            print("  Deviations from Baseline : None (within baseline tolerance)")
    else:
        print("  Deviation Analysis       : Omitted")
    print("=" * 65)


def process_single_file(
    pipeline: VoiceAIPipeline,
    file_path: str,
    baseline_path: Optional[str] = None,
    personal_baseline: Optional[PersonalVoiceBaseline] = None,
    update_baseline: bool = False,
    save_json_path: Optional[str] = None,
) -> None:
    try:
        if baseline_path:
            if os.path.exists(baseline_path):
                personal_baseline = PersonalVoiceBaseline.load_from_file(baseline_path)
                print(f"[*] Loaded existing personal baseline from '{baseline_path}' ({personal_baseline.observation_count} sessions)")
            else:
                personal_baseline = PersonalVoiceBaseline(user_id="user_001")
                print(f"[*] Initialized new personal baseline for '{baseline_path}'")

        obs = pipeline.process_file(
            file_path,
            personal_baseline=personal_baseline,
            update_baseline=update_baseline,
        )

        if personal_baseline and update_baseline and baseline_path:
            personal_baseline.save_to_file(baseline_path)
            print(f"[+] Updated and saved personal baseline to '{baseline_path}' (Total sessions: {personal_baseline.observation_count})")

        print_human_summary(file_path, obs)
        print("\nSTRUCTURED JSON OBSERVATION OUTPUT:")
        json_output = obs.to_json(indent=2)
        print(json_output)

        if save_json_path:
            with open(save_json_path, "w", encoding="utf-8") as f:
                f.write(json_output)
            print(f"\n[+] Saved JSON observation to '{save_json_path}'")

    except Exception as e:
        print(f"\n[!] ERROR processing '{file_path}': {str(e)}", file=sys.stderr)
        sys.exit(1)


def process_directory(pipeline: VoiceAIPipeline, dir_path: str) -> None:
    if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
        print(f"[!] Directory not found: '{dir_path}'", file=sys.stderr)
        sys.exit(1)

    wav_files = [
        os.path.join(dir_path, f) for f in os.listdir(dir_path) if f.lower().endswith(".wav")
    ]

    if not wav_files:
        print(f"[!] No .wav files found in directory '{dir_path}'")
        return

    print(f"[*] Found {len(wav_files)} WAV recording(s) in directory '{dir_path}'\n")

    for wav_file in wav_files:
        print(f"\n--- Processing: {os.path.basename(wav_file)} ---")
        try:
            obs = pipeline.process_file(wav_file)
            print(
                f"Quality: {obs.qualityScore:.2f} | WPM: {obs.features['speakingRateWpm']} | "
                f"Pitch: {obs.features['pitchMeanHz']} Hz | Pauses: {int(obs.features['totalPauseCount'])} | "
                f"SpeechRatio: {obs.features['speechRatio']:.2f}"
            )
        except Exception as e:
            print(f"[!] Failed to process '{wav_file}': {str(e)}")


def run_sensitivity_comparison(pipeline: VoiceAIPipeline) -> None:
    """Generates audio variations (normal, fast, slow, high pitch, long pauses) and compares extracted features."""
    print("=" * 70)
    print("       VOICE AI V1 ACOUSTIC SENSITIVITY COMPARISON DEMO          ")
    print("=" * 70)
    print("Testing pipeline sensitivity to varying acoustic characteristics...\n")

    configs = [
        ("Normal Speech", 180.0, 3.5, 2, 0.4),
        ("Fast Speech", 180.0, 6.0, 2, 0.3),
        ("Slow Speech", 180.0, 2.0, 2, 0.6),
        ("High Pitch Voice", 260.0, 3.5, 2, 0.4),
        ("Long Pauses Speech", 180.0, 3.5, 4, 0.9),
    ]

    import tempfile
    for name, pitch, syllables_rate, pauses, pause_dur in configs:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            temp_wav = tf.name

        try:
            generate_synthetic_speech_wav(
                temp_wav,
                duration_sec=7.0,
                pitch_hz=pitch,
                syllables_per_sec=syllables_rate,
                pause_count=pauses,
                pause_duration_sec=pause_dur,
            )
            obs = pipeline.process_file(temp_wav)
            f = obs.features
            print(f"[{name:18s}] -> WPM: {f['speakingRateWpm']:5.1f} | Pitch: {f['pitchMeanHz']:5.1f} Hz | Pauses: {int(f['totalPauseCount']):2d} | Mean Pause: {f['meanPauseDurationMs']:5.1f} ms | Speech Ratio: {f['speechRatio']:.2f}")
        finally:
            if os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except OSError:
                    pass
    print("=" * 70)


def run_demo(pipeline: VoiceAIPipeline) -> None:
    print("[*] Running Voice AI V1 Demo with longitudinal multi-session simulation...\n")
    demo_baseline = PersonalVoiceBaseline(user_id="demo_participant_01", min_observations=3)
    
    import tempfile
    # Simulate Days 1, 2, 3 (consistent baseline around 150 WPM, 180 Hz)
    print("--- 1. Establishing Personal Longitudinal Baseline (Days 1, 2, 3) ---")
    for day in [1, 2, 3]:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            temp_wav = tf.name
        try:
            generate_synthetic_speech_wav(
                temp_wav,
                duration_sec=6.0,
                pitch_hz=180.0 + (day * 2.0),
                syllables_per_sec=3.8,
                pause_count=2,
                pause_duration_sec=0.4,
            )
            obs = pipeline.process_file(temp_wav, personal_baseline=demo_baseline, update_baseline=True)
            print(f"Day {day} processed -> Baseline established: {demo_baseline.is_established} (Sessions: {demo_baseline.observation_count}/3)")
        finally:
            if os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except OSError:
                    pass

    # Baseline is now established!
    stats = demo_baseline.get_baseline_stats()
    print(f"\n[+] Personal baseline established for {demo_baseline.user_id}:")
    print(f"    Speaking Rate Mean : {stats['speakingRateWpm']['mean']} ± {stats['speakingRateWpm']['std']} WPM")
    print(f"    Pitch Mean         : {stats['pitchMeanHz']['mean']} ± {stats['pitchMeanHz']['std']} Hz")

    # Simulate Day 4: Significant reduction in speaking rate (110 WPM) and longer pauses
    print("\n--- 2. Evaluating Day 4 Observation (Slow Speech Drift) ---")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        temp_wav = tf.name
    try:
        generate_synthetic_speech_wav(
            temp_wav,
            duration_sec=6.0,
            pitch_hz=175.0,
            syllables_per_sec=2.2,  # noticeably slower
            pause_count=3,
            pause_duration_sec=0.7,
        )
        # Process Day 4 against baseline WITHOUT updating yet
        process_single_file(
            pipeline,
            temp_wav,
            personal_baseline=demo_baseline,
            save_json_path="demo_observation.json",
        )
    finally:
        if os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except OSError:
                pass


def main():
    parser = argparse.ArgumentParser(description="Standalone Voice AI System V1 - Longitudinal Voice Tracker")
    parser.add_argument("input_wav", nargs="?", help="Path to WAV speech recording file")
    parser.add_argument("--dir", type=str, help="Path to directory containing WAV recordings to process in batch")
    parser.add_argument("--demo", action="store_true", help="Run multi-session longitudinal baseline demonstration")
    parser.add_argument("--compare-sensitivity", action="store_true", help="Compare extracted features across varied acoustics")
    parser.add_argument("--baseline", type=str, help="Path to personal baseline JSON file to evaluate against")
    parser.add_argument("--update-baseline", type=str, help="Path to personal baseline JSON file to evaluate against AND update")
    parser.add_argument("--save-json", type=str, help="Optional output filepath to save JSON observation")

    args = parser.parse_args()
    pipeline = VoiceAIPipeline()

    if args.demo:
        run_demo(pipeline)
    elif args.compare_sensitivity:
        run_sensitivity_comparison(pipeline)
    elif args.dir:
        process_directory(pipeline, args.dir)
    elif args.input_wav:
        baseline_file = args.update_baseline or args.baseline
        update_flag = bool(args.update_baseline)
        process_single_file(
            pipeline,
            args.input_wav,
            baseline_path=baseline_file,
            update_baseline=update_flag,
            save_json_path=args.save_json,
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

