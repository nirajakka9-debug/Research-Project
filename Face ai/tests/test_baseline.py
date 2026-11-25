"""
test_baseline.py
----------------
Comprehensive unit tests for the longitudinal personal baseline system and wellness monitoring:
- Baseline creation and local JSON persistence
- User ID sanitization and path traversal prevention
- Calibration check-in accumulation and minimum check-in threshold
- Feature-specific statistics (never treating missing features as zero)
- Assessment without an existing baseline (proper error / notice)
- Zero and near-zero baseline variance handling
- Standardized z-score, relative change %, and absolute difference calculations
- Prevention of accidental baseline modification during assessment
- Quality suitability checks preventing low-quality calibration
- Incompatible or corrupt profile handling
- Verification of non-diagnostic wording (no stress scores, no medical claims)
"""

import json
import math
import tempfile
from pathlib import Path
import pytest

from baseline_manager import (
    BaselineManager,
    UserBaselineProfile,
    FeatureStatistic,
    InvalidUserIdError,
    ProfileNotFoundError,
    IncompatibleProfileError,
    BaselineError,
    validate_user_id,
    NON_DIAGNOSTIC_LIMITATION,
    FEATURE_KEYS
)
from feature_calculations import ExtractedFeatures
from quality_assessment import QualityReport


def create_dummy_quality(is_suitable: bool = True) -> QualityReport:
    """Creates a synthetic QualityReport for testing."""
    if is_suitable:
        return QualityReport(
            total_frames=100,
            usable_frames=100,
            fps=30.0,
            duration_sec=3.33,
            detection_coverage=1.0,
            quality_score=95.0,
            is_reliable=True,
            is_suitable_for_baseline=True,
            warnings=[]
        )
    else:
        return QualityReport(
            total_frames=100,
            usable_frames=10,
            fps=30.0,
            duration_sec=3.33,
            detection_coverage=0.10,
            quality_score=15.0,
            is_reliable=False,
            is_suitable_for_baseline=False,
            warnings=["Severe tracking loss"]
        )


def create_dummy_features(
    vel: float = 0.20,
    blink: float = 24.0,
    jitter: float = 2.0,
    smile: float = 0.60,
    brow: float = 0.30
) -> ExtractedFeatures:
    """Creates synthetic ExtractedFeatures for testing."""
    return ExtractedFeatures(
        facialMovementVelocity=vel,
        eyeBlinkRatePm=blink,
        headPoseJitterStd=jitter,
        smileIntensityProxy=smile,
        browFurrowProxy=brow
    )


def test_user_id_validation_and_path_traversal():
    """Verify that safe user IDs are accepted and dangerous path traversal IDs are rejected."""
    # Valid IDs
    assert validate_user_id("user_123") == "user_123"
    assert validate_user_id("participant-A") == "participant-A"
    assert validate_user_id("demoUser") == "demoUser"

    # Dangerous path traversal attacks must be rejected
    with pytest.raises(InvalidUserIdError):
        validate_user_id("../secret")
    with pytest.raises(InvalidUserIdError):
        validate_user_id("..\\windows\\system32")
    with pytest.raises(InvalidUserIdError):
        validate_user_id("user/subfolder")
    with pytest.raises(InvalidUserIdError):
        validate_user_id("")
    with pytest.raises(InvalidUserIdError):
        validate_user_id("user*name?")


def test_baseline_creation_and_persistence():
    """Verify fresh baseline profile initialization and saving to JSON."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = BaselineManager(profiles_dir=tmp_dir, min_calibration_checkins=5)
        profile = mgr.create_or_load_profile("participant_01")

        assert profile.user_id == "participant_01"
        assert profile.total_checkins_recorded == 0
        assert not profile.is_calibrated
        assert len(profile.feature_stats) == len(FEATURE_KEYS)

        # Save and verify on disk
        saved_path = mgr.save_profile(profile)
        assert Path(saved_path).is_file()

        # Reload
        reloaded = mgr.load_profile("participant_01")
        assert reloaded.user_id == "participant_01"
        assert reloaded.total_checkins_recorded == 0


def test_calibration_minimum_observations():
    """Verify that is_calibrated stays False until min_calibration_checkins (e.g. 5) is met."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = BaselineManager(profiles_dir=tmp_dir, min_calibration_checkins=5)
        q = create_dummy_quality(is_suitable=True)

        for i in range(1, 5):
            feats = create_dummy_features(vel=0.15 + (i * 0.01))
            prof, _ = mgr.add_calibration_checkin("user_test", feats, q, f"vid_{i}.mp4")
            assert prof.total_checkins_recorded == i
            assert not prof.is_calibrated, f"Should not be calibrated at check-in {i} of 5"

        # 5th check-in: baseline established!
        feats5 = create_dummy_features(vel=0.20)
        prof5, _ = mgr.add_calibration_checkin("user_test", feats5, q, "vid_5.mp4")
        assert prof5.total_checkins_recorded == 5
        assert prof5.is_calibrated


def test_missing_features_never_treated_as_zero():
    """
    Verify that if a feature is None (e.g. blink rate cannot be calculated on short clip),
    it is NOT stored or computed as 0.0 in the baseline mean.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = BaselineManager(profiles_dir=tmp_dir, min_calibration_checkins=3)
        q = create_dummy_quality(is_suitable=True)

        # Session 1: blink rate 30.0
        f1 = create_dummy_features(blink=30.0)
        mgr.add_calibration_checkin("user_blink", f1, q, "v1.mp4")

        # Session 2: blink rate is None (e.g. clip too short)
        f2 = create_dummy_features()
        f2.eyeBlinkRatePm = None
        mgr.add_calibration_checkin("user_blink", f2, q, "v2.mp4")

        # Session 3: blink rate 40.0
        f3 = create_dummy_features(blink=40.0)
        prof, _ = mgr.add_calibration_checkin("user_blink", f3, q, "v3.mp4")

        blink_stat = prof.feature_stats["eyeBlinkRatePm"]
        # Only 2 valid observations: mean should be (30 + 40)/2 = 35.0, NOT (30 + 0 + 40)/3 = 23.33!
        assert blink_stat.count == 2
        assert pytest.approx(blink_stat.mean, rel=1e-3) == 35.0


def test_assessment_without_existing_baseline():
    """Verify ProfileNotFoundError when attempting to assess without an existing baseline profile."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = BaselineManager(profiles_dir=tmp_dir)
        assert not mgr.profile_exists("nonexistent_user")
        with pytest.raises(ProfileNotFoundError):
            mgr.load_profile("nonexistent_user")


def test_assessment_deviations_and_z_scores():
    """Verify calculation of absolute diff, relative change, and standardized z-scores during assessment."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = BaselineManager(profiles_dir=tmp_dir, min_calibration_checkins=3)
        q = create_dummy_quality(is_suitable=True)

        # Calibrate with 3 sessions where facialMovementVelocity = [0.10, 0.20, 0.30]
        # Mean = 0.20, Std = 0.10
        mgr.add_calibration_checkin("user_stats", create_dummy_features(vel=0.10), q, "v1.mp4")
        mgr.add_calibration_checkin("user_stats", create_dummy_features(vel=0.20), q, "v2.mp4")
        prof, _ = mgr.add_calibration_checkin("user_stats", create_dummy_features(vel=0.30), q, "v3.mp4")

        # Assessment check-in with vel = 0.35
        # diff = +0.15, z = +0.15 / 0.10 = +1.50, rel = (+0.15 / 0.20) * 100 = +75%
        assess_feat = create_dummy_features(vel=0.35)
        report = mgr.compare_checkin_with_baseline(prof, assess_feat, q)

        comp = report.comparisons["facialMovementVelocity"]
        assert pytest.approx(comp.baseline_mean, abs=1e-3) == 0.20
        assert pytest.approx(comp.baseline_std, abs=1e-3) == 0.10
        assert pytest.approx(comp.absolute_difference, abs=1e-3) == 0.15
        assert pytest.approx(comp.relative_change_pct, abs=1e-1) == 75.0
        assert pytest.approx(comp.standardized_z, abs=1e-2) == 1.50
        assert "Higher than the observed personal baseline" in comp.interpretation


def test_zero_variance_handling():
    """Verify that zero baseline variance does not cause division by zero or errors."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = BaselineManager(profiles_dir=tmp_dir, min_calibration_checkins=2)
        q = create_dummy_quality(is_suitable=True)

        # 2 identical sessions: smile = 0.50 both times
        mgr.add_calibration_checkin("user_zero_var", create_dummy_features(smile=0.50), q, "v1.mp4")
        prof, _ = mgr.add_calibration_checkin("user_zero_var", create_dummy_features(smile=0.50), q, "v2.mp4")

        smile_stat = prof.feature_stats["smileIntensityProxy"]
        assert smile_stat.std == 0.0

        # Assess with smile = 0.60 (higher, but std is 0.0)
        report = mgr.compare_checkin_with_baseline(prof, create_dummy_features(smile=0.60), q)
        comp = report.comparisons["smileIntensityProxy"]
        # z-score should safely be None instead of raising ZeroDivisionError
        assert comp.standardized_z is None
        assert pytest.approx(comp.absolute_difference, abs=1e-4) == 0.10
        assert "zero baseline variance" in comp.interpretation.lower()


def test_prevention_of_accidental_baseline_update():
    """Verify that running an assessment comparison does NOT modify or update the baseline file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = BaselineManager(profiles_dir=tmp_dir, min_calibration_checkins=2)
        q = create_dummy_quality(is_suitable=True)

        mgr.add_calibration_checkin("user_fixed", create_dummy_features(vel=0.20), q, "v1.mp4")
        prof, _ = mgr.add_calibration_checkin("user_fixed", create_dummy_features(vel=0.20), q, "v2.mp4")

        # Snapshot modification time and history count
        profile_path = mgr.get_profile_path("user_fixed")
        initial_mtime = profile_path.stat().st_mtime_ns
        initial_checkins = prof.total_checkins_recorded

        # Perform multiple assessment comparisons
        for _ in range(5):
            mgr.compare_checkin_with_baseline(prof, create_dummy_features(vel=0.50), q)

        # Baseline file must remain strictly untouched
        reloaded = mgr.load_profile("user_fixed")
        assert reloaded.total_checkins_recorded == initial_checkins
        assert profile_path.stat().st_mtime_ns == initial_mtime


def test_low_quality_checkin_rejected_for_calibration():
    """Verify that a poor quality check-in is rejected from corrupting the calibration profile."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = BaselineManager(profiles_dir=tmp_dir)
        bad_quality = create_dummy_quality(is_suitable=False)

        with pytest.raises(BaselineError, match="Recording quality is insufficient for baseline calibration"):
            mgr.add_calibration_checkin("user_reject", create_dummy_features(), bad_quality, "bad_vid.mp4")


def test_incompatible_or_corrupt_profile():
    """Verify that a corrupted or malformed profile JSON raises IncompatibleProfileError."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        bad_file = Path(tmp_dir) / "corrupt_user.json"
        with open(bad_file, "w") as f:
            f.write("{ invalid json content ...")

        mgr = BaselineManager(profiles_dir=tmp_dir)
        with pytest.raises(IncompatibleProfileError):
            mgr.load_profile("corrupt_user")


def test_non_diagnostic_wording():
    """Verify report limitations string strictly matches non-diagnostic requirement."""
    assert "Stress inference is not validated" in NON_DIAGNOSTIC_LIMITATION
    assert "personal-baseline comparisons only" in NON_DIAGNOSTIC_LIMITATION
