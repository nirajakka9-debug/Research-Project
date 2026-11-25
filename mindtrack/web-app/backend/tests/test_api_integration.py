"""Integration tests for the MindTrack unified FastAPI backend and real AI adapters."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = BACKEND_DIR.parent.parent.parent

# Isolate test database and profile directories cleanly
_TEST_TMP_DIR = Path(tempfile.mkdtemp(prefix="mindtrack_test_"))
os.environ["MINDTRACK_DATA_DIR"] = str(_TEST_TMP_DIR)
os.environ["MINDTRACK_DATABASE_URL"] = f"sqlite:///{(_TEST_TMP_DIR / 'test_mindtrack.db').as_posix()}"

sys.path.insert(0, str(BACKEND_DIR))
from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client: TestClient):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "mindtrack-backend"
    assert data["status"] == "UP"
    assert data["faceAiAvailable"] is True
    assert data["voiceAiAvailable"] is True


def test_questionnaire_only_checkin_and_validation(client: TestClient):
    # Invalid daily affect (6 > 5) must fail validation
    bad_resp = client.post(
        "/api/v1/questionnaire",
        json={
            "phq2Anhedonia": 1,
            "phq2DepressedMood": 0,
            "gad2Nervousness": 1,
            "gad2Worrying": 1,
            "dailyAffectMood": 6,
            "dailyAffectEnergy": 3,
            "dailyAffectStress": 2,
        },
    )
    assert bad_resp.status_code == 422

    # Valid questionnaire-only check-in via unified endpoint
    resp = client.post(
        "/api/v1/checkins",
        json={
            "userId": "demo_user",
            "questionnaire": {
                "phq2Anhedonia": 1,
                "phq2DepressedMood": 0,
                "gad2Nervousness": 1,
                "gad2Worrying": 0,
                "dailyAffectMood": 4,
                "dailyAffectEnergy": 3,
                "dailyAffectStress": 2,
                "sleepQuality": 4,
                "reflectionNote": "Questionnaire only test",
            },
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["availableModalities"] == ["QUESTIONNAIRE"]
    assert set(data["missingModalities"]) == {"FACE", "VOICE"}
    assert data["face"] is None
    assert data["voice"] is None
    assert data["wellnessSummary"]["stressScore"] is None
    assert data["wellnessSummary"]["fusionModelStatus"] == "UNVALIDATED_RESEARCH_FRAMEWORK"


def test_file_validation_rejects_bad_extensions(client: TestClient):
    bad_face = client.post(
        "/api/v1/face/analyze",
        data={"userId": "demo_user", "mode": "single", "maxDuration": "30"},
        files={"file": ("notes.txt", b"not a video", "text/plain")},
    )
    assert bad_face.status_code == 400
    assert "Unsupported video format" in bad_face.json()["detail"]

    bad_voice = client.post(
        "/api/v1/voice/analyze",
        data={"userId": "demo_user", "mode": "single"},
        files={"file": ("clip.mp3", b"not wav", "audio/mpeg")},
    )
    assert bad_voice.status_code == 400
    assert "Unsupported audio format" in bad_voice.json()["detail"]

    bad_user = client.post(
        "/api/v1/face/analyze",
        data={"userId": "../../etc/passwd", "mode": "single", "maxDuration": "30"},
        files={"file": ("clip.mp4", b"dummy", "video/mp4")},
    )
    assert bad_user.status_code == 400


def test_real_face_voice_and_multimodal_checkin_flow(client: TestClient):
    demo_video = WORKSPACE_ROOT / "Face ai" / "videos" / "demo.mp4"
    sample_wav = WORKSPACE_ROOT / "Voice ai - Copy" / "test_data" / "real_speech.wav"
    assert demo_video.is_file(), f"Missing demo video: {demo_video}"
    assert sample_wav.is_file(), f"Missing real speech wav: {sample_wav}"

    # 1. Calibrate Face AI once for isolated user 'pytest_user'
    with open(demo_video, "rb") as vf:
        face_cal = client.post(
            "/api/v1/face/analyze",
            data={"userId": "pytest_user", "mode": "calibrate", "maxDuration": "30"},
            files={"file": ("demo.mp4", vf, "video/mp4")},
        )
    assert face_cal.status_code == 200, face_cal.text
    face_cal_data = face_cal.json()
    assert face_cal_data["result"]["quality"]["usable_frames"] > 0
    assert face_cal_data["result"]["features"]["facialMovementVelocity"] is not None
    assert face_cal_data["result"]["calibration_status"]["total_checkins"] == 1

    # 2. Assess Face AI against that personal baseline
    with open(demo_video, "rb") as vf:
        face_assess = client.post(
            "/api/v1/face/analyze",
            data={"userId": "pytest_user", "mode": "assess", "maxDuration": "30"},
            files={"file": ("demo.mp4", vf, "video/mp4")},
        )
    assert face_assess.status_code == 200, face_assess.text
    face_assess_data = face_assess.json()
    assert "baseline_comparison" in face_assess_data["result"]
    face_run_id = face_assess_data["runId"]

    # 3. Calibrate & analyze Voice AI using real_speech.wav
    with open(sample_wav, "rb") as af:
        voice_cal = client.post(
            "/api/v1/voice/analyze",
            data={"userId": "pytest_user", "mode": "calibrate"},
            files={"file": ("real_speech.wav", af, "audio/wav")},
        )
    assert voice_cal.status_code == 200, voice_cal.text
    voice_data = voice_cal.json()
    assert voice_data["result"]["features"]["speakingRateWpm"] > 50
    assert voice_data["result"]["features"]["pitchMeanHz"] > 75
    voice_run_id = voice_data["runId"]

    # 4. Submit unified trimodal check-in linking both real runs
    checkin_resp = client.post(
        "/api/v1/checkins",
        json={
            "userId": "pytest_user",
            "questionnaire": {
                "phq2Anhedonia": 0,
                "phq2DepressedMood": 1,
                "gad2Nervousness": 1,
                "gad2Worrying": 1,
                "dailyAffectMood": 4,
                "dailyAffectEnergy": 4,
                "dailyAffectStress": 2,
            },
            "faceAnalysisRunId": face_run_id,
            "voiceAnalysisRunId": voice_run_id,
            "notes": "Full multimodal integration test",
        },
    )
    assert checkin_resp.status_code == 201, checkin_resp.text
    checkin = checkin_resp.json()
    assert set(checkin["availableModalities"]) == {"QUESTIONNAIRE", "FACE", "VOICE"}
    assert checkin["missingModalities"] == []
    assert checkin["face"]["features"]["eyeBlinkRatePm"] is not None
    assert checkin["voice"]["features"]["speakingRateWpm"] > 50

    # 5. Verify dashboard & baselines reflect isolated pytest_user data
    dash = client.get("/api/v1/dashboard/pytest_user").json()
    assert dash["todayStatus"]["totalCheckins"] == 1
    assert dash["baselines"]["face"]["totalRecorded"] == 1
    assert dash["baselines"]["voice"]["observationCount"] == 1
    assert len(dash["trends"]) == 1

    # Demo user must stay isolated from pytest_user
    demo_baselines = client.get("/api/v1/baselines/demo_user").json()
    assert demo_baselines["face"]["total_checkins_recorded"] == 0
    assert demo_baselines["voice"]["observation_count"] == 0
