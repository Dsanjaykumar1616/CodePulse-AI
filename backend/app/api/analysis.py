from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.repositories import job_out
from app.db.session import get_db
from app.models import AnalysisJob, User
from app.schemas import JobOut

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _owned_job(job_id: str, user: User, db: Session) -> AnalysisJob:
    job = db.get(AnalysisJob, job_id)
    if job is None or job.repository.user_id != user.id:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    return job


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return job_out(_owned_job(job_id, user, db))


@router.get("/{job_id}/status", response_model=JobOut)
def get_job_status(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return job_out(_owned_job(job_id, user, db))
