"""Read-only endpoints serving stored analysis results."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import get_owned_repository
from app.db.session import get_db
from app.models import AnalysisResult, Repository
from app.services import guide
from app.services.jobs import latest_completed_job

router = APIRouter(prefix="/repositories/{repository_id}", tags=["results"])

SECTIONS = ("overview", "health", "risk", "debt", "duplicates", "review")


def _result(db: Session, repository: Repository) -> AnalysisResult:
    job = latest_completed_job(db, repository)
    if job is None or job.result is None:
        raise HTTPException(
            status_code=404,
            detail="This repository has no completed analysis yet. Run an analysis first.",
        )
    return job.result


def _envelope(result: AnalysisResult, data: dict) -> dict[str, Any]:
    return {
        "job_id": result.job_id,
        "analyzed_at": result.job.finished_at.isoformat() if result.job.finished_at else None,
        **(data or {}),
    }


def _section_endpoint(section: str):
    def endpoint(
        repository: Repository = Depends(get_owned_repository), db: Session = Depends(get_db)
    ) -> dict[str, Any]:
        result = _result(db, repository)
        return _envelope(result, getattr(result, section))

    endpoint.__name__ = f"get_{section}"
    return endpoint


for _section in SECTIONS:
    router.add_api_route(
        f"/{_section}",
        _section_endpoint(_section),
        methods=["GET"],
        summary=f"Latest {_section} results",
    )


@router.get("/architecture")
def get_architecture(
    repository: Repository = Depends(get_owned_repository),
    db: Session = Depends(get_db),
    limit: int = Query(120, ge=5, le=1000, description="Maximum nodes in the overview"),
    directory: str | None = Query(None, max_length=500, description="Only files under this directory"),
    focus: str | None = Query(None, max_length=1000, description="Show the neighbourhood of this file"),
    depth: int = Query(1, ge=1, le=3),
) -> dict[str, Any]:
    result = _result(db, repository)
    data = result.architecture or {}
    if not data.get("available"):
        return _envelope(result, data)

    nodes: list[dict] = data.get("nodes", [])
    edges: list[dict] = data.get("edges", [])
    by_id = {node["id"]: node for node in nodes}

    directories: dict[str, int] = {}
    for node in nodes:
        directories[node["directory"]] = directories.get(node["directory"], 0) + 1

    if focus:
        if focus not in by_id:
            raise HTTPException(status_code=404, detail="File is not part of the dependency graph")
        adjacency: dict[str, set] = {}
        for edge in edges:
            adjacency.setdefault(edge["source"], set()).add(edge["target"])
            adjacency.setdefault(edge["target"], set()).add(edge["source"])
        selected = {focus}
        frontier = {focus}
        for _ in range(depth):
            frontier = {n for current in frontier for n in adjacency.get(current, set())} - selected
            selected |= frontier
        candidates = [by_id[node_id] for node_id in selected]
        candidates.sort(key=lambda node: (node["id"] != focus, -node["total"], node["id"]))
        chosen = candidates[:limit]
    else:
        candidates = nodes
        if directory:
            prefix = directory.rstrip("/")
            candidates = [
                node for node in nodes
                if node["directory"] == prefix or node["directory"].startswith(prefix + "/")
            ]
        chosen = sorted(candidates, key=lambda node: (-node["total"], node["id"]))[:limit]

    chosen = guide.annotate_nodes(chosen, data, result.opportunities)
    chosen_ids = {node["id"] for node in chosen}
    chosen_edges = [edge for edge in edges if edge["source"] in chosen_ids and edge["target"] in chosen_ids]
    unresolved = data.get("unresolved", [])

    return _envelope(result, {
        "available": True,
        "files": data.get("files"),
        "dependency_relationships": data.get("dependency_relationships"),
        "unresolved_dependencies": data.get("unresolved_dependencies"),
        "graphviz_available": data.get("graphviz_available"),
        "nodes": chosen,
        "edges": chosen_edges,
        "candidate_count": len(candidates),
        "truncated": len(candidates) > len(chosen),
        "focus": focus,
        "directory": directory,
        "directories": [
            {"directory": name, "count": count}
            for name, count in sorted(directories.items(), key=lambda item: (-item[1], item[0]))
        ],
        "most_connected": guide.annotate_nodes(
            sorted(nodes, key=lambda node: (-node["total"], node["id"]))[:15], data, result.opportunities
        ),
        "unresolved": sorted(unresolved, key=lambda item: -len(item["imports"]))[:100],
    })


@router.get("/files")
def list_files(repository: Repository = Depends(get_owned_repository), db: Session = Depends(get_db)):
    result = _result(db, repository)
    documents = (result.files or {}).get("documents", {})
    return _envelope(result, {
        "files": [
            {
                "file": row["file"],
                "language": row.get("language"),
                "risk_level": row.get("risk_level"),
                "debt_level": row.get("debt_level"),
                "has_intelligence": row["file"] in documents,
            }
            for row in (result.risk or {}).get("files", [])
        ],
        "limited": (result.files or {}).get("limited", False),
    })


_SAFE_PATH = re.compile(r"^[^\x00]{1,1000}$")


@router.get("/files/intelligence")
def file_intelligence(
    path: str = Query(..., min_length=1, max_length=1000),
    repository: Repository = Depends(get_owned_repository),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # The path is only used as a key into stored results, never on the filesystem.
    normalized = path.replace("\\", "/").lstrip("/")
    if not _SAFE_PATH.match(normalized) or ".." in normalized.split("/"):
        raise HTTPException(status_code=422, detail="Invalid file path")
    result = _result(db, repository)
    documents = (result.files or {}).get("documents", {})
    document = documents.get(normalized)
    if document is None:
        known = any(row["file"] == normalized for row in (result.risk or {}).get("files", []))
        raise HTTPException(
            status_code=404,
            detail=(
                "Detailed intelligence was not precomputed for this file because the repository is very large."
                if known
                else "File not found in this analysis"
            ),
        )
    enriched = guide.enrich_file(
        document, normalized, result.risk, result.architecture, result.opportunities, result.issues
    )
    return _envelope(result, enriched)


@router.get("/opportunities")
def opportunities(
    repository: Repository = Depends(get_owned_repository), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Opportunities with the evidence behind each recommendation and difficulty."""
    result = _result(db, repository)
    data = result.opportunities or {}
    if not data.get("available", True):
        return _envelope(result, {**data, "issues_available": bool((result.issues or {}).get("available"))})
    return _envelope(result, guide.enrich_opportunities(data, result.risk, result.architecture, result.issues))


@router.get("/guide")
def contributor_guide(
    repository: Repository = Depends(get_owned_repository), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Onboarding: repository facts, directory groups, start-here files and roadmap."""
    result = _result(db, repository)
    return _envelope(
        result,
        guide.build_guide(result.overview or {}, result.risk, result.architecture, result.opportunities, result.issues),
    )


@router.get("/issues")
def issues(
    repository: Repository = Depends(get_owned_repository), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Issues with beginner label signals and an estimated difficulty per issue."""
    result = _result(db, repository)
    data = result.issues or {}
    if not data.get("available"):
        return _envelope(result, data)
    documents = (result.files or {}).get("documents", {})
    return _envelope(
        result, guide.enrich_issues(data, documents, result.risk, result.architecture, result.opportunities)
    )


@router.get("/issues/{issue_number}/work")
def issue_work(
    issue_number: int,
    repository: Repository = Depends(get_owned_repository),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """A step-by-step plan for working on one issue, with related files, impact and tests."""
    result = _result(db, repository)
    issues_data = result.issues or {}
    if not issues_data.get("available"):
        raise HTTPException(status_code=404, detail="GitHub issue data is not available for this analysis.")
    issue = next((item for item in issues_data.get("issues", []) if item.get("number") == issue_number), None)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found in this analysis")
    documents = (result.files or {}).get("documents", {})
    return _envelope(result, {
        **guide.issue_work_plan(
            issue, repository.full_name, documents, result.risk, result.architecture, result.opportunities
        ),
        "files_limited": (result.files or {}).get("limited", False),
    })


@router.get("/issues/{issue_number}/files")
def issue_files(
    issue_number: int,
    repository: Repository = Depends(get_owned_repository),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Files CodePulse inferred as related to one issue, ranked by match evidence."""
    result = _result(db, repository)
    issues = result.issues or {}
    if not issues.get("available"):
        raise HTTPException(status_code=404, detail="GitHub issue data is not available for this analysis.")
    issue = next((item for item in issues.get("issues", []) if item.get("number") == issue_number), None)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found in this analysis")
    documents = (result.files or {}).get("documents", {})
    return _envelope(result, {
        "issue": issue,
        "files": guide.issue_related_files(issue_number, documents, result.risk, result.opportunities),
        "basis": (
            "CodePulse inferred relationship: the issue's title or body mentions the file path, file name, "
            "module name, directory or module keywords. GitHub does not link these files to the issue."
        ),
    })


@router.get("/report", response_class=HTMLResponse)
def report(
    repository: Repository = Depends(get_owned_repository),
    db: Session = Depends(get_db),
    download: bool = Query(True),
) -> HTMLResponse:
    result = _result(db, repository)
    if not result.report_html:
        raise HTTPException(status_code=404, detail="The HTML report was not generated for this analysis.")
    headers = {}
    if download:
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", repository.full_name)
        headers["Content-Disposition"] = f'attachment; filename="codepulse-{safe_name}.html"'
    return HTMLResponse(content=result.report_html, headers=headers)
