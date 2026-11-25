"""MindTrack FastAPI Backend Application.

Integrates:
- Check-in persistence & questionnaire endpoints (SQLite via SQLAlchemy)
- Real Face ai Python pipeline adapter (MediaPipe + OpenCV)
- Real Voice ai - Copy Python pipeline adapter (DSP acoustic analysis)
- Per-user baseline isolation and longitudinal trend aggregation
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from .adapters.face_adapter import (
    FaceAnalysisError,
    read_face_baseline,
    reset_face_baseline,
    run_face_analyzer,
    save_validated_video_upload,
)
from .adapters.voice_adapter import (
    VoiceAnalysisError,
    read_voice_baseline,
    reset_voice_baseline,
    run_voice_analyzer,
    save_validated_audio_upload,
)
from .config import (
    DEFAULT_FACE_MAX_DURATION_SEC,
    FACE_AI_DIR,
    NON_DIAGNOSTIC_NOTICE,
    VOICE_AI_DIR,
    validate_safe_user_id,
)
from .database import Base, SessionLocal, engine, get_db
from .models import (
    AnalysisRunModel,
    CheckinSessionModel,
    FaceFeatureModel,
    QuestionnaireResponseModel,
    UserModel,
    VoiceFeatureModel,
    WellnessSummaryModel,
)
from .schemas import CheckinCreateRequest, QuestionnaireRequest, UserCreateRequest
from .services.wellness_engine import (
    ALL_MODALITIES,
    build_transparent_wellness_summary,
    compute_questionnaire_baseline_stats,
    compute_questionnaire_summary,
)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _ensure_default_user(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="MindTrack Unified Wellness API",
    version="1.0.0",
    description=(
        "Non-diagnostic longitudinal wellness monitoring backend unifying questionnaires, "
        "Face ai (MediaPipe facial behaviour analysis), and Voice ai (acoustic signal processing)."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _as_utc(dt: datetime) -> datetime:
    """SQLite drops tzinfo on DateTime columns; normalize naive DB timestamps to UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _iso_utc(dt: datetime) -> str:
    return _as_utc(dt).isoformat()


def _ensure_default_user(db: Session) -> None:
    if db.get(UserModel, "demo_user") is None:
        db.add(
            UserModel(
                id="demo_user",
                email="demo_user@mindtrack.local",
                full_name="Demo Participant",
                role="ROLE_USER",
            )
        )
        db.commit()


def _get_or_create_user(db: Session, user_id: str) -> UserModel:
    clean_id = validate_safe_user_id(user_id)
    user = db.get(UserModel, clean_id)
    if user is None:
        user = UserModel(
            id=clean_id,
            email=f"{clean_id}@mindtrack.local",
            full_name=clean_id.replace("_", " ").replace("-", " ").title(),
            role="ROLE_USER",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _serialize_checkin(session: CheckinSessionModel) -> Dict[str, Any]:
    modalities = [m for m in session.available_modalities.split(",") if m]
    missing = [m for m in ALL_MODALITIES if m not in modalities]
    q_data = compute_questionnaire_summary(session.questionnaire)

    face_data = None
    if session.face_features is not None:
        f = session.face_features
        face_raw = json.loads(f.raw_json)
        face_data = {
            "id": f.id,
            "analysisRunId": f.analysis_run_id,
            "mode": f.mode,
            "filename": f.filename,
            "durationSec": f.duration_sec,
            "totalFrames": f.total_frames,
            "usableFrames": f.usable_frames,
            "detectionCoverage": f.detection_coverage,
            "qualityScore": f.quality_score,
            "isReliable": f.is_reliable,
            "isSuitableForBaseline": f.is_suitable_for_baseline,
            "features": {
                "facialMovementVelocity": f.facial_movement_velocity,
                "eyeBlinkRatePm": f.eye_blink_rate_pm,
                "headPoseJitterStd": f.head_pose_jitter_std,
                "smileIntensityProxy": f.smile_intensity_proxy,
                "browFurrowProxy": f.brow_furrow_proxy,
            },
            "raw": face_raw,
        }

    voice_data = None
    if session.voice_features is not None:
        v = session.voice_features
        voice_raw = json.loads(v.raw_json)
        voice_data = {
            "id": v.id,
            "analysisRunId": v.analysis_run_id,
            "mode": v.mode,
            "filename": v.filename,
            "durationSec": v.duration_sec,
            "sampleRate": v.sample_rate,
            "qualityScore": v.quality_score,
            "technicalDeviationScore": v.technical_deviation_score,
            "features": voice_raw.get("features", {}),
            "voicePattern": voice_raw.get("voicePattern"),
            "qualityWarnings": voice_raw.get("qualityWarnings", []),
            "raw": voice_raw,
        }

    summary_data = (
        json.loads(session.wellness_summary.summary_json)
        if session.wellness_summary is not None
        else None
    )

    return {
        "id": session.id,
        "userId": session.user_id,
        "sessionTimestamp": _iso_utc(session.session_timestamp),
        "status": session.status,
        "availableModalities": modalities,
        "missingModalities": missing,
        "notes": session.notes,
        "questionnaire": q_data,
        "face": face_data,
        "voice": voice_data,
        "wellnessSummary": summary_data,
    }


def _attach_face_run(
    db: Session,
    checkin: CheckinSessionModel,
    run: AnalysisRunModel,
) -> FaceFeatureModel:
    raw = json.loads(run.raw_json)
    meta = raw.get("video_metadata", {})
    qual = raw.get("quality", {})
    feats = raw.get("features", {})
    model = FaceFeatureModel(
        checkin_id=checkin.id,
        analysis_run_id=run.id,
        mode=run.mode,
        filename=run.original_filename,
        duration_sec=meta.get("duration_sec"),
        total_frames=qual.get("total_frames"),
        usable_frames=qual.get("usable_frames"),
        detection_coverage=qual.get("detection_coverage"),
        quality_score=qual.get("quality_score"),
        is_reliable=qual.get("is_reliable"),
        is_suitable_for_baseline=qual.get("is_suitable_for_baseline"),
        facial_movement_velocity=feats.get("facialMovementVelocity"),
        eye_blink_rate_pm=feats.get("eyeBlinkRatePm"),
        head_pose_jitter_std=feats.get("headPoseJitterStd"),
        smile_intensity_proxy=feats.get("smileIntensityProxy"),
        brow_furrow_proxy=feats.get("browFurrowProxy"),
        raw_json=run.raw_json,
    )
    db.add(model)
    return model


def _attach_voice_run(
    db: Session,
    checkin: CheckinSessionModel,
    run: AnalysisRunModel,
) -> VoiceFeatureModel:
    raw = json.loads(run.raw_json)
    audio = raw.get("audio", {})
    feats = raw.get("features", {})
    vp = raw.get("voicePattern") or {}
    model = VoiceFeatureModel(
        checkin_id=checkin.id,
        analysis_run_id=run.id,
        mode=run.mode,
        filename=run.original_filename,
        duration_sec=audio.get("durationSec"),
        sample_rate=audio.get("sampleRate"),
        quality_score=raw.get("qualityScore"),
        speaking_rate_wpm=feats.get("speakingRateWpm"),
        total_pause_count=feats.get("totalPauseCount"),
        mean_pause_duration_ms=feats.get("meanPauseDurationMs"),
        longest_pause_duration_ms=feats.get("longestPauseDurationMs"),
        speech_ratio=feats.get("speechRatio"),
        speech_duration_sec=feats.get("speechDurationSec"),
        silence_duration_sec=feats.get("silenceDurationSec"),
        pitch_mean_hz=feats.get("pitchMeanHz"),
        pitch_std_dev_hz=feats.get("pitchStdDevHz"),
        pitch_range_hz=feats.get("pitchRangeHz"),
        energy_mean_rms=feats.get("energyMeanRms"),
        energy_std_dev=feats.get("energyStdDev"),
        technical_deviation_score=vp.get("technicalDeviationScore"),
        raw_json=run.raw_json,
    )
    db.add(model)
    return model


@app.get("/api/v1/health")
def health_check(db: Session = Depends(get_db)) -> Dict[str, Any]:
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    face_ready = (FACE_AI_DIR / "main.py").is_file() and (FACE_AI_DIR / "face_landmarker.task").is_file()
    voice_ready = (VOICE_AI_DIR / "inference" / "pipeline.py").is_file()

    return {
        "service": "mindtrack-backend",
        "runtime": "FastAPI + SQLite (MVP adapter)",
        "status": "UP" if db_ok else "DEGRADED",
        "database": "CONNECTED (SQLite)" if db_ok else "DISCONNECTED",
        "faceAiAvailable": face_ready,
        "voiceAiAvailable": voice_ready,
        "disclaimer": NON_DIAGNOSTIC_NOTICE,
    }


@app.get("/api/v1/users")
def list_users(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    _ensure_default_user(db)
    users = db.query(UserModel).order_by(UserModel.created_at.asc()).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "fullName": u.full_name,
            "role": u.role,
            "createdAt": _iso_utc(u.created_at),
        }
        for u in users
    ]


@app.post("/api/v1/users", status_code=201)
def create_user(payload: UserCreateRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    existing = db.get(UserModel, payload.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"User profile '{payload.id}' already exists.")
    email_taken = db.query(UserModel).filter(UserModel.email == payload.email).first()
    if email_taken is not None:
        raise HTTPException(status_code=409, detail=f"Email '{payload.email}' is already registered.")
    user = UserModel(id=payload.id, email=payload.email, full_name=payload.fullName)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "fullName": user.full_name,
        "role": user.role,
        "createdAt": _iso_utc(user.created_at),
    }


@app.post("/api/v1/face/analyze")
async def analyze_face_video(
    file: UploadFile = File(...),
    userId: str = Form("demo_user"),
    mode: str = Form("single"),
    maxDuration: float = Form(DEFAULT_FACE_MAX_DURATION_SEC),
    updateBaseline: bool = Form(False),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        clean_user_id = validate_safe_user_id(userId)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _get_or_create_user(db, clean_user_id)

    saved_path = None
    try:
        saved_path, original_name = await save_validated_video_upload(file)
        result = run_face_analyzer(
            video_path=saved_path,
            user_id=clean_user_id,
            mode=mode,
            max_duration=maxDuration,
            update_baseline=updateBaseline,
        )
    except FaceAnalysisError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    finally:
        if saved_path is not None:
            saved_path.unlink(missing_ok=True)

    quality = result.get("quality", {})
    run = AnalysisRunModel(
        id=str(uuid.uuid4()),
        user_id=clean_user_id,
        modality="FACE",
        mode=mode,
        original_filename=original_name,
        quality_score=quality.get("quality_score"),
        is_reliable=quality.get("is_reliable"),
        raw_json=json.dumps(result),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return {
        "runId": run.id,
        "userId": clean_user_id,
        "modality": "FACE",
        "mode": mode,
        "filename": original_name,
        "qualityScore": run.quality_score,
        "isReliable": run.is_reliable,
        "createdAt": _iso_utc(run.created_at),
        "result": result,
        "disclaimer": NON_DIAGNOSTIC_NOTICE,
    }


@app.post("/api/v1/voice/analyze")
async def analyze_voice_audio(
    file: UploadFile = File(...),
    userId: str = Form("demo_user"),
    mode: str = Form("single"),
    updateBaseline: bool = Form(False),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        clean_user_id = validate_safe_user_id(userId)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _get_or_create_user(db, clean_user_id)

    saved_path = None
    try:
        saved_path, original_name = await save_validated_audio_upload(file)
        result = run_voice_analyzer(
            wav_path=saved_path,
            user_id=clean_user_id,
            mode=mode,
            update_baseline=updateBaseline,
        )
    except VoiceAnalysisError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    finally:
        if saved_path is not None:
            saved_path.unlink(missing_ok=True)

    q_score = result.get("qualityScore")
    is_reliable = (float(q_score) >= 0.55) if q_score is not None else None
    run = AnalysisRunModel(
        id=str(uuid.uuid4()),
        user_id=clean_user_id,
        modality="VOICE",
        mode=mode,
        original_filename=original_name,
        quality_score=q_score,
        is_reliable=is_reliable,
        raw_json=json.dumps(result),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return {
        "runId": run.id,
        "userId": clean_user_id,
        "modality": "VOICE",
        "mode": mode,
        "filename": original_name,
        "qualityScore": run.quality_score,
        "isReliable": run.is_reliable,
        "createdAt": _iso_utc(run.created_at),
        "result": result,
        "disclaimer": NON_DIAGNOSTIC_NOTICE,
    }


@app.get("/api/v1/analysis-runs/{user_id}")
def list_recent_analysis_runs(
    user_id: str,
    modality: Optional[str] = Query(default=None),
    limit: int = Query(default=15, ge=1, le=50),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    try:
        clean_id = validate_safe_user_id(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    query = db.query(AnalysisRunModel).filter(AnalysisRunModel.user_id == clean_id)
    if modality:
        query = query.filter(AnalysisRunModel.modality == modality.upper())
    runs = query.order_by(AnalysisRunModel.created_at.desc()).limit(limit).all()
    return [
        {
            "runId": r.id,
            "userId": r.user_id,
            "modality": r.modality,
            "mode": r.mode,
            "filename": r.original_filename,
            "qualityScore": r.quality_score,
            "isReliable": r.is_reliable,
            "createdAt": _iso_utc(r.created_at),
            "result": json.loads(r.raw_json),
        }
        for r in runs
    ]


@app.post("/api/v1/questionnaire", status_code=201)
def submit_questionnaire_compat(
    payload: QuestionnaireRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Compatibility endpoint matching the QuestionnaireApiTest contract."""
    user = _get_or_create_user(db, payload.userId or "demo_user")

    if payload.checkinId:
        checkin = db.get(CheckinSessionModel, payload.checkinId)
        if checkin is None:
            raise HTTPException(status_code=404, detail=f"Check-in session '{payload.checkinId}' not found.")
        modalities = [m for m in checkin.available_modalities.split(",") if m]
        if "QUESTIONNAIRE" not in modalities:
            modalities.insert(0, "QUESTIONNAIRE")
            checkin.available_modalities = ",".join(modalities)
    else:
        checkin = CheckinSessionModel(
            user_id=user.id,
            status="COMPLETED",
            available_modalities="QUESTIONNAIRE",
        )
        db.add(checkin)
        db.flush()

    existing_q = (
        db.query(QuestionnaireResponseModel)
        .filter(QuestionnaireResponseModel.checkin_id == checkin.id)
        .first()
    )
    if existing_q is not None:
        existing_q.phq2_anhedonia = payload.phq2Anhedonia
        existing_q.phq2_depressed_mood = payload.phq2DepressedMood
        existing_q.gad2_nervousness = payload.gad2Nervousness
        existing_q.gad2_worrying = payload.gad2Worrying
        existing_q.daily_affect_mood = payload.dailyAffectMood
        existing_q.daily_affect_energy = payload.dailyAffectEnergy
        existing_q.daily_affect_stress = payload.dailyAffectStress
        existing_q.sleep_quality = payload.sleepQuality
        existing_q.reflection_note = payload.reflectionNote
        q_row = existing_q
    else:
        q_row = QuestionnaireResponseModel(
            checkin_id=checkin.id,
            phq2_anhedonia=payload.phq2Anhedonia,
            phq2_depressed_mood=payload.phq2DepressedMood,
            gad2_nervousness=payload.gad2Nervousness,
            gad2_worrying=payload.gad2Worrying,
            daily_affect_mood=payload.dailyAffectMood,
            daily_affect_energy=payload.dailyAffectEnergy,
            daily_affect_stress=payload.dailyAffectStress,
            sleep_quality=payload.sleepQuality,
            reflection_note=payload.reflectionNote,
        )
        db.add(q_row)

    db.commit()
    db.refresh(q_row)
    return {
        "status": "SUCCESS",
        "checkinId": checkin.id,
        "phq2Anhedonia": q_row.phq2_anhedonia,
        "phq2DepressedMood": q_row.phq2_depressed_mood,
        "gad2Nervousness": q_row.gad2_nervousness,
        "gad2Worrying": q_row.gad2_worrying,
        "dailyAffectMood": q_row.daily_affect_mood,
        "dailyAffectEnergy": q_row.daily_affect_energy,
        "dailyAffectStress": q_row.daily_affect_stress,
        "sleepQuality": q_row.sleep_quality,
        "reflectionNote": q_row.reflection_note,
        "disclaimer": NON_DIAGNOSTIC_NOTICE,
    }


@app.post("/api/v1/checkins/{checkin_id}/questionnaire", status_code=201)
def submit_questionnaire_for_checkin(
    checkin_id: str,
    payload: QuestionnaireRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    payload.checkinId = checkin_id
    return submit_questionnaire_compat(payload, db)


@app.get("/api/v1/questionnaire/{checkin_id}")
def get_questionnaire_by_checkin(checkin_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    q_row = (
        db.query(QuestionnaireResponseModel)
        .filter(QuestionnaireResponseModel.checkin_id == checkin_id)
        .first()
    )
    if q_row is None:
        raise HTTPException(status_code=404, detail=f"Questionnaire not found for check-in '{checkin_id}'.")
    return {
        "checkinId": q_row.checkin_id,
        "phq2Anhedonia": q_row.phq2_anhedonia,
        "phq2DepressedMood": q_row.phq2_depressed_mood,
        "gad2Nervousness": q_row.gad2_nervousness,
        "gad2Worrying": q_row.gad2_worrying,
        "dailyAffectMood": q_row.daily_affect_mood,
        "dailyAffectEnergy": q_row.daily_affect_energy,
        "dailyAffectStress": q_row.daily_affect_stress,
        "sleepQuality": q_row.sleep_quality,
        "reflectionNote": q_row.reflection_note,
        "disclaimer": NON_DIAGNOSTIC_NOTICE,
    }


@app.post("/api/v1/checkins", status_code=201)
def create_unified_checkin(
    payload: CheckinCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    if (
        payload.questionnaire is None
        and payload.faceAnalysisRunId is None
        and payload.voiceAnalysisRunId is None
    ):
        raise HTTPException(
            status_code=400,
            detail="A check-in requires at least one completed modality (Questionnaire, Facial AI, or Voice AI).",
        )

    user = _get_or_create_user(db, payload.userId)
    modalities: List[str] = []

    face_run: Optional[AnalysisRunModel] = None
    if payload.faceAnalysisRunId:
        face_run = db.get(AnalysisRunModel, payload.faceAnalysisRunId)
        if face_run is None or face_run.modality != "FACE" or face_run.user_id != user.id:
            raise HTTPException(
                status_code=400,
                detail="Invalid or mismatched facial analysis run ID for this user.",
            )

    voice_run: Optional[AnalysisRunModel] = None
    if payload.voiceAnalysisRunId:
        voice_run = db.get(AnalysisRunModel, payload.voiceAnalysisRunId)
        if voice_run is None or voice_run.modality != "VOICE" or voice_run.user_id != user.id:
            raise HTTPException(
                status_code=400,
                detail="Invalid or mismatched voice analysis run ID for this user.",
            )

    if payload.questionnaire is not None:
        modalities.append("QUESTIONNAIRE")
    if face_run is not None:
        modalities.append("FACE")
    if voice_run is not None:
        modalities.append("VOICE")

    checkin = CheckinSessionModel(
        id=str(uuid.uuid4()),
        user_id=user.id,
        status="COMPLETED",
        available_modalities=",".join(modalities),
        notes=payload.notes,
    )
    db.add(checkin)
    db.flush()

    q_row: Optional[QuestionnaireResponseModel] = None
    if payload.questionnaire is not None:
        q = payload.questionnaire
        q_row = QuestionnaireResponseModel(
            checkin_id=checkin.id,
            phq2_anhedonia=q.phq2Anhedonia,
            phq2_depressed_mood=q.phq2DepressedMood,
            gad2_nervousness=q.gad2Nervousness,
            gad2_worrying=q.gad2Worrying,
            daily_affect_mood=q.dailyAffectMood,
            daily_affect_energy=q.dailyAffectEnergy,
            daily_affect_stress=q.dailyAffectStress,
            sleep_quality=q.sleepQuality,
            reflection_note=q.reflectionNote,
        )
        db.add(q_row)

    face_row = _attach_face_run(db, checkin, face_run) if face_run is not None else None
    voice_row = _attach_voice_run(db, checkin, voice_run) if voice_run is not None else None

    summary_dict = build_transparent_wellness_summary(
        available_modalities=modalities,
        questionnaire=q_row,
        face=face_row,
        voice=voice_row,
    )
    summary_row = WellnessSummaryModel(
        checkin_id=checkin.id,
        user_id=user.id,
        available_modalities=",".join(modalities),
        missing_modalities=",".join(summary_dict["missingModalities"]),
        summary_json=json.dumps(summary_dict),
    )
    db.add(summary_row)
    db.commit()

    saved = (
        db.query(CheckinSessionModel)
        .options(
            joinedload(CheckinSessionModel.questionnaire),
            joinedload(CheckinSessionModel.face_features),
            joinedload(CheckinSessionModel.voice_features),
            joinedload(CheckinSessionModel.wellness_summary),
        )
        .filter(CheckinSessionModel.id == checkin.id)
        .one()
    )
    return _serialize_checkin(saved)


@app.get("/api/v1/checkins")
def list_checkins(
    userId: str = Query("demo_user"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    try:
        clean_id = validate_safe_user_id(userId)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    sessions = (
        db.query(CheckinSessionModel)
        .options(
            joinedload(CheckinSessionModel.questionnaire),
            joinedload(CheckinSessionModel.face_features),
            joinedload(CheckinSessionModel.voice_features),
            joinedload(CheckinSessionModel.wellness_summary),
        )
        .filter(CheckinSessionModel.user_id == clean_id)
        .order_by(CheckinSessionModel.session_timestamp.desc())
        .all()
    )
    return [_serialize_checkin(s) for s in sessions]


@app.get("/api/v1/checkins/{checkin_id}")
def get_checkin_detail(checkin_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    session = (
        db.query(CheckinSessionModel)
        .options(
            joinedload(CheckinSessionModel.questionnaire),
            joinedload(CheckinSessionModel.face_features),
            joinedload(CheckinSessionModel.voice_features),
            joinedload(CheckinSessionModel.wellness_summary),
        )
        .filter(CheckinSessionModel.id == checkin_id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail=f"Check-in '{checkin_id}' not found.")
    return _serialize_checkin(session)


@app.delete("/api/v1/checkins/{checkin_id}")
def delete_checkin(checkin_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    session = db.get(CheckinSessionModel, checkin_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Check-in '{checkin_id}' not found.")
    db.delete(session)
    db.commit()
    return {"deleted": True, "checkinId": checkin_id}


@app.get("/api/v1/baselines/{user_id}")
def get_user_baselines(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        clean_id = validate_safe_user_id(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    face_baseline = read_face_baseline(clean_id)
    voice_baseline = read_voice_baseline(clean_id)
    sessions = (
        db.query(CheckinSessionModel)
        .options(joinedload(CheckinSessionModel.questionnaire))
        .filter(CheckinSessionModel.user_id == clean_id)
        .order_by(CheckinSessionModel.session_timestamp.asc())
        .all()
    )
    questionnaire_stats = compute_questionnaire_baseline_stats(sessions)

    return {
        "userId": clean_id,
        "face": face_baseline,
        "voice": voice_baseline,
        "questionnaire": {
            "sessionCount": sum(1 for s in sessions if s.questionnaire is not None),
            "stats": questionnaire_stats,
        },
        "disclaimer": NON_DIAGNOSTIC_NOTICE,
    }


@app.delete("/api/v1/baselines/{user_id}/{modality}")
def delete_user_baseline(user_id: str, modality: str) -> Dict[str, Any]:
    try:
        clean_id = validate_safe_user_id(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    mod = modality.lower()
    if mod == "face":
        removed = reset_face_baseline(clean_id)
    elif mod == "voice":
        removed = reset_voice_baseline(clean_id)
    else:
        raise HTTPException(status_code=400, detail="Modality must be 'face' or 'voice'.")
    return {"userId": clean_id, "modality": mod, "reset": removed}


@app.get("/api/v1/dashboard/{user_id}")
def get_dashboard_overview(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        clean_id = validate_safe_user_id(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = _get_or_create_user(db, clean_id)
    sessions = (
        db.query(CheckinSessionModel)
        .options(
            joinedload(CheckinSessionModel.questionnaire),
            joinedload(CheckinSessionModel.face_features),
            joinedload(CheckinSessionModel.voice_features),
            joinedload(CheckinSessionModel.wellness_summary),
        )
        .filter(CheckinSessionModel.user_id == clean_id)
        .order_by(CheckinSessionModel.session_timestamp.desc())
        .all()
    )

    today_local = datetime.now().astimezone().date()
    checked_in_today = any(
        _as_utc(s.session_timestamp).astimezone().date() == today_local
        for s in sessions
    )

    latest_checkin = _serialize_checkin(sessions[0]) if sessions else None
    latest_q = next((_serialize_checkin(s) for s in sessions if s.questionnaire is not None), None)
    latest_face = next((_serialize_checkin(s) for s in sessions if s.face_features is not None), None)
    latest_voice = next((_serialize_checkin(s) for s in sessions if s.voice_features is not None), None)

    recent_runs = (
        db.query(AnalysisRunModel)
        .filter(AnalysisRunModel.user_id == clean_id)
        .order_by(AnalysisRunModel.created_at.desc())
        .limit(10)
        .all()
    )

    face_baseline = read_face_baseline(clean_id)
    voice_baseline = read_voice_baseline(clean_id)

    # Real chronological trend points (never fabricated)
    chronological = list(reversed(sessions))
    trends: List[Dict[str, Any]] = []
    for s in chronological:
        q = s.questionnaire
        f = s.face_features
        v = s.voice_features
        modalities = [m for m in s.available_modalities.split(",") if m]
        trends.append(
            {
                "checkinId": s.id,
                "timestamp": _iso_utc(s.session_timestamp),
                "label": _as_utc(s.session_timestamp).astimezone().strftime("%b %d %H:%M"),
                "availableModalities": modalities,
                "mood": q.daily_affect_mood if q else None,
                "energy": q.daily_affect_energy if q else None,
                "stress": q.daily_affect_stress if q else None,
                "phq2Total": (
                    (q.phq2_anhedonia + q.phq2_depressed_mood)
                    if q and q.phq2_anhedonia is not None and q.phq2_depressed_mood is not None
                    else None
                ),
                "gad2Total": (
                    (q.gad2_nervousness + q.gad2_worrying)
                    if q and q.gad2_nervousness is not None and q.gad2_worrying is not None
                    else None
                ),
                "facialMovementVelocity": f.facial_movement_velocity if f else None,
                "eyeBlinkRatePm": f.eye_blink_rate_pm if f else None,
                "headPoseJitterStd": f.head_pose_jitter_std if f else None,
                "smileIntensityProxy": f.smile_intensity_proxy if f else None,
                "browFurrowProxy": f.brow_furrow_proxy if f else None,
                "faceQualityScore": f.quality_score if f else None,
                "speakingRateWpm": v.speaking_rate_wpm if v else None,
                "pitchMeanHz": v.pitch_mean_hz if v else None,
                "meanPauseDurationMs": v.mean_pause_duration_ms if v else None,
                "speechRatio": v.speech_ratio if v else None,
                "energyMeanRms": v.energy_mean_rms if v else None,
                "voiceQualityScore": v.quality_score if v else None,
            }
        )

    return {
        "user": {
            "id": user.id,
            "fullName": user.full_name,
            "email": user.email,
        },
        "todayStatus": {
            "checkedInToday": checked_in_today,
            "totalCheckins": len(sessions),
            "lastCheckinAt": _iso_utc(sessions[0].session_timestamp) if sessions else None,
        },
        "latestCheckin": latest_checkin,
        "latestQuestionnaire": latest_q["questionnaire"] if latest_q else None,
        "latestFace": latest_face["face"] if latest_face else None,
        "latestVoice": latest_voice["voice"] if latest_voice else None,
        "baselines": {
            "face": {
                "isCalibrated": face_baseline.get("is_calibrated", False),
                "totalRecorded": face_baseline.get("total_checkins_recorded", 0),
                "minRequired": face_baseline.get("min_calibration_checkins", 5),
                "featureStats": face_baseline.get("feature_stats", {}),
            },
            "voice": {
                "isEstablished": voice_baseline.get("is_established", False),
                "observationCount": voice_baseline.get("observation_count", 0),
                "minRequired": voice_baseline.get("min_observations", 3),
                "stats": voice_baseline.get("stats", {}),
            },
            "questionnaire": compute_questionnaire_baseline_stats(sessions),
        },
        "recentCheckins": [_serialize_checkin(s) for s in sessions[:6]],
        "recentAnalysisRuns": [
            {
                "runId": r.id,
                "modality": r.modality,
                "mode": r.mode,
                "filename": r.original_filename,
                "qualityScore": r.quality_score,
                "isReliable": r.is_reliable,
                "createdAt": _iso_utc(r.created_at),
            }
            for r in recent_runs
        ],
        "trends": trends,
        "disclaimer": NON_DIAGNOSTIC_NOTICE,
    }
