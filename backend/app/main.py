"""FastAPI application entry point.

Run during development (from the backend/ directory):

    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.api import analysis, auth, repositories, results
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import engine
from app.services.jobs import job_manager

LOGGER = logging.getLogger("codepulse.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    get_settings().validate()
    try:
        job_manager.recover()
    except SQLAlchemyError:
        LOGGER.exception(
            "Database is not reachable or not migrated. Check DATABASE_URL and run 'alembic upgrade head'."
        )
    job_manager.start()
    yield


app = FastAPI(
    title="CodePulse AI API",
    version="1.0.0",
    description="Codebase health, technical debt and contribution intelligence.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.exception_handler(OperationalError)
async def database_unavailable(_: Request, error: OperationalError):
    LOGGER.error("Database error: %s", error)
    return JSONResponse(
        status_code=503,
        content={"detail": "The database is unavailable. Please try again shortly."},
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(_: Request, error: SQLAlchemyError):
    LOGGER.exception("Database error", exc_info=error)
    return JSONResponse(status_code=500, content={"detail": "A database error occurred."})


api = APIRouter(prefix="/api")
api.include_router(auth.router)
api.include_router(repositories.router)
api.include_router(results.router)
api.include_router(analysis.router)


@api.get("/health", tags=["system"])
def health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError:
        database = "unavailable"
    return {"status": "ok", "database": database}


app.include_router(api)
