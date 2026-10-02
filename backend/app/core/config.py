"""Application settings, read from environment variables (and backend/.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ENGINE_ROOT = BACKEND_ROOT.parent

try:  # python-dotenv is optional at import time (tests set env directly)
    from dotenv import load_dotenv

    load_dotenv(BACKEND_ROOT / ".env")
except ImportError:  # pragma: no cover
    pass


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://codepulse:codepulse@localhost:5432/codepulse",
        )
    )
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", ""))
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = field(
        default_factory=lambda: int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))
    )
    cors_origins: list[str] = field(
        default_factory=lambda: _split(os.getenv("CORS_ORIGINS", "http://localhost:5173"))
    )
    max_file_intelligence: int = field(
        default_factory=lambda: int(os.getenv("MAX_FILE_INTELLIGENCE", "3000"))
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    # When true, analysis jobs run synchronously inside the request (tests only).
    run_jobs_inline: bool = field(
        default_factory=lambda: os.getenv("CODEPULSE_RUN_JOBS_INLINE", "") == "1"
    )

    def validate(self) -> None:
        if not self.jwt_secret or self.jwt_secret == "change-me-to-a-long-random-string":
            raise RuntimeError(
                "JWT_SECRET is not set. Copy backend/.env.example to backend/.env "
                "and set JWT_SECRET to a long random string."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
