"""Background analysis jobs.

A single worker thread pulls job ids from a queue and runs them one at a
time (the engine itself also holds a lock). Job state lives in the
database, so the frontend can poll it and it survives page reloads.
"""

from __future__ import annotations

import logging
import queue
import threading
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AnalysisJob, AnalysisResult, Repository
from app.services import engine_runner
from app.services.engine_runner import STAGES, AnalysisError
from app.services.result_builder import build_sections, headline_values

LOGGER = logging.getLogger("codepulse.jobs")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def initial_stages() -> list[dict]:
    return [
        {"key": key, "label": label, "status": "pending", "message": None,
         "started_at": None, "finished_at": None}
        for key, label in STAGES
    ]


class JobManager:
    def __init__(self) -> None:
        self._queue: queue.Queue[str] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    # -- lifecycle --------------------------------------------------------
    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._worker, name="codepulse-analysis", daemon=True)
            self._thread.start()

    def recover(self) -> None:
        """Fail jobs left running by a previous server process; requeue queued ones."""
        with SessionLocal() as db:
            stale = db.scalars(select(AnalysisJob).where(AnalysisJob.status == "running")).all()
            for job in stale:
                job.status = "failed"
                job.error_code = "interrupted"
                job.error_message = "The analysis was interrupted because the server restarted. Run it again."
                job.finished_at = _now()
            queued = db.scalars(
                select(AnalysisJob).where(AnalysisJob.status == "queued").order_by(AnalysisJob.created_at)
            ).all()
            db.commit()
            for job in queued:
                self._queue.put(job.id)

    def submit(self, job_id: str) -> None:
        if get_settings().run_jobs_inline:
            self.run_job(job_id)
            return
        self.start()
        self._queue.put(job_id)

    def queue_position(self, job_id: str) -> int | None:
        with self._queue.mutex:
            items = list(self._queue.queue)
        return items.index(job_id) + 1 if job_id in items else None

    def _worker(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                self.run_job(job_id)
            except Exception:  # noqa: BLE001 - never let the worker die
                LOGGER.exception("Unexpected error running job %s", job_id)
            finally:
                self._queue.task_done()

    # -- execution ---------------------------------------------------------
    def run_job(self, job_id: str) -> None:
        with SessionLocal() as db:
            job = db.get(AnalysisJob, job_id)
            if job is None or job.status != "queued":
                return
            repository = job.repository
            job.status = "running"
            job.started_at = _now()
            job.stages = initial_stages()
            db.commit()
            repo_url = f"https://github.com/{repository.owner}/{repository.name}"
            owner, name = repository.owner, repository.name

        progress = _ProgressWriter(job_id)
        try:
            run = engine_runner.run_engine(
                repo_url,
                owner=owner,
                name=name,
                progress=progress,
                max_file_intelligence=get_settings().max_file_intelligence,
            )
            sections = build_sections(run)
        except AnalysisError as error:
            self._fail(job_id, error.code, error.message)
            return
        except Exception as error:  # noqa: BLE001
            LOGGER.exception("Analysis job %s crashed", job_id)
            self._fail(job_id, "analysis_failed", f"The analysis failed unexpectedly: {error}")
            return
        self._complete(job_id, sections, run.warnings)

    def _complete(self, job_id: str, sections: dict, warnings: list) -> None:
        try:
            with SessionLocal() as db:
                job = db.get(AnalysisJob, job_id)
                if job is None:  # repository deleted while running
                    return
                result = AnalysisResult(job_id=job_id, **sections)
                db.add(result)
                job.status = "completed"
                job.progress = 100
                job.current_stage = None
                job.finished_at = _now()
                job.warnings = list(dict.fromkeys(sections["overview"].get("warnings", warnings)))
                repository = job.repository
                headline = headline_values(sections)
                repository.last_analyzed_at = job.finished_at
                repository.health_score = headline["health_score"]
                repository.debt_score = headline["debt_score"]
                repository.risk_signal = headline["risk_signal"]
                db.commit()
        except Exception as error:  # noqa: BLE001 - database failure
            LOGGER.exception("Could not save results for job %s", job_id)
            self._fail(job_id, "database_error", f"The analysis finished but its results could not be saved: {error}")

    def _fail(self, job_id: str, code: str, message: str) -> None:
        with SessionLocal() as db:
            job = db.get(AnalysisJob, job_id)
            if job is None:
                return
            job.status = "failed"
            job.error_code = code
            job.error_message = message
            job.finished_at = _now()
            stages = [dict(stage) for stage in (job.stages or [])]
            for stage in stages:
                if stage["status"] == "running":
                    stage["status"] = "failed"
                    stage["message"] = message
                    stage["finished_at"] = _now().isoformat()
            job.stages = stages
            db.commit()


class _ProgressWriter:
    """Persist stage transitions so the progress page can poll them."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id

    def __call__(self, key: str, status: str, message: str | None) -> None:
        try:
            with SessionLocal() as db:
                job = db.get(AnalysisJob, self.job_id)
                if job is None:
                    return
                stages = [dict(stage) for stage in (job.stages or initial_stages())]
                now = _now().isoformat()
                for stage in stages:
                    if stage["key"] == key:
                        stage["status"] = status
                        if message:
                            stage["message"] = message
                        if status == "running":
                            stage["started_at"] = now
                        else:
                            stage["finished_at"] = now
                job.stages = stages
                finished = sum(1 for stage in stages if stage["status"] in ("done", "skipped"))
                job.progress = int(100 * finished / len(stages))
                job.current_stage = key if status == "running" else job.current_stage
                db.commit()
        except Exception:  # noqa: BLE001 - progress must never break analysis
            LOGGER.exception("Could not record progress for job %s", self.job_id)


job_manager = JobManager()


def latest_completed_job(db: Session, repository: Repository) -> AnalysisJob | None:
    return db.scalars(
        select(AnalysisJob)
        .where(AnalysisJob.repository_id == repository.id, AnalysisJob.status == "completed")
        .order_by(AnalysisJob.finished_at.desc())
        .limit(1)
    ).first()


def latest_job(db: Session, repository: Repository) -> AnalysisJob | None:
    return db.scalars(
        select(AnalysisJob)
        .where(AnalysisJob.repository_id == repository.id)
        .order_by(AnalysisJob.created_at.desc())
        .limit(1)
    ).first()
