"""Pydantic request/response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name is required")
        return value

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Password must contain at least one letter and one number")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserOut


class StageOut(BaseModel):
    key: str
    label: str
    status: Literal["pending", "running", "done", "skipped", "failed"]
    message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    status: Literal["queued", "running", "completed", "failed"]
    current_stage: str | None
    progress: int
    stages: list[StageOut]
    warnings: list[str]
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    queue_position: int | None = None


class RepositoryCreate(BaseModel):
    url: str = Field(min_length=3, max_length=500)
    analyze: bool = True


class RepositoryOut(BaseModel):
    id: str
    owner: str
    name: str
    full_name: str
    url: str
    created_at: datetime
    last_analyzed_at: datetime | None
    health_score: float | None
    debt_score: float | None
    risk_signal: float | None
    status: Literal["never_analyzed", "queued", "running", "completed", "failed"]
    latest_job: JobOut | None
    has_results: bool


class RepositoryCreated(BaseModel):
    repository: RepositoryOut
    job: JobOut | None
    created: bool


class FileIndexItem(BaseModel):
    file: str
    language: str | None
    risk_level: str | None
    debt_level: str | None


class Section(BaseModel):
    """A stored analysis section (free-form JSON produced by the engine)."""

    model_config = ConfigDict(extra="allow")

    job_id: str
    analyzed_at: datetime | None
    data: dict[str, Any]
