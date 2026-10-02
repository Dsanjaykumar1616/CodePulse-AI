"""Turn raw engine results into the JSON documents served to the web UI.

Everything here reshapes values the engine already computed. No scores are
calculated here; the only derived numbers are counts, averages and rankings
of engine output, used as evidence in the UI.
"""

from __future__ import annotations

import os
import posixpath
from datetime import datetime, timezone
from pathlib import Path

from app.services.engine_runner import EngineRun
from app.services.serialize import number, records, to_jsonable

ML_LABEL_DEFINITION = (
    "The ML model is trained on a proxy label: a file is labelled 1 when its Git "
    "history contains at least one commit whose message matches a bug-fix keyword. "
    "Its output is a historical risk signal based on repository history, not a "
    "confirmed probability of future defects."
)

DUPLICATE_LIMITATIONS = (
    "Duplicate detection compares normalized token sequences of whole files. "
    "It reports file pairs and a similarity score; it does not record line ranges, "
    "so exact duplicated lines are not shown."
)

HEALTH_LABELS = {
    "code_quality": ("Code Quality", "Lower complexity and nesting, and more comments, score higher."),
    "git_stability": ("Git Stability", "Lower churn, fewer repeated changes and fewer historical bug-fix commits score higher."),
    "defect_risk": ("Historical Risk", "100 minus the average historical risk signal from the ML model."),
    "maintainability": ("Maintainability", "Average maintainability index of Python files."),
}

HEALTH_WEIGHTS = {"code_quality": 0.30, "git_stability": 0.30, "defect_risk": 0.25, "maintainability": 0.15}

DEBT_WEIGHTS = {"complexity": 0.35, "ml": 0.25, "duplication": 0.20, "maintainability": 0.10, "churn": 0.10}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _relative(run: EngineRun, path: str) -> str:
    try:
        return Path(path).resolve().relative_to(Path(run.repo_path).resolve()).as_posix()
    except (ValueError, OSError):
        return str(path).replace("\\", "/").lstrip("./")


def _maintainability_by_file(run: EngineRun) -> dict[str, float]:
    values = {}
    for metric in run.metrics or []:
        value = metric.get("maintainability")
        if value is not None:
            values[_relative(run, metric["file"])] = number(value, 2)
    return values


def _prediction_map(run: EngineRun) -> dict[str, dict]:
    if run.predictions is None:
        return {}
    return {
        row["file"]: {"probability": number(row.get("bug_probability"), 4), "level": row.get("risk_level")}
        for row in records(run.predictions)
    }


def _debt_map(run: EngineRun) -> dict[str, dict]:
    return {row["file"]: row for row in records(run.technical_debt)}


def _directory(path: str) -> str:
    directory = posixpath.dirname(path)
    return directory or "(root)"


def _mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 2) if values else None


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def build_sections(run: EngineRun) -> dict:
    predictions = _prediction_map(run)
    debt = _debt_map(run)
    maintainability = _maintainability_by_file(run)
    dataset_rows = records(run.dataset)
    review_rows = records(run.review_findings)
    review_by_file: dict[str, list] = {}
    for finding in review_rows:
        review_by_file.setdefault(finding["file"], []).append(finding)

    file_rows = []
    for row in dataset_rows:
        path = row["file"]
        prediction = predictions.get(path, {})
        debt_row = debt.get(path, {})
        file_rows.append({
            "file": path,
            "directory": _directory(path),
            "language": row.get("language"),
            "loc": row.get("loc"),
            "complexity": row.get("complexity"),
            "functions": row.get("functions"),
            "classes": row.get("classes"),
            "nesting_depth": row.get("nesting_depth"),
            "comment_ratio": number(row.get("comment_ratio"), 4),
            "commit_count": row.get("commit_count"),
            "contributors": row.get("contributors"),
            "code_churn": row.get("code_churn"),
            "bug_fix_commits": row.get("bug_fix_commits"),
            "file_age_days": row.get("file_age_days"),
            "maintainability": maintainability.get(path),
            "risk_probability": prediction.get("probability"),
            "risk_level": prediction.get("level"),
            "debt_score": debt_row.get("technical_debt_score"),
            "debt_level": debt_row.get("technical_debt_level"),
            "review_findings": len(review_by_file.get(path, [])),
        })
    file_rows.sort(key=lambda item: (-(item["risk_probability"] or 0), -(item["debt_score"] or 0), item["file"]))

    overview = _overview(run, file_rows, maintainability)
    sections = {
        "overview": overview,
        "health": _health(run, file_rows),
        "risk": _risk(run, file_rows),
        "debt": _debt(run),
        "duplicates": _duplicates(run),
        "architecture": _architecture(run, predictions, debt),
        "review": _review(run, review_rows),
        "issues": _issues(run),
        "opportunities": _opportunities(run, review_by_file),
        "files": _files(run, file_rows, debt, review_by_file),
        "report_html": run.report_html,
    }
    return sections


def _availability(value, reason):
    return {"value": value, "available": value is not None, "reason": None if value is not None else reason}


def _overview(run: EngineRun, file_rows: list[dict], maintainability: dict) -> dict:
    info = run.repository_info or {}
    health = run.health_report or {}
    components = health.get("components", {})
    debt_summary = run.technical_debt_summary or {}
    probabilities = [row["risk_probability"] for row in file_rows if row["risk_probability"] is not None]
    risk_signal = round(100 * sum(probabilities) / len(probabilities), 1) if probabilities else None
    elevated = sum(1 for row in file_rows if (row["risk_level"] or "") in ("High", "Critical"))
    ml_reason = run.ml_unavailable_reason or run.stage_notes.get("ml_risk") or "ML risk analysis was not run."

    language_counts = info.get("languages") or {}
    analyzed_languages: dict[str, int] = {}
    for row in file_rows:
        analyzed_languages[row["language"] or "Other"] = analyzed_languages.get(row["language"] or "Other", 0) + 1

    return {
        "repository": {
            "owner": run.owner,
            "name": run.name,
            "full_name": f"{run.owner}/{run.name}" if run.owner else run.name,
            "url": f"https://github.com/{run.owner}/{run.name}" if run.owner else None,
            "analyzed_at": _now(),
        },
        "languages": to_jsonable(language_counts),
        "analyzed_languages": analyzed_languages,
        "total_files": info.get("total_files"),
        "analyzed_files": len(file_rows),
        "unsupported_files": info.get("unsupported_files"),
        "commits": info.get("commits"),
        "metrics": {
            "health_score": _availability(number(health.get("overall_score"), 1), run.stage_notes.get("health", "Health score could not be calculated.")),
            "health_level": health.get("health_level"),
            "code_quality": _availability(number(components.get("code_quality"), 1), "Health score could not be calculated."),
            "git_stability": _availability(number(components.get("git_stability"), 1), "Health score could not be calculated."),
            "maintainability": _availability(
                number(components.get("maintainability"), 1),
                "Maintainability index is only computed for Python files; none were found." if not maintainability else "Not available.",
            ),
            "historical_risk_signal": _availability(risk_signal, ml_reason),
            "elevated_risk_files": elevated if probabilities else None,
            "technical_debt": _availability(number(debt_summary.get("repository_debt_score"), 1), run.stage_notes.get("technical_debt", "Technical debt could not be calculated.")),
            "technical_debt_level": debt_summary.get("debt_level"),
            "duplicate_groups": _availability(
                (run.duplicate_summary or {}).get("duplicate_groups") if run.duplicate_summary is not None else None,
                run.stage_notes.get("duplicate_detection", "Duplicate detection did not run."),
            ),
            "dependencies": _availability(
                (run.architecture_report or {}).get("dependency_relationships") if run.architecture_report else None,
                run.stage_notes.get("architecture", "Dependency analysis did not run."),
            ),
            "contributors": _availability(info.get("contributors"), "Contributor count not available."),
        },
        "warnings": [run.scrub(w) for w in dict.fromkeys(run.warnings)],
    }


def _top(rows, key, limit=5, reverse=True):
    present = [row for row in rows if row.get(key) is not None]
    present.sort(key=lambda row: row[key], reverse=reverse)
    return [{"file": row["file"], "value": row[key]} for row in present[:limit]]


def _health(run: EngineRun, file_rows: list[dict]) -> dict:
    report = run.health_report
    if not report:
        return {
            "available": False,
            "reason": run.stage_notes.get("health", "Health score could not be calculated."),
        }
    components = report.get("components", {})
    available_weight = sum(HEALTH_WEIGHTS[key] for key in components if key in HEALTH_WEIGHTS)
    component_list = []
    for key, (label, description) in HEALTH_LABELS.items():
        value = number(components.get(key), 1)
        reason = None
        if value is None:
            reason = (
                run.ml_unavailable_reason or "ML risk analysis did not run."
                if key == "defect_risk"
                else "No Python files with a maintainability index were found."
            )
        component_list.append({
            "key": key,
            "label": label,
            "description": description,
            "value": value,
            "available": value is not None,
            "weight": HEALTH_WEIGHTS[key],
            "effective_weight": round(HEALTH_WEIGHTS[key] / available_weight, 3) if value is not None and available_weight else None,
            "reason": reason,
        })

    risk_levels: dict[str, int] = {}
    for row in file_rows:
        if row["risk_level"]:
            risk_levels[row["risk_level"]] = risk_levels.get(row["risk_level"], 0) + 1

    evidence = {
        "code_quality": {
            "average_complexity": _mean([row["complexity"] for row in file_rows]),
            "average_nesting_depth": _mean([row["nesting_depth"] for row in file_rows]),
            "average_comment_ratio": _mean([row["comment_ratio"] for row in file_rows]),
            "most_complex_files": _top(file_rows, "complexity"),
            "deepest_nesting_files": _top(file_rows, "nesting_depth"),
        },
        "git_stability": {
            "total_churn": sum(row["code_churn"] or 0 for row in file_rows),
            "files_with_bug_fix_activity": sum(1 for row in file_rows if (row["bug_fix_commits"] or 0) > 0),
            "highest_churn_files": _top(file_rows, "code_churn"),
            "most_bug_fix_activity": [item for item in _top(file_rows, "bug_fix_commits") if item["value"]],
        },
        "defect_risk": {
            "average_signal": _mean([row["risk_probability"] for row in file_rows]),
            "risk_level_counts": risk_levels,
            "highest_signal_files": _top(file_rows, "risk_probability"),
        },
        "maintainability": {
            "average_index": _mean([row["maintainability"] for row in file_rows]),
            "lowest_maintainability_files": _top(file_rows, "maintainability", reverse=False),
        },
    }
    return {
        "available": True,
        "overall_score": number(report.get("overall_score"), 1),
        "health_level": report.get("health_level"),
        "components": component_list,
        "evidence": evidence,
    }


def _risk(run: EngineRun, file_rows: list[dict]) -> dict:
    available = run.predictions is not None
    model_results = []
    for name, metrics in (run.ml_results or {}).items():
        model_results.append({
            "model": name,
            "selected": name == run.ml_best_model,
            **{key: number(value, 4) for key, value in metrics.items()},
        })
    return {
        "available": available,
        "reason": None if available else (run.ml_unavailable_reason or run.stage_notes.get("ml_risk") or "ML risk analysis was not run."),
        "label_definition": ML_LABEL_DEFINITION,
        "selected_model": run.ml_best_model,
        "models": model_results,
        "class_distribution": to_jsonable(run.ml_class_distribution),
        "files": file_rows,
    }


def _debt(run: EngineRun) -> dict:
    if run.technical_debt is None:
        return {"available": False, "reason": run.stage_notes.get("technical_debt", "Technical debt could not be calculated.")}
    summary = run.technical_debt_summary or {}
    rows = records(run.technical_debt)
    return {
        "available": True,
        "repository_debt_score": number(summary.get("repository_debt_score"), 2),
        "debt_level": summary.get("debt_level"),
        "distribution": {
            "LOW": summary.get("low_count", 0),
            "MEDIUM": summary.get("medium_count", 0),
            "HIGH": summary.get("high_count", 0),
            "CRITICAL": summary.get("critical_count", 0),
        },
        "high_critical_percentage": number(summary.get("high_critical_percentage"), 2),
        "duplication_available": bool(summary.get("duplication_available")),
        "weights": DEBT_WEIGHTS,
        "files": rows,
    }


def _duplicates(run: EngineRun) -> dict:
    if run.duplicate_pairs is None:
        return {
            "available": False,
            "reason": run.stage_notes.get("duplicate_detection", "Duplicate detection did not run."),
            "limitations": DUPLICATE_LIMITATIONS,
        }
    pairs = records(run.duplicate_pairs)
    # Group membership uses the same transitive merge as DuplicateCodeDetector.summarize().
    groups: list[set] = []
    for pair in pairs:
        members = {pair["file_a"], pair["file_b"]}
        matching = [group for group in groups if group & members]
        if matching:
            merged = members.union(*matching)
            groups = [group for group in groups if not group & members]
            groups.append(merged)
        else:
            groups.append(members)

    group_docs = []
    for index, members in enumerate(groups, start=1):
        group_pairs = [pair for pair in pairs if pair["file_a"] in members]
        best = max((pair["similarity_score"] or 0 for pair in group_pairs), default=0)
        levels = {pair["similarity_level"] for pair in group_pairs}
        group_docs.append({
            "id": index,
            "files": sorted(members),
            "pair_count": len(group_pairs),
            "max_similarity": best,
            "severity": "HIGH" if "HIGH" in levels else ("MEDIUM" if "MEDIUM" in levels else "LOW"),
            "pairs": group_pairs,
        })
    group_docs.sort(key=lambda group: (-group["max_similarity"], group["id"]))
    summary = run.duplicate_summary or {}
    return {
        "available": True,
        "duplicate_groups": summary.get("duplicate_groups", len(groups)),
        "high_similarity_pairs": summary.get("high_similarity_groups", 0),
        "pair_count": len(pairs),
        "groups": group_docs,
        "pairs": pairs,
        "limitations": DUPLICATE_LIMITATIONS,
    }


def _architecture(run: EngineRun, predictions: dict, debt: dict) -> dict:
    graph = run.dependency_graph
    if graph is None:
        return {"available": False, "reason": run.stage_notes.get("architecture", "Dependency analysis did not run.")}
    max_total = max((item["total_connections"] for item in run.full_centrality), default=0) or 1
    language_by_file = {row["file"]: row.get("language") for row in records(run.dataset)}
    nodes = []
    for item in run.full_centrality:
        path = item["file"]
        prediction = predictions.get(path, {})
        debt_row = debt.get(path, {})
        nodes.append({
            "id": path,
            "label": posixpath.basename(path),
            "directory": _directory(path),
            "language": language_by_file.get(path),
            "incoming": item["incoming_dependencies"],
            "outgoing": item["outgoing_dependencies"],
            "total": item["total_connections"],
            "centrality": round(item["total_connections"] / max_total, 4),
            "risk_probability": prediction.get("probability"),
            "risk_level": prediction.get("level"),
            "debt_score": debt_row.get("technical_debt_score"),
            "debt_level": debt_row.get("technical_debt_level"),
        })
    edges = [
        {"source": source, "target": target}
        for source in sorted(graph.dependencies)
        for target in sorted(graph.dependencies[source])
    ]
    unresolved = [
        {"file": path, "imports": sorted(imports)}
        for path, imports in sorted(getattr(graph, "unresolved_imports", {}).items())
    ]
    report = run.architecture_report or {}
    return {
        "available": True,
        "files": len(nodes),
        "dependency_relationships": report.get("dependency_relationships", len(edges)),
        "unresolved_dependencies": report.get("unresolved_dependencies", 0),
        "graphviz_available": bool(report.get("graphviz_available")),
        "nodes": nodes,
        "edges": edges,
        "unresolved": unresolved,
    }


def _review(run: EngineRun, review_rows: list[dict]) -> dict:
    if run.review_findings is None:
        return {"available": False, "reason": run.stage_notes.get("code_review", "Code review did not run.")}
    summary = run.review_summary or {}
    return {
        "available": True,
        "files_reviewed": summary.get("files_reviewed"),
        "total_findings": summary.get("total_findings", len(review_rows)),
        "counts": {
            "CRITICAL": summary.get("critical_count", 0),
            "HIGH": summary.get("high_count", 0),
            "MEDIUM": summary.get("medium_count", 0),
            "LOW": summary.get("low_count", 0),
        },
        "findings": [{"id": index, **finding} for index, finding in enumerate(review_rows)],
    }


def _excerpt(text, limit=280):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _issues(run: EngineRun) -> dict:
    result = run.issue_result
    if not result or not result.get("available"):
        return {
            "available": False,
            "reason": (result or {}).get("message") or run.stage_notes.get("github_issues", "GitHub issue analysis did not run."),
            "issues": [],
        }
    matched_files: dict = {}
    for path, matches in run.issue_matches.items():
        for match in matches:
            matched_files.setdefault(match.get("number"), []).append(path)

    issues = []
    for issue in result.get("issues", []):
        state = str(issue.get("state") or "UNKNOWN").upper()
        if state not in ("OPEN", "CLOSED"):
            state = "UNKNOWN"
        number_ = issue.get("number")
        issues.append({
            "number": number_,
            "title": issue.get("title"),
            "state": state,
            "labels": [
                label.get("name", "") if isinstance(label, dict) else str(label)
                for label in issue.get("labels", [])
            ],
            "url": issue.get("html_url"),
            "author": (issue.get("user") or {}).get("login"),
            "comments": issue.get("comments"),
            "created_at": issue.get("created_at"),
            "updated_at": issue.get("updated_at"),
            "description": _excerpt(issue.get("body")),
            "related_files": sorted(matched_files.get(number_, []))[:20],
        })
    counts = {"OPEN": 0, "CLOSED": 0, "UNKNOWN": 0}
    for issue in issues:
        counts[issue["state"]] += 1
    return {
        "available": True,
        "reason": None,
        "note": "The GitHub API returns at most the 100 most recently updated issues per request; pull requests are excluded.",
        "counts": counts,
        "issues": issues,
    }


def _opportunities(run: EngineRun, review_by_file: dict) -> dict:
    if run.stage_notes.get("contribution_intelligence") and not run.opportunities:
        return {"available": False, "reason": run.stage_notes["contribution_intelligence"], "items": []}
    items = []
    for rank, item in enumerate(run.opportunities or [], start=1):
        doc = to_jsonable(item)
        doc["rank"] = rank
        doc["review_finding_count"] = len(review_by_file.get(doc.get("file"), []))
        items.append(doc)
    return {
        "available": True,
        "reason": None,
        "disclaimer": (
            "Opportunity scores and difficulty levels are CodePulse's calculated guidance "
            "from code metrics, Git history, dependencies, technical debt and issues. "
            "They are not an absolute judgement of the work involved."
        ),
        "items": items,
    }


def _files(run: EngineRun, file_rows: list[dict], debt: dict, review_by_file: dict) -> dict:
    duplicate_rows = records(run.duplicate_pairs)
    opportunity_by_file = {item["file"]: to_jsonable(item) for item in (run.opportunities or [])}
    row_by_file = {row["file"]: row for row in file_rows}
    documents = {}
    for path, entry in run.file_intelligence.items():
        doc = to_jsonable(entry)
        explanation = doc.get("explanation") or {}
        if explanation:
            explanation["file"] = path
        for issue in doc.get("issues") or []:
            issue["body"] = _excerpt(issue.get("body"), 400)
        doc["summary"] = row_by_file.get(path)
        doc["debt"] = debt.get(path)
        doc["review_findings"] = review_by_file.get(path, [])
        doc["duplicates"] = [
            pair for pair in duplicate_rows if path in (pair.get("file_a"), pair.get("file_b"))
        ]
        doc["opportunity"] = opportunity_by_file.get(path)
        documents[path] = doc
    return {
        "limited": run.file_intelligence_limited,
        "documents": documents,
    }


def headline_values(sections: dict) -> dict:
    metrics = sections["overview"]["metrics"]
    return {
        "health_score": metrics["health_score"]["value"],
        "debt_score": metrics["technical_debt"]["value"],
        "risk_signal": metrics["historical_risk_signal"]["value"],
    }
