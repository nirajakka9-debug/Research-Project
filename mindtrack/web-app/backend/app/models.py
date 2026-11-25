"""SQLAlchemy ORM models aligned with the MindTrack multimodal schema."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(64), default="ROLE_USER", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    checkins: Mapped[list["CheckinSessionModel"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class AnalysisRunModel(Base):
    """Stores executed real Face AI / Voice AI pipeline runs before or alongside check-ins."""

    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    modality: Mapped[str] = mapped_column(String(32), nullable=False)  # FACE | VOICE
    mode: Mapped[str] = mapped_column(String(32), nullable=False)      # single | calibrate | assess
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_reliable: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class CheckinSessionModel(Base):
    __tablename__ = "checkin_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="COMPLETED", nullable=False)
    available_modalities: Mapped[str] = mapped_column(String(128), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    user: Mapped["UserModel"] = relationship(back_populates="checkins")
    questionnaire: Mapped[Optional["QuestionnaireResponseModel"]] = relationship(
        back_populates="checkin",
        uselist=False,
        cascade="all, delete-orphan",
    )
    face_features: Mapped[Optional["FaceFeatureModel"]] = relationship(
        back_populates="checkin",
        uselist=False,
        cascade="all, delete-orphan",
    )
    voice_features: Mapped[Optional["VoiceFeatureModel"]] = relationship(
        back_populates="checkin",
        uselist=False,
        cascade="all, delete-orphan",
    )
    wellness_summary: Mapped[Optional["WellnessSummaryModel"]] = relationship(
        back_populates="checkin",
        uselist=False,
        cascade="all, delete-orphan",
    )


class QuestionnaireResponseModel(Base):
    __tablename__ = "questionnaire_responses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    checkin_id: Mapped[str] = mapped_column(
        ForeignKey("checkin_sessions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    phq2_anhedonia: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    phq2_depressed_mood: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gad2_nervousness: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gad2_worrying: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    daily_affect_mood: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_affect_energy: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_affect_stress: Mapped[int] = mapped_column(Integer, nullable=False)
    sleep_quality: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reflection_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    checkin: Mapped["CheckinSessionModel"] = relationship(back_populates="questionnaire")


class FaceFeatureModel(Base):
    __tablename__ = "face_features"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    checkin_id: Mapped[str] = mapped_column(
        ForeignKey("checkin_sessions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    analysis_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_frames: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    usable_frames: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    detection_coverage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_reliable: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    is_suitable_for_baseline: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    facial_movement_velocity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eye_blink_rate_pm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    head_pose_jitter_std: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    smile_intensity_proxy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    brow_furrow_proxy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    checkin: Mapped["CheckinSessionModel"] = relationship(back_populates="face_features")


class VoiceFeatureModel(Base):
    __tablename__ = "voice_features"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    checkin_id: Mapped[str] = mapped_column(
        ForeignKey("checkin_sessions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    analysis_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sample_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speaking_rate_wpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_pause_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mean_pause_duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longest_pause_duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speech_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speech_duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    silence_duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pitch_mean_hz: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pitch_std_dev_hz: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pitch_range_hz: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    energy_mean_rms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    energy_std_dev: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    technical_deviation_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    checkin: Mapped["CheckinSessionModel"] = relationship(back_populates="voice_features")


class WellnessSummaryModel(Base):
    """Stores transparent multimodal summary, baseline context, and missing-modality tracking."""

    __tablename__ = "wellness_summaries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    checkin_id: Mapped[str] = mapped_column(
        ForeignKey("checkin_sessions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    available_modalities: Mapped[str] = mapped_column(String(128), nullable=False)
    missing_modalities: Mapped[str] = mapped_column(String(128), nullable=False)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    checkin: Mapped["CheckinSessionModel"] = relationship(back_populates="wellness_summary")
