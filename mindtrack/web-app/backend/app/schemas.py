"""Pydantic request and response schemas for the MindTrack API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from .config import validate_safe_user_id


class UserCreateRequest(BaseModel):
    id: str = Field(..., min_length=1, max_length=64, description="URL-safe participant identifier")
    fullName: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=3, max_length=255)

    @field_validator("id")
    @classmethod
    def check_safe_id(cls, value: str) -> str:
        return validate_safe_user_id(value)


class UserResponse(BaseModel):
    id: str
    email: str
    fullName: str
    role: str
    createdAt: str


class QuestionnaireRequest(BaseModel):
    checkinId: Optional[str] = None
    userId: Optional[str] = "demo_user"
    phq2Anhedonia: Optional[int] = Field(default=None, ge=0, le=3)
    phq2DepressedMood: Optional[int] = Field(default=None, ge=0, le=3)
    gad2Nervousness: Optional[int] = Field(default=None, ge=0, le=3)
    gad2Worrying: Optional[int] = Field(default=None, ge=0, le=3)
    dailyAffectMood: int = Field(..., ge=1, le=5)
    dailyAffectEnergy: int = Field(..., ge=1, le=5)
    dailyAffectStress: int = Field(..., ge=1, le=5)
    sleepQuality: Optional[int] = Field(default=None, ge=1, le=5)
    reflectionNote: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("userId")
    @classmethod
    def check_user_id(cls, value: Optional[str]) -> str:
        return validate_safe_user_id(value or "demo_user")


class CheckinCreateRequest(BaseModel):
    userId: str = Field(default="demo_user", min_length=1, max_length=64)
    questionnaire: Optional[QuestionnaireRequest] = None
    faceAnalysisRunId: Optional[str] = None
    voiceAnalysisRunId: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("userId")
    @classmethod
    def check_user_id(cls, value: str) -> str:
        return validate_safe_user_id(value)


class AnalysisRunResponse(BaseModel):
    runId: str
    userId: str
    modality: str
    mode: str
    filename: str
    qualityScore: Optional[float] = None
    isReliable: Optional[bool] = None
    createdAt: str
    result: Dict[str, Any]
    disclaimer: str
