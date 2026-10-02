"""Database models.

The schema is deliberately small:

* users                - accounts
* repositories         - a GitHub repository a user added (one row per user+repo)
* analysis_jobs        - one row per analysis run, with live stage progress
* analysis_results     - the finished output of a job, one JSONB column per
                         section, plus the exported HTML report

The engine's outputs are nested and read as whole sections by the UI, so they
are stored as JSONB documents instead of being normalised into many tables.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base, JSONType


def _uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    repositories: Mapped[list[Repository]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("user_id", "canonical_url", name="uq_user_repo"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    canonical_url: Mapped[str] = mapped_column(String(500))
    owner: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Denormalised from the latest completed analysis, for the repository list.
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    health_score: Mapped[float | None] = mapped_column(Float)
    debt_score: Mapped[float | None] = mapped_column(Float)
    risk_signal: Mapped[float | None] = mapped_column(Float)

    user: Mapped[User] = relationship(back_populates="repositories")
    jobs: Mapped[list[AnalysisJob]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
        order_by="AnalysisJob.created_at.desc()",
    )

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    repository_id: Mapped[str] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    # queued | running | completed | failed
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    current_stage: Mapped[str | None] = mapped_column(String(50))
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stages: Mapped[list] = mapped_column(JSONType, default=list)
    warnings: Mapped[list] = mapped_column(JSONType, default=list)
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    repository: Mapped[Repository] = relationship(back_populates="jobs")
    result: Mapped[AnalysisResult | None] = relationship(
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"), unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    overview: Mapped[dict] = mapped_column(JSONType)
    health: Mapped[dict] = mapped_column(JSONType)
    risk: Mapped[dict] = mapped_column(JSONType)
    debt: Mapped[dict] = mapped_column(JSONType)
    duplicates: Mapped[dict] = mapped_column(JSONType)
    architecture: Mapped[dict] = mapped_column(JSONType)
    review: Mapped[dict] = mapped_column(JSONType)
    issues: Mapped[dict] = mapped_column(JSONType)
    opportunities: Mapped[dict] = mapped_column(JSONType)
    # {relative_path: intelligence document}
    # Large columns are loaded only by the endpoints that need them.
    files: Mapped[dict] = mapped_column(JSONType, deferred=True)
    report_html: Mapped[str | None] = mapped_column(Text, deferred=True)

    job: Mapped[AnalysisJob] = relationship(back_populates="result")
