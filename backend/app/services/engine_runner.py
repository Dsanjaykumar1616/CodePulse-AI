"""Run the existing CodePulse analysis engine, stage by stage.

This module is the bridge between the web backend and the engine modules in
the repository root (analyzer/, metrics/, git_analysis/, ml/, analysis/,
github/). It calls them in the same order as ``workspace.ContributorPipeline``
and does not re-implement any analysis logic. What it adds:

* progress callbacks after every stage, for the live progress UI
* structured, human-readable errors instead of printed messages
* a process-wide lock, because the engine writes its artifacts to fixed
  paths under data/datasets/ and invalidates them at the start of each run,
  so two analyses must never overlap
"""

from __future__ import annotations

import contextlib
import io
import logging
import os
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from app.core.config import ENGINE_ROOT

if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

LOGGER = logging.getLogger("codepulse.engine")

# Only one analysis may touch the engine's shared artifact paths at a time.
ENGINE_LOCK = threading.Lock()


STAGES: list[tuple[str, str]] = [
    ("repository_access", "Repository access"),
    ("repository_structure", "Repository structure"),
    ("code_metrics", "Code metrics"),
    ("git_history", "Git history"),
    ("ml_risk", "ML risk analysis"),
    ("duplicate_detection", "Duplicate detection"),
    ("code_review", "Code review"),
    ("technical_debt", "Technical debt"),
    ("architecture", "Architecture"),
    ("github_issues", "GitHub issues"),
    ("health", "Health score"),
    ("contribution_intelligence", "Contribution intelligence"),
    ("report", "Report"),
]

# (stage_key, status, message) where status is running|done|skipped
ProgressCallback = Callable[[str, str, "str | None"], None]


class AnalysisError(Exception):
    """A failure that stops the analysis, with a user-facing message."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class StageSkipped(Exception):
    """A stage that could not produce results; the analysis continues."""


@dataclass
class EngineRun:
    """Raw engine objects for one completed analysis."""

    repo_url: str
    owner: str | None
    name: str
    repo_path: str
    repository_info: dict = field(default_factory=dict)
    metrics: list = field(default_factory=list)
    git_metrics: list = field(default_factory=list)
    dataset: Any = None
    predictions: Any = None
    ml_results: dict | None = None
    ml_best_model: str | None = None
    ml_class_distribution: dict | None = None
    ml_unavailable_reason: str | None = None
    duplicate_pairs: Any = None
    duplicate_summary: dict | None = None
    duplicate_signal: Any = None
    review_findings: Any = None
    review_summary: dict | None = None
    technical_debt: Any = None
    technical_debt_summary: dict | None = None
    dependency_graph: Any = None
    architecture_report: dict | None = None
    full_centrality: list = field(default_factory=list)
    issue_result: dict | None = None
    issue_matches: dict = field(default_factory=dict)
    health_report: dict | None = None
    opportunities: list = field(default_factory=list)
    file_intelligence: dict = field(default_factory=dict)
    file_intelligence_limited: bool = False
    report_html: str | None = None
    stage_notes: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)

    def scrub(self, text: Any) -> str:
        """Remove internal filesystem paths from a message shown to users."""
        message = str(text)
        for secret in {self.repo_path, os.path.abspath(self.repo_path), str(ENGINE_ROOT)}:
            if secret:
                message = message.replace(secret + os.sep, "").replace(secret, "<repository>")
        return message


class _StdoutToLog(io.TextIOBase):
    """Send the engine's print() output to the debug log instead of stdout."""

    def write(self, text: str) -> int:
        stripped = text.strip()
        if stripped:
            LOGGER.debug(stripped)
        return len(text)


# ---------------------------------------------------------------------------
# Engine imports (lazy, so the API can start even if an engine dependency is
# missing; the analysis then fails with a clear message).
# ---------------------------------------------------------------------------

def _engine():
    try:
        from analyzer.repository_analyzer import RepositoryAnalyzer
        from metrics.code_metrics import CodeMetricsExtractor
        from git_analysis.git_history_analyzer import GitHistoryAnalyzer
        from ml.feature_engineering import FeatureEngineer
        from ml.defect_prediction import DefectPredictionModel
        from analysis.health_score import RepositoryHealthScore
        from analysis.contribution_opportunities import ContributionOpportunityGenerator
        from analysis.risk_explanation import FileRiskExplainer
        from analysis.contribution_plan import ContributionPlanGenerator
        from analysis.dependency_analyzer import StaticDependencyAnalyzer
        from analysis.related_files import RelatedFilesFinder
        from analysis.dependency_impact import DependencyImpactAnalyzer
        from analysis.git_history_context import GitHistoryContext
        from analysis.technical_debt import TechnicalDebtAnalyzer
        from analysis.duplicate_code import DuplicateCodeDetector
        from analysis.architecture_diagram import ArchitectureDiagramGenerator
        from analysis.code_review import RuleBasedCodeReviewer
        from analysis.html_report import HtmlReportGenerator
        from github.issue_analyzer import GitHubIssueAnalyzer
        import codepulse_runtime as runtime
    except ImportError as error:  # pragma: no cover - environment problem
        raise AnalysisError(
            "engine_unavailable",
            f"The CodePulse analysis engine could not be loaded ({error}). "
            "Install the backend requirements with pip install -r backend/requirements.txt.",
        ) from error

    return {name: value for name, value in locals().items() if name != "error"}


def _cached_risk_explainer(base):
    """FileRiskExplainer with its per-call maintainability lookup memoised.

    ``explain()`` rebuilds the same repository-wide maintainability map on
    every call; caching it keeps per-file intelligence linear in repository
    size without changing the explainer's results.
    """

    class CachedFileRiskExplainer(base):
        def __init__(self):
            self._maintainability_cache = {}

        def _maintainability_by_file(self, code_metrics, repository_path):
            key = (id(code_metrics), str(repository_path))
            if key not in self._maintainability_cache:
                self._maintainability_cache[key] = base._maintainability_by_file(
                    code_metrics, repository_path
                )
            return self._maintainability_cache[key]

    return CachedFileRiskExplainer()


# ---------------------------------------------------------------------------
# GitHub checks and clone error classification
# ---------------------------------------------------------------------------

def _preflight_github(owner: str, name: str, run: EngineRun) -> None:
    """Check the repository is public and reachable before cloning."""
    import requests

    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.get(
            f"https://api.github.com/repos/{owner}/{name}", headers=headers, timeout=15
        )
    except requests.RequestException:
        run.warnings.append(
            "Could not reach the GitHub API to verify the repository; trying to clone it directly."
        )
        return

    if response.status_code == 404:
        raise AnalysisError(
            "repository_not_found",
            f"Repository {owner}/{name} was not found. It may not exist, or it may be private. "
            "CodePulse can only analyze public GitHub repositories.",
        )
    if response.status_code in (403, 429):
        run.warnings.append(
            "GitHub API rate limit reached while verifying the repository. "
            "Issue analysis may be unavailable; set GITHUB_TOKEN to raise the limit."
        )
        return
    if response.ok and response.json().get("private"):
        raise AnalysisError(
            "private_repository",
            f"{owner}/{name} is a private repository. CodePulse can only analyze public repositories.",
        )


def _classify_git_error(error: Exception) -> AnalysisError:
    text = str(error).lower()
    if "not found" in text or "could not read username" in text or "authentication" in text:
        return AnalysisError(
            "repository_not_found",
            "The repository could not be cloned. It may not exist or may be private.",
        )
    if "could not resolve host" in text or "unable to access" in text or "timed out" in text:
        return AnalysisError(
            "network_error",
            "Could not connect to GitHub to clone the repository. Check the server's internet connection.",
        )
    return AnalysisError("clone_failed", "Git could not clone the repository.")


def _refresh_existing_clone(repo_path: str, run: EngineRun) -> None:
    """Bring a previously cloned repository up to date before re-analysis."""
    try:
        from git import Repo

        repo = Repo(repo_path)
        origin = repo.remotes.origin
        origin.fetch(prune=True)
        try:
            target = origin.refs.HEAD.reference.name  # e.g. origin/main
        except (TypeError, AttributeError, ValueError, IndexError):
            target = f"origin/{repo.active_branch.name}"
        repo.git.reset("--hard", target)
    except Exception as error:  # noqa: BLE001 - analysis can proceed on the old clone
        LOGGER.warning("Could not refresh existing clone: %s", error)
        run.warnings.append(
            "Could not fetch the latest changes; the previously downloaded copy was analyzed."
        )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_engine(
    repo_url: str,
    *,
    owner: str | None,
    name: str,
    progress: ProgressCallback,
    check_github: bool = True,
    max_file_intelligence: int = 3000,
) -> EngineRun:
    """Run every analysis stage and return the raw engine results.

    ``repo_url`` is passed straight to the engine (a GitHub URL in production;
    tests also pass a local repository path with ``check_github=False``).
    """
    with ENGINE_LOCK, contextlib.redirect_stdout(_StdoutToLog()):
        return _run_pipeline(
            repo_url,
            owner=owner,
            name=name,
            progress=progress,
            check_github=check_github,
            max_file_intelligence=max_file_intelligence,
        )


def _run_pipeline(repo_url, *, owner, name, progress, check_github, max_file_intelligence):
    e = _engine()
    runtime = e["runtime"]

    def stage(key, func, optional=False):
        progress(key, "running", None)
        try:
            note = func()
        except StageSkipped as skipped:
            message = run.scrub(skipped)
            run.stage_notes[key] = message
            run.warnings.append(message)
            progress(key, "skipped", message)
            return
        except AnalysisError:
            raise
        except Exception as error:  # noqa: BLE001
            LOGGER.exception("Stage %s failed", key)
            if not optional:
                raise AnalysisError(
                    f"{key}_failed",
                    f"{dict(STAGES)[key]} failed: {run.scrub(error)}",
                ) from error
            message = f"{dict(STAGES)[key]} is unavailable: {run.scrub(error)}"
            run.stage_notes[key] = message
            run.warnings.append(message)
            progress(key, "skipped", message)
            return
        progress(key, "done", note)

    analyzer = e["RepositoryAnalyzer"](repo_url)
    run = EngineRun(repo_url=repo_url, owner=owner, name=name, repo_path=analyzer.repo_path)

    # 1. Repository access -------------------------------------------------
    def access():
        if check_github and owner:
            _preflight_github(owner, name, run)
        existed = os.path.exists(analyzer.repo_path)
        try:
            analyzer.clone_repository()
        except RuntimeError as error:  # identity collision in data/repositories
            raise AnalysisError("clone_failed", run.scrub(error)) from error
        except Exception as error:  # noqa: BLE001 - GitPython errors
            raise _classify_git_error(error) from error
        if existed:
            _refresh_existing_clone(analyzer.repo_path, run)
            return "Updated existing copy"
        return "Cloned"

    stage("repository_access", access)

    # 2. Repository structure ---------------------------------------------
    def structure():
        run.repository_info = analyzer.analyze()
        if int(run.repository_info.get("commits") or 0) < 2:
            run.warnings.append(
                "This repository has very little Git history, so history-based signals "
                "(churn, bug-fix activity, historical risk) will be limited."
            )
        return f"{run.repository_info.get('total_files', 0)} files"

    stage("repository_structure", structure)

    # 3. Code metrics -----------------------------------------------------
    def code_metrics():
        run.metrics = e["CodeMetricsExtractor"](analyzer.repo_path).analyze_repository()
        if not run.metrics:
            raise AnalysisError(
                "no_source_files",
                "No supported source files were found. CodePulse analyzes Python, "
                "JavaScript, TypeScript, React, HTML, CSS and Java.",
            )
        return f"{len(run.metrics)} source files"

    stage("code_metrics", code_metrics)

    # 4. Git history (repository-level git log --numstat parsing) ---------
    def git_history():
        run.git_metrics = e["GitHistoryAnalyzer"](
            analyzer.repo_path,
            source_files=[item["file"] for item in run.metrics],
        ).analyze_repository()
        return f"{len(run.git_metrics)} files with history"

    stage("git_history", git_history)

    # 5. Feature engineering + ML historical-risk model -------------------
    def ml_risk():
        feature_engineer = e["FeatureEngineer"](analyzer.repo_path)
        run.dataset = feature_engineer.prepare_dataset(run.metrics, run.git_metrics)
        runtime.invalidate_analysis_artifacts("starting a new repository analysis")
        if run.dataset is None or run.dataset.empty:
            raise AnalysisError(
                "dataset_unavailable",
                "The feature dataset could not be built from this repository's code and Git history.",
            )
        feature_engineer.save_dataset(run.dataset, runtime.FEATURES_PATH)
        runtime.write_run_metadata(repo_url, runtime.FEATURES_PATH, runtime.PREDICTIONS_PATH)

        if not runtime.dataset_is_valid_for_run(run.dataset, repo_url):
            raise AnalysisError(
                "dataset_unavailable",
                "The feature dataset did not match this repository.",
            )

        model = e["DefectPredictionModel"](runtime.FEATURES_PATH)
        try:
            run.ml_results = model.run()
        except ValueError as error:
            run.ml_class_distribution = getattr(model, "class_distribution", None) or None
            run.ml_unavailable_reason = str(error)
            raise StageSkipped(f"ML risk analysis skipped: {error}") from error
        run.ml_class_distribution = getattr(model, "class_distribution", None) or None
        predictions = model.predictions
        if not runtime.predictions_are_valid_for_run(predictions, run.dataset, repo_url):
            runtime.invalidate_analysis_artifacts(
                "ML predictions did not match the current repository"
            )
            run.ml_unavailable_reason = "Model predictions did not match the analyzed files."
            raise StageSkipped("ML risk analysis skipped: predictions did not match the analyzed files.")
        run.predictions = predictions
        if run.ml_results:
            # Same selection rule as DefectPredictionModel.select_best_model().
            run.ml_best_model = max(run.ml_results, key=lambda key: run.ml_results[key]["f1"])
        return f"{len(predictions)} files scored"

    stage("ml_risk", ml_risk, optional=True)

    # 6. Duplicate detection ----------------------------------------------
    def duplicates():
        detector = e["DuplicateCodeDetector"](analyzer.repo_path)
        run.duplicate_pairs = detector.analyze()
        run.duplicate_summary = detector.summarize(run.duplicate_pairs)
        run.duplicate_signal = detector.per_file_signal(run.duplicate_pairs)
        detector.save(run.duplicate_pairs)
        return f"{run.duplicate_summary.get('duplicate_groups', 0)} groups"

    stage("duplicate_detection", duplicates, optional=True)

    # 7. Rule-based code review -------------------------------------------
    def review():
        reviewer = e["RuleBasedCodeReviewer"]()
        run.review_findings = reviewer.review(
            run.dataset,
            code_metrics=run.metrics,
            duplicate_pairs=run.duplicate_pairs,
            repository_path=analyzer.repo_path,
        )
        run.review_summary = reviewer.summarize(
            run.review_findings, files_reviewed=len(run.dataset)
        )
        reviewer.save(run.review_findings)
        return f"{run.review_summary.get('total_findings', 0)} findings"

    stage("code_review", review, optional=True)

    # 8. Technical debt ----------------------------------------------------
    def debt():
        debt_analyzer = e["TechnicalDebtAnalyzer"]()
        run.technical_debt = debt_analyzer.analyze(
            run.dataset,
            run.predictions,
            run.metrics,
            duplication=run.duplicate_signal,
            repository_path=analyzer.repo_path,
        )
        run.technical_debt_summary = debt_analyzer.summarize(run.technical_debt)
        debt_analyzer.save(run.technical_debt)
        return f"Score {run.technical_debt_summary.get('repository_debt_score')}"

    stage("technical_debt", debt, optional=True)

    # 9. Architecture ------------------------------------------------------
    def architecture():
        run.dependency_graph = e["StaticDependencyAnalyzer"](
            analyzer.repo_path, run.dataset["file"].tolist()
        ).build()
        generator = e["ArchitectureDiagramGenerator"](run.dependency_graph)
        run.architecture_report = generator.generate()
        # Uncapped centrality for the interactive graph (same formula).
        run.full_centrality = e["ArchitectureDiagramGenerator"](
            run.dependency_graph, limit=None
        )._centrality()
        if not run.architecture_report.get("graphviz_available"):
            run.warnings.append(
                "Graphviz is not installed, so static architecture images were not rendered. "
                "The interactive architecture view is unaffected."
            )
        return f"{run.architecture_report.get('dependency_relationships', 0)} dependencies"

    stage("architecture", architecture, optional=True)

    # 10. GitHub issues ----------------------------------------------------
    def issues():
        if not owner:
            raise StageSkipped("GitHub issue analysis is only available for GitHub repositories.")
        issue_analyzer = e["GitHubIssueAnalyzer"](run.repository_info.get("repository_url") or repo_url)
        run.issue_result = issue_analyzer.fetch_issues()
        if not run.issue_result.get("available"):
            raise StageSkipped(run.issue_result.get("message") or "GitHub issue analysis unavailable.")
        repo_issues = run.issue_result.get("issues", [])
        run.issue_matches = {
            file_path: issue_analyzer.match_issues(file_path, repo_issues)
            for file_path in run.dataset["file"].tolist()
        }
        return f"{len(repo_issues)} issues"

    stage("github_issues", issues, optional=True)

    # 11. Health score -----------------------------------------------------
    def health():
        run.health_report = e["RepositoryHealthScore"]().calculate(
            run.dataset, run.predictions, run.metrics, analyzer.repo_path
        )
        return f"{run.health_report.get('overall_score')} / 100"

    stage("health", health, optional=True)

    # 12. Contribution intelligence ---------------------------------------
    def contribution():
        run.opportunities = e["ContributionOpportunityGenerator"]().generate(
            run.dataset,
            run.predictions,
            technical_debt=run.technical_debt,
            dependency_graph=run.dependency_graph,
            issue_matches=run.issue_matches,
            review_findings=run.review_findings,
        ) or []
        _build_file_intelligence(e, run, analyzer.repo_path, max_file_intelligence)
        return f"{len(run.opportunities)} opportunities"

    stage("contribution_intelligence", contribution, optional=True)

    # 13. HTML report --------------------------------------------------------
    def report():
        output_path = e["HtmlReportGenerator"]().generate(
            repository_info=run.repository_info,
            dataset=run.dataset,
            health_report=run.health_report,
            predictions=run.predictions,
            ml_results=run.ml_results,
            technical_debt_summary=run.technical_debt_summary,
            duplicate_summary=run.duplicate_summary,
            architecture_report=run.architecture_report,
            review_summary=run.review_summary,
            opportunities=run.opportunities,
            selected=None,
        )
        run.report_html = _inline_report_images(output_path.read_text(encoding="utf-8"), output_path.parent)
        return "Ready"

    stage("report", report, optional=True)
    return run


def _build_file_intelligence(e, run: EngineRun, repo_path: str, limit: int) -> None:
    """Selected-file intelligence, as assembled by workspace.option_analyze_file."""
    files = run.dataset["file"].tolist()
    if len(files) > limit:
        ranked = [item["file"] for item in run.opportunities]
        files = list(dict.fromkeys(ranked + files))[:limit]
        run.file_intelligence_limited = True

    explainer = _cached_risk_explainer(e["FileRiskExplainer"])
    plan_generator = e["ContributionPlanGenerator"]()
    related_finder = e["RelatedFilesFinder"]()
    impact_analyzer = e["DependencyImpactAnalyzer"]()
    history_context = e["GitHistoryContext"]()

    for file_path in files:
        entry: dict = {"file": file_path}
        try:
            explanation = explainer.explain(
                file_path, run.dataset, run.predictions, run.metrics, repo_path
            )
        except Exception as error:  # noqa: BLE001
            entry["explanation_error"] = run.scrub(error)
            run.file_intelligence[file_path] = entry
            continue
        entry["explanation"] = explanation

        related, impact = [], None
        if run.dependency_graph is not None:
            related = related_finder.find(file_path, run.dependency_graph)
            impact = impact_analyzer.analyze(
                file_path, run.dependency_graph, risk_level=explanation.get("risk_level")
            )
        entry["related_files"] = related
        entry["impact"] = impact

        try:
            history = history_context.get_context(file_path, run.git_metrics)
        except (ValueError, KeyError):
            history = None
        entry["history"] = history

        matches = run.issue_matches.get(file_path, [])
        entry["issues"] = matches
        open_issue = next(
            (issue for issue in matches if str(issue.get("state", "UNKNOWN")).upper() == "OPEN"),
            None,
        )
        entry["plan"] = plan_generator.create_plan(
            explanation,
            repo_path,
            context={
                "related_files": related,
                "impact": impact,
                "history": history,
                "open_issue": open_issue,
            },
        )
        entry["open_issue_number"] = open_issue.get("number") if open_issue else None
        run.file_intelligence[file_path] = entry


def _inline_report_images(html: str, directory) -> str:
    """Embed the architecture PNGs so the exported report is self-contained."""
    import base64
    import re
    from pathlib import Path

    def replace(match):
        name = match.group(1)
        path = Path(directory) / name
        if "/" in name or "\\" in name or not path.is_file() or path.stat().st_size > 8_000_000:
            return match.group(0)
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f'src="data:image/png;base64,{data}"'

    return re.sub(r'src="([^"]+\.png)"', replace, html)
