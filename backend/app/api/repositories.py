from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_repository
from app.db.session import get_db
from app.models import AnalysisJob, Repository, User
from app.schemas import JobOut, RepositoryCreate, RepositoryCreated, RepositoryOut
from app.services.github_url import InvalidRepositoryUrl, parse_github_url
from app.services.jobs import initial_stages, job_manager, latest_completed_job, latest_job

router = APIRouter(prefix="/repositories", tags=["repositories"])


def job_out(job: AnalysisJob) -> JobOut:
    out = JobOut.model_validate(job)
    if job.status == "queued":
        out.queue_position = job_manager.queue_position(job.id)
    return out


def repository_out(db: Session, repository: Repository) -> RepositoryOut:
    job = latest_job(db, repository)
    return RepositoryOut(
        id=repository.id,
        owner=repository.owner,
        name=repository.name,
        full_name=repository.full_name,
        url=f"https://github.com/{repository.owner}/{repository.name}",
        created_at=repository.created_at,
        last_analyzed_at=repository.last_analyzed_at,
        health_score=repository.health_score,
        debt_score=repository.debt_score,
        risk_signal=repository.risk_signal,
        status=job.status if job else "never_analyzed",
        latest_job=job_out(job) if job else None,
        has_results=latest_completed_job(db, repository) is not None,
    )


def start_analysis(db: Session, repository: Repository) -> AnalysisJob:
    active = db.scalar(
        select(AnalysisJob).where(
            AnalysisJob.repository_id == repository.id,
            AnalysisJob.status.in_(("queued", "running")),
        )
    )
    if active:
        return active
    job = AnalysisJob(repository_id=repository.id, status="queued", stages=initial_stages(), warnings=[])
    db.add(job)
    db.commit()
    db.refresh(job)
    job_manager.submit(job.id)
    db.refresh(job)
    return job


@router.get("", response_model=list[RepositoryOut])
def list_repositories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    repositories = db.scalars(
        select(Repository).where(Repository.user_id == user.id).order_by(Repository.created_at.desc())
    ).all()
    return [repository_out(db, repository) for repository in repositories]


@router.post("", response_model=RepositoryCreated, status_code=status.HTTP_201_CREATED)
def add_repository(
    payload: RepositoryCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        parsed = parse_github_url(payload.url)
    except InvalidRepositoryUrl as error:
        raise HTTPException(status_code=422, detail=str(error))

    repository = db.scalar(
        select(Repository).where(
            Repository.user_id == user.id, Repository.canonical_url == parsed.canonical_url
        )
    )
    created = repository is None
    if created:
        repository = Repository(
            user_id=user.id, canonical_url=parsed.canonical_url, owner=parsed.owner, name=parsed.name
        )
        db.add(repository)
        db.commit()
        db.refresh(repository)
    else:
        response.status_code = status.HTTP_200_OK

    job = start_analysis(db, repository) if payload.analyze else None
    return RepositoryCreated(
        repository=repository_out(db, repository),
        job=job_out(job) if job else None,
        created=created,
    )


@router.get("/{repository_id}", response_model=RepositoryOut)
def get_repository(repository: Repository = Depends(get_owned_repository), db: Session = Depends(get_db)):
    return repository_out(db, repository)


@router.delete("/{repository_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repository(repository: Repository = Depends(get_owned_repository), db: Session = Depends(get_db)):
    db.delete(repository)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{repository_id}/analyze", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def analyze_repository(repository: Repository = Depends(get_owned_repository), db: Session = Depends(get_db)):
    return job_out(start_analysis(db, repository))


@router.get("/{repository_id}/jobs", response_model=list[JobOut])
def list_jobs(repository: Repository = Depends(get_owned_repository), db: Session = Depends(get_db)):
    jobs = db.scalars(
        select(AnalysisJob)
        .where(AnalysisJob.repository_id == repository.id)
        .order_by(AnalysisJob.created_at.desc())
        .limit(20)
    ).all()
    return [job_out(job) for job in jobs]
