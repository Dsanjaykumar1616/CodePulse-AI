"""A small, deterministic EngineRun used by API tests.

It has the same shapes the real engine produces (DataFrames, dependency
graph object, dicts), so result building and every endpoint are exercised
without cloning a repository. The real engine is covered separately in
test_engine_integration.py.
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from app.services.engine_runner import STAGES, EngineRun

FILES = ["src/core/payment.py", "src/core/user.py", "src/api/routes.py", "web/app.js"]


def make_run(repo_url: str, owner: str | None, name: str) -> EngineRun:
    run = EngineRun(repo_url=repo_url, owner=owner, name=name, repo_path="/srv/codepulse/data/repositories/x")
    run.repository_info = {
        "repository_name": name, "repository_url": repo_url, "repository_path": run.repo_path,
        "total_files": 6, "languages": {"Python": 3, "JavaScript": 1}, "unsupported_files": 2,
        "commits": 42, "contributors": 5,
    }
    run.metrics = [
        {"file": f"{run.repo_path}/{path}", "language": "Python" if path.endswith(".py") else "JavaScript",
         "maintainability": 60.0 + i * 5 if path.endswith(".py") else None}
        for i, path in enumerate(FILES)
    ]
    run.git_metrics = [
        {"file": path, "commit_count": 10 - i, "contributors": 3, "lines_added": 100, "lines_deleted": 20,
         "code_churn": 120 - i * 20, "bug_fix_commits": 3 - i if i < 3 else 0, "file_age_days": 300,
         "first_modified": "2025-01-01", "last_modified": "2026-09-01"}
        for i, path in enumerate(FILES)
    ]
    run.dataset = pd.DataFrame([
        {"file": path, "language": "Python" if path.endswith(".py") else "JavaScript", "loc": 200 - i * 30,
         "complexity": 20 - i * 4, "functions": 8, "classes": 1, "nesting_depth": 4 - i % 3,
         "comment_ratio": 0.1, "commit_count": 10 - i, "contributors": 3, "code_churn": 120 - i * 20,
         "bug_fix_commits": 3 - i if i < 3 else 0, "file_age_days": 300, "bug_label": 1 if i < 3 else 0}
        for i, path in enumerate(FILES)
    ])
    run.predictions = pd.DataFrame([
        {"file": path, "language": "Python", "bug_probability": p, "risk_level": level}
        for path, p, level in zip(FILES, [0.81, 0.55, 0.3, 0.1], ["Critical", "High", "Medium", "Low"])
    ])
    run.ml_results = {"Random Forest": {"accuracy": 0.8, "precision": 0.75, "recall": 0.7, "f1": 0.72, "roc_auc": 0.81},
                      "Logistic Regression": {"accuracy": 0.7, "precision": 0.6, "recall": 0.6, "f1": 0.6, "roc_auc": 0.7}}
    run.ml_best_model = "Random Forest"
    run.ml_class_distribution = {0: 1, 1: 3}
    run.duplicate_pairs = pd.DataFrame([
        {"file_a": FILES[0], "file_b": FILES[1], "similarity_score": 91.2, "similarity_level": "HIGH",
         "matching_token_count": 140, "evidence": "Normalized token sequences share substantial structure"},
    ])
    run.duplicate_summary = {"duplicate_groups": 1, "high_similarity_groups": 1, "top_pairs": []}
    run.review_findings = pd.DataFrame([
        {"file": FILES[0], "rule_id": "COMPLEXITY_HIGH", "severity": "HIGH", "title": "High cyclomatic complexity",
         "evidence": "Cyclomatic complexity = 20", "metric": "Cyclomatic complexity", "value": 20,
         "recommendation": "Split complex logic into smaller, focused functions."},
    ])
    run.review_summary = {"files_reviewed": 4, "total_findings": 1, "critical_count": 0, "high_count": 1,
                          "medium_count": 0, "low_count": 0, "top_findings": []}
    run.technical_debt = pd.DataFrame([
        {"file": path, "technical_debt_score": s, "technical_debt_level": lvl, "complexity_component": 80.0,
         "ml_component": 50.0, "duplication_component": None, "maintainability_component": 40.0,
         "churn_component": 30.0, "duplication_available": False, "ml_available": True,
         "maintainability_available": True, "debt_reasons": ["High relative complexity"]}
        for path, s, lvl in zip(FILES, [72.0, 55.0, 30.0, 10.0], ["HIGH", "MEDIUM", "LOW", "LOW"])
    ])
    run.technical_debt_summary = {"repository_debt_score": 41.75, "debt_level": "MEDIUM", "low_count": 2,
                                  "medium_count": 1, "high_count": 1, "critical_count": 0,
                                  "high_critical_percentage": 25.0, "duplication_available": False}
    dependencies = {FILES[0]: set(), FILES[1]: {FILES[0]}, FILES[2]: {FILES[0], FILES[1]}, FILES[3]: set()}
    used_by = {FILES[0]: {FILES[1], FILES[2]}, FILES[1]: {FILES[2]}, FILES[2]: set(), FILES[3]: set()}
    run.dependency_graph = SimpleNamespace(
        dependencies=dependencies, used_by=used_by, unresolved_imports={FILES[2]: {"flask"}}
    )
    run.full_centrality = sorted(
        ({"file": f, "incoming_dependencies": len(used_by[f]), "outgoing_dependencies": len(dependencies[f]),
          "total_connections": len(used_by[f]) + len(dependencies[f])} for f in FILES),
        key=lambda item: (-item["total_connections"], item["file"]),
    )
    run.architecture_report = {"dependency_relationships": 3, "unresolved_dependencies": 1, "graphviz_available": False}
    run.issue_result = {"available": True, "issues": [
        {"number": 7, "title": "payment rounding bug", "state": "open", "labels": [{"name": "bug"}],
         "html_url": "https://github.com/o/r/issues/7", "user": {"login": "x"}, "body": "payment.py rounds wrong"},
        {"number": 3, "title": "old crash", "state": "closed", "labels": [], "html_url": "https://github.com/o/r/issues/3",
         "user": {"login": "y"}, "body": ""},
    ]}
    run.issue_matches = {FILES[0]: [{"number": 7, "title": "payment rounding bug", "state": "OPEN", "body": "payment.py",
                                     "labels": ["bug"], "url": "https://github.com/o/r/issues/7", "relevance": "HIGH",
                                     "score": 8, "evidence": ["File name found in issue body"]}]}
    run.health_report = {"overall_score": 61.4, "health_level": "Good",
                         "components": {"code_quality": 58.0, "git_stability": 49.2, "defect_risk": 56.0, "maintainability": 67.5},
                         "maintainability_available": True}
    run.opportunities = [
        {"title": "Refactor payment", "file": FILES[0], "priority": "HIGH", "difficulty": "ADVANCED",
         "suggested_for": "Suggested for Advanced", "reasons": ["High complexity"], "suggested_action": "Refactor",
         "score": 9.1, "impact_score": 9.1, "opportunity_score": 9.1, "impact": "MEDIUM", "centrality": 2,
         "related_files": [FILES[1], FILES[2]], "open_issue_count": 1, "closed_issue_count": 0,
         "related_issue_status": "OPEN"},
        {"title": "Document user", "file": FILES[1], "priority": "LOW", "difficulty": "BEGINNER",
         "suggested_for": "Suggested for Beginner", "reasons": ["Low documentation"], "suggested_action": "Docs",
         "score": 4.0, "impact_score": 4.0, "opportunity_score": 4.0, "impact": "LOW", "centrality": 2,
         "related_files": [], "open_issue_count": 0, "closed_issue_count": 0, "related_issue_status": "NONE"},
    ]
    for path in FILES:
        run.file_intelligence[path] = {
            "file": path,
            "explanation": {"file": path, "risk_level": "High", "bug_probability": 0.55,
                            "metrics": {"loc": 100, "complexity": 10, "nesting_depth": 2, "commit_count": 5,
                                        "bug_fix_commits": 1, "contributors": 2, "code_churn": 50, "maintainability": 60.0},
                            "reasons": ["Large file"], "recommendation": "Review carefully.",
                            "complexity_high": False, "churn_high": True},
            "related_files": [{"file": FILES[1], "reason": "Imports the selected file"}],
            "impact": {"file": path, "depends_on": [], "used_by": [FILES[1]], "impact_level": "LOW",
                       "reason": "Only one direct static dependency was detected.", "available": True},
            "history": {"file": path, "commit_count": 5, "contributors": 2, "code_churn": 50,
                        "bug_fix_commits": 1, "recent_activity": "MODERATE", "explanation": "x"},
            "issues": run.issue_matches.get(path, []),
            "plan": {"target": path, "contribution_type": "Stability improvement", "difficulty": "INTERMEDIATE",
                     "priority": "MEDIUM", "steps": ["Read the file.", "Run the tests."]},
            "open_issue_number": 7 if path == FILES[0] else None,
        }
    run.report_html = "<!doctype html><html><body><h1>CodePulse AI Analysis Report</h1></body></html>"
    run.warnings = ["Graphviz is not installed, so static architecture images were not rendered."]
    return run


def fake_run_engine(repo_url, *, owner, name, progress, **_):
    for key, _label in STAGES:
        progress(key, "running", None)
        progress(key, "done", None)
    return make_run(repo_url, owner, name)
