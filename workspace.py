import os
import sys
from pathlib import Path

import pandas as pd

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
from analysis.contributor_view import ContributorView
from github.issue_analyzer import GitHubIssueAnalyzer
from analysis.technical_debt import TechnicalDebtAnalyzer
from analysis.duplicate_code import DuplicateCodeDetector
from analysis.architecture_diagram import ArchitectureDiagramGenerator
from analysis.code_review import RuleBasedCodeReviewer
from analysis.html_report import HtmlReportGenerator
from analysis.contributor_workspace import (
    ContributorWorkspace as ReportingWorkspace
)
from codepulse_runtime import (
    FEATURES_PATH,
    PREDICTIONS_PATH,
    dataset_is_valid_for_run,
    invalidate_analysis_artifacts,
    predictions_are_valid_for_run,
    write_run_metadata,
)


class ContributorPipeline:
    """Run the repository pipeline and prepare the reusable reporting workspace."""

    def __init__(self):
        self.repo_url = None
        self.repository_info = None
        self.metrics = None
        self.git_metrics = None
        self.dataset = None
        self.predictions = None
        self.ml_results = None
        self.health_report = None
        self.opportunities = None
        self.dependency_graph = None
        self.issue_analyzer = None
        self.repo_issues = None
        self.technical_debt = None
        self.technical_debt_summary = None
        self.duplicate_pairs = None
        self.duplicate_summary = None
        self.architecture_report = None
        self.review_findings = None
        self.review_summary = None
        self.issue_matches = {}
        self.selected_file_intelligence = None

    def reporting_workspace(self):
        """Return the canonical contributor reporting layer for this run."""
        return ReportingWorkspace(
            self.repository_info,
            self.dataset,
            self.predictions,
            self.metrics,
            self.git_metrics,
            self.health_report,
            self.opportunities,
            self.dependency_graph,
        )

    # =========================================================
    # Analysis Pipeline
    # =========================================================

    def run_analysis(self, repo_url):
        self.repo_url = repo_url

        print()
        print(
            "=========================================="
        )
        print(
            "              CODEPULSE AI"
        )
        print(
            "        CONTRIBUTOR WORKSPACE"
        )
        print(
            "=========================================="
        )
        print(
            "\nRunning full repository analysis..."
        )
        print(
            "This may take a few minutes for large repositories."
        )

        try:
            analyzer = RepositoryAnalyzer(repo_url)
            self.repository_info = analyzer.analyze()

            print()
            print(
                "=========================================="
            )
            print(
                "        REPOSITORY ANALYSIS"
            )
            print(
                "=========================================="
            )
            print(
                f"Repository : {self.repository_info['repository_name']}"
            )
            print(
                f"Total Files: {self.repository_info['total_files']}"
            )
            print(
                "\nLanguages Detected:"
            )
            for language, count in (
                self.repository_info["languages"].items()
            ):
                print(
                    f"{language:<12}: {count} files"
                )
            print(
                f"\nCommits      : {self.repository_info['commits']}"
            )
            print(
                f"Contributors : {self.repository_info['contributors']}"
            )

            print()
            print(
                "=========================================="
            )
            print(
                "        MULTI-LANGUAGE CODE METRICS"
            )
            print(
                "=========================================="
            )

            metrics_extractor = CodeMetricsExtractor(
                analyzer.repo_path
            )
            self.metrics = metrics_extractor.analyze_repository()

            print()
            print(
                "=========================================="
            )
            print(
                "        GIT HISTORY INTELLIGENCE"
            )
            print(
                "=========================================="
            )

            git_analyzer = GitHistoryAnalyzer(
                analyzer.repo_path,
                source_files=[item["file"] for item in self.metrics],
            )
            self.git_metrics = git_analyzer.analyze_repository()

            print()
            print(
                "=========================================="
            )
            print(
                "        FEATURE ENGINEERING"
            )
            print(
                "=========================================="
            )

            feature_engineer = FeatureEngineer(
                analyzer.repo_path
            )
            self.dataset = feature_engineer.prepare_dataset(
                self.metrics,
                self.git_metrics
            )

            invalidate_analysis_artifacts("starting a new repository analysis")

            if self.dataset.empty:
                print(
                    "\nFeature dataset could not be created; ML will be skipped."
                )
            else:
                print(
                    f"\nFeature dataset created."
                )
                print(
                    f"Total samples: {len(self.dataset)}"
                )
                print(
                    f"Total features: {len(self.dataset.columns)}"
                )

                feature_engineer.save_dataset(
                    self.dataset,
                    FEATURES_PATH
                )
                write_run_metadata(repo_url, FEATURES_PATH, PREDICTIONS_PATH)

            print()
            print(
                "=========================================="
            )
            print(
                "        ML DEFECT PREDICTION"
            )
            print(
                "=========================================="
            )

            self.predictions = None

            try:
                if not dataset_is_valid_for_run(self.dataset, repo_url):
                    raise ValueError(
                        "Current analysis has no valid repository-owned feature dataset."
                    )
                ml_model = DefectPredictionModel(
                    FEATURES_PATH
                )
                self.ml_results = ml_model.run()
                self.predictions = ml_model.predictions
                if not predictions_are_valid_for_run(
                    self.predictions, self.dataset, repo_url
                ):
                    invalidate_analysis_artifacts(
                        "ML predictions did not match the current repository"
                    )
                    self.predictions = None
            except ValueError as error:
                print(
                    "\nPhase 6 is not run for this repository."
                )
                print(
                    f"Reason: {error}"
                )

            print()
            print(
                "=========================================="
            )
            print(
                "          GIT METRICS SUMMARY"
            )
            print(
                "=========================================="
            )

            for metric in self.git_metrics:
                print(
                    "\n------------------------------------------"
                )
                print(
                    f"File: {metric['file']}"
                )
                print(
                    f"Commits: {metric['commit_count']}"
                )
                print(
                    f"Contributors: {metric['contributors']}"
                )
                print(
                    f"Lines Added: {metric['lines_added']}"
                )
                print(
                    f"Lines Deleted: {metric['lines_deleted']}"
                )
                print(
                    f"Code Churn: {metric['code_churn']}"
                )
                print(
                    f"Bug-Fix Commits: {metric['bug_fix_commits']}"
                )
                print(
                    f"File Age (days): {metric['file_age_days']}"
                )
                print(
                    f"Last Modified: {metric['last_modified']}"
                )

            print()
            print(
                "=========================================="
            )
            print(
                "             METRICS SUMMARY"
            )
            print(
                "=========================================="
            )

            for metric in self.metrics:
                print(
                    "\n------------------------------------------"
                )
                print(
                    f"File: {metric['file']}"
                )
                print(
                    f"Language: {metric['language']}"
                )
                print(
                    f"LOC: {metric['loc']}"
                )
                print(
                    f"Complexity: {metric['complexity']}"
                )
                print(
                    f"Maintainability: {metric['maintainability']}"
                )
                print(
                    f"Functions: {metric['functions']}"
                )
                print(
                    f"Classes: {metric['classes']}"
                )
                print(
                    f"Nesting Depth: {metric['nesting_depth']}"
                )
                print(
                    f"Comment Ratio: {metric['comment_ratio']}"
                )

                if metric["elements"] > 0:
                    print(
                        f"HTML Elements: {metric['elements']}"
                    )
                if metric["selectors"] > 0:
                    print(
                        f"CSS Selectors: {metric['selectors']}"
                    )
                if metric["declarations"] > 0:
                    print(
                        f"CSS Declarations: {metric['declarations']}"
                    )
                if metric["important_count"] > 0:
                    print(
                        f"!important Usage: {metric['important_count']}"
                    )

            print()
            print(
                "=========================================="
            )
            print(
                f"Successfully analyzed "
                f"{len(self.metrics)} source files."
            )
            print(
                "=========================================="
            )

            # Pre-fetch GitHub issues
            self._prefetch_issues()

            # Pre-compute health score and opportunities
            self._precompute_derived_data(analyzer.repo_path)

            print()
            print(
                "=========================================="
            )
            print(
                "   ANALYSIS COMPLETE - WORKSPACE READY"
            )
            print(
                "=========================================="
            )

            return True

        except Exception as error:
            print()
            print(
                "Analysis failed."
            )
            print(
                f"Error: {error}"
            )
            return False

    def _precompute_derived_data(self, repo_path):
        try:
            duplicate_detector = DuplicateCodeDetector(repo_path)
            self.duplicate_pairs = duplicate_detector.analyze()
            self.duplicate_summary = duplicate_detector.summarize(
                self.duplicate_pairs
            )
            duplicate_signal = duplicate_detector.per_file_signal(
                self.duplicate_pairs
            )
            duplicate_detector.save(self.duplicate_pairs)

            reviewer = RuleBasedCodeReviewer()
            self.review_findings = reviewer.review(
                self.dataset,
                code_metrics=self.metrics,
                duplicate_pairs=self.duplicate_pairs,
                repository_path=repo_path,
            )
            self.review_summary = reviewer.summarize(
                self.review_findings,
                files_reviewed=len(self.dataset),
            )
            reviewer.save(self.review_findings)

            debt_analyzer = TechnicalDebtAnalyzer()
            self.technical_debt = debt_analyzer.analyze(
                self.dataset,
                self.predictions,
                self.metrics,
                duplication=duplicate_signal,
                repository_path=repo_path,
            )
            self.technical_debt_summary = debt_analyzer.summarize(
                self.technical_debt
            )
            debt_analyzer.save(self.technical_debt)

        except Exception as error:
            self.duplicate_pairs = None
            self.duplicate_summary = None
            self.technical_debt = None
            self.technical_debt_summary = None
            self.review_findings = None
            self.review_summary = None
            print(f"\nWarning: duplicate/debt analysis is unavailable: {error}")

        try:
            if not self.dataset.empty:
                self.dependency_graph = StaticDependencyAnalyzer(
                    repo_path,
                    self.dataset["file"].tolist(),
                ).build()
                self.architecture_report = ArchitectureDiagramGenerator(
                    self.dependency_graph
                ).generate()
        except Exception as error:
            self.architecture_report = None
            print(f"\nWarning: architecture diagram generation is unavailable: {error}")

        try:
            health_calculator = RepositoryHealthScore()
            self.health_report = health_calculator.calculate(
                self.dataset,
                self.predictions,
                self.metrics,
                repo_path
            )
        except Exception:
            self.health_report = None
            print("\nWarning: repository health could not be calculated.")

        try:
            opportunity_generator = ContributionOpportunityGenerator()
            self.opportunities = opportunity_generator.generate(
                self.dataset,
                self.predictions,
                technical_debt=self.technical_debt,
                dependency_graph=self.dependency_graph,
                issue_matches=self.issue_matches,
                review_findings=self.review_findings,
            )
        except Exception:
            self.opportunities = []
            print("\nWarning: contribution opportunities could not be calculated.")

    def _prefetch_issues(self):
        if not self.repository_info:
            return
        try:
            self.issue_analyzer = GitHubIssueAnalyzer(
                self.repository_info["repository_url"]
            )
            self.repo_issues = self.issue_analyzer.fetch_issues()
            if self.repo_issues.get("available"):
                issues = self.repo_issues.get("issues", [])
                self.issue_matches = {
                    file_path: self.issue_analyzer.match_issues(file_path, issues)
                    for file_path in (self.dataset["file"].tolist() if self.dataset is not None else [])
                }
        except Exception:
            self.issue_analyzer = None
            self.repo_issues = None
            self.issue_matches = {}
            print("\nWarning: GitHub issue analysis is unavailable; continuing without it.")

    # =========================================================
    # Menu Display
    # =========================================================

    def show_main_menu(self):
        print()
        print(
            "=========================================="
        )
        print(
            "             CODEPULSE AI"
        )
        print(
            "        CONTRIBUTOR WORKSPACE"
        )
        print(
            "=========================================="
        )
        print(
            f"\nRepository:\n{self.repository_info['repository_name']}"
        )

        if self.health_report:
            print(
                f"\nHealth Score:\n"
                f"{self.health_report['overall_score']:.0f} / 100"
            )
        else:
            print(
                "\nHealth Score:\nNot available"
            )

        print(
            "\nChoose an option:"
        )
        print()
        print(
            "1. Repository Health"
        )
        print(
            "2. Contribution Opportunities"
        )
        print(
            "3. Find Beginner Opportunities"
        )
        print(
            "4. Find Intermediate Opportunities"
        )
        print(
            "5. Find Advanced Opportunities"
        )
        print(
            "6. View Top Risk Files"
        )
        print(
            "7. Analyze a File"
        )
        print(
            "8. View GitHub Issues"
        )
        print(
            "9. Technical Debt Analysis"
        )
        print(
            "10. Duplicate Code Analysis"
        )
        print(
            "11. Architecture Analysis"
        )
        print(
            "12. Rule-Based Code Review"
        )
        print(
            "13. Generate HTML Report"
        )
        print(
            "14. Exit"
        )

    # =========================================================
    # Menu Options
    # =========================================================

    def option_repository_health(self):
        if not self.health_report:
            print(
                "\nRepository health is not available."
            )
            return

        report = self.health_report
        components = report["components"]

        print()
        print(
            "=========================================="
        )
        print(
            "         REPOSITORY HEALTH REPORT"
        )
        print(
            "=========================================="
        )
        print(
            f"Repository: {self.repository_info['repository_name']}"
        )
        print(
            f"Overall Health Score: {report['overall_score']:.1f} / 100"
        )
        print(
            f"Health Level: {report['health_level'].upper()}"
        )
        print(
            f"Code Quality:       {components['code_quality']:.1f} / 100"
        )
        print(
            f"Git Stability:      {components['git_stability']:.1f} / 100"
        )

        if "maintainability" in components:
            print(
                f"Maintainability:    {components['maintainability']:.1f} / 100"
            )
        else:
            print(
                "Maintainability:    Not available for analyzed languages"
            )

        if "defect_risk" in components:
            print(
                f"Defect Risk Health: {components['defect_risk']:.1f} / 100"
            )
        else:
            print(
                "Defect Risk Health: Not available (ML training skipped)"
            )

        high_risk_count = 0
        critical_count = 0
        if self.predictions is not None and not self.predictions.empty:
            high_risk_count = len(
                self.predictions[
                    self.predictions["risk_level"].isin(
                        ["High", "Critical"]
                    )
                ]
            )
            critical_count = len(
                self.predictions[
                    self.predictions["risk_level"] == "Critical"
                ]
            )

        print(
            f"\nHigh-Risk File Count: {high_risk_count}"
        )
        print(
            f"Critical File Count: {critical_count}"
        )
        print(
            "=========================================="
        )

    def option_contribution_opportunities(self):
        if not self.opportunities:
            print(
                "\nNo contribution opportunities available."
            )
            return

        print()
        print(
            "=========================================="
        )
        print(
            "     SUGGESTED CONTRIBUTION OPPORTUNITIES"
        )
        print(
            "=========================================="
        )
        print(
            "Note: Opportunities are suggested based on measurable file metrics."
        )
        print(
            "Choose the level that matches your desired contribution scope.\n"
        )

        levels = ["BEGINNER", "INTERMEDIATE", "ADVANCED"]
        found_any = False

        for lvl in levels:
            group = [
                op for op in self.opportunities
                if op["difficulty"] == lvl
            ]
            if not group:
                continue

            found_any = True
            suggested_for = (
                group[0]["suggested_for"]
                if group else ""
            )
            print(
                f"--- {lvl} OPPORTUNITIES ({suggested_for}) ---"
            )
            for index, opportunity in enumerate(
                group[:10], start=1
            ):
                print(
                    f"\n{index}. {opportunity['title']}"
                )
                print(
                    f"   File: {opportunity['file']}"
                )
                print(
                    f"   Priority: {opportunity['priority']}"
                )
                print(
                    f"   Opportunity Score: "
                    f"{opportunity.get('opportunity_score', opportunity.get('score', 0)):.2f}"
                )
                print(
                    f"   Difficulty: {opportunity['difficulty']} "
                    f"({opportunity['suggested_for']})"
                )
                print(
                    f"   Impact: {opportunity.get('impact', 'Not available')}"
                )
                print(
                    f"   Issue status: "
                    f"{opportunity.get('related_issue_status', 'NONE/UNAVAILABLE')}"
                )
                print(
                    "   Evidence:"
                )
                for reason in opportunity["reasons"]:
                    print(
                        f"   - {reason}"
                    )
                print(
                    f"   Suggested action: "
                    f"{opportunity['suggested_action']}"
                )
            print()

        if not found_any:
            print(
                "No opportunities found matching current evidence rules."
            )

        print(
            "=========================================="
        )

    def option_filter_opportunities(self, level):
        level_map = {
            "3": "BEGINNER",
            "beginner": "BEGINNER",
            "4": "INTERMEDIATE",
            "intermediate": "INTERMEDIATE",
            "5": "ADVANCED",
            "advanced": "ADVANCED",
        }
        selected_level = level_map.get(
            str(level).lower(), str(level).upper()
        )

        if not self.opportunities:
            print(
                "\nNo contribution opportunities available."
            )
            return

        filtered = [
            op for op in self.opportunities
            if op["difficulty"] == selected_level
        ]

        if not filtered:
            print(
                f"\nNo {selected_level} opportunities found."
            )
            return

        print()
        print(
            "=========================================="
        )
        print(
            f"     {selected_level} CONTRIBUTION OPPORTUNITIES"
        )
        print(
            "=========================================="
        )

        for index, opportunity in enumerate(
            filtered[:10], start=1
        ):
            print(
                f"\n{index}. {opportunity['title']}"
            )
            print(
                f"   File: {opportunity['file']}"
            )
            print(
                f"   Priority: {opportunity['priority']}"
            )
            print(
                f"   Difficulty: {opportunity['difficulty']} "
                f"({opportunity['suggested_for']})"
            )
            print(
                "   Evidence:"
            )
            for reason in opportunity["reasons"]:
                print(
                    f"   - {reason}"
                )
            print(
                f"   Suggested action: "
                f"{opportunity['suggested_action']}"
            )

        print()
        print(
            "=========================================="
        )

    def option_view_top_risk_files(self):
        if (
            self.predictions is None
            or self.predictions.empty
        ):
            print(
                "\nML predictions are not available for this repository."
            )
            return

        print()
        print(
            "=========================================="
        )
        print(
            "           TOP RISK FILES"
        )
        print(
            "=========================================="
        )

        top_risks = self.predictions.head(20)

        for index, row in top_risks.iterrows():
            print(
                f"\n{index + 1}. {row['file']}"
            )
            print(
                f"   Risk Level: {row['risk_level'].upper()}"
            )
            print(
                f"   Probability: {row['bug_probability']:.0%}"
            )

        print()
        print(
            "=========================================="
        )

    def option_analyze_file(self):
        if not self.dataset.empty:
            file_path = input(
                "\nEnter file path: "
            ).strip()
        else:
            file_path = None

        if not file_path:
            print(
                "\nFile path cannot be empty."
            )
            return

        normalized_path = file_path.replace("\\", "/")
        matches = self.dataset[self.dataset["file"] == normalized_path]

        if matches.empty:
            print(
                f"\nFile not found in dataset: {normalized_path}"
            )
            print(
                "Available files:"
            )
            for f in self.dataset["file"].tolist()[:20]:
                print(f"  - {f}")
            if len(self.dataset) > 20:
                print(f"  ... and {len(self.dataset) - 20} more")
            return

        try:
            explanation = FileRiskExplainer().explain(
                normalized_path,
                self.dataset,
                self.predictions,
                self.metrics,
                self.repository_info["repository_path"]
            )
        except Exception as error:
            print(
                f"\nRisk explanation failed: {error}"
            )
            explanation = None

        try:
            plan = ContributionPlanGenerator().create_plan(
                explanation,
                self.repository_info["repository_path"]
            )
        except Exception as error:
            print(
                f"\nContribution plan generation failed: {error}"
            )
            plan = None

        related_files = []
        impact = {
            "impact_level": "Not available",
            "available": False,
        }
        history = {
            "commit_count": 0,
            "contributors": 0,
            "bug_fix_commits": 0,
        }
        issues = {
            "available": False,
            "matches": [],
        }

        if self.dependency_graph:
            try:
                related_files = RelatedFilesFinder().find(
                    normalized_path,
                    self.dependency_graph
                )
            except Exception:
                related_files = []

            try:
                impact = DependencyImpactAnalyzer().analyze(
                    normalized_path,
                    self.dependency_graph
                )
            except Exception:
                pass

        if self.git_metrics:
            try:
                history = GitHistoryContext().get_context(
                    normalized_path,
                    self.git_metrics
                )
            except Exception:
                pass

        if self.issue_analyzer:
            try:
                issues = self.issue_analyzer.analyze_file(
                    normalized_path
                )
            except Exception:
                issues = {"available": False, "matches": []}

        if explanation:
            open_issue = next(
                (
                    issue for issue in issues.get("matches", [])
                    if str(issue.get("state", "UNKNOWN")).upper() == "OPEN"
                ),
                None,
            )
            try:
                plan = self.plan_generator.create_plan(
                    explanation,
                    self.repository_info["repository_path"],
                    context={
                        "related_files": related_files,
                        "impact": impact,
                        "history": history,
                        "open_issue": open_issue,
                    },
                )
            except Exception as error:
                print(f"\nContribution plan enrichment failed: {error}")

        debt_match = self.technical_debt.iloc[0:0] if self.technical_debt is not None else None
        debt_level = None

        print()
        print(
            "------------------------------------------"
        )
        print(
            "          FILE CONTRIBUTOR ANALYSIS"
        )
        print(
            "------------------------------------------"
        )
        print(
            f"\nFile:\n{normalized_path}"
        )

        if explanation:
            print(
                f"\nML Risk:\n{explanation['risk_level'].upper()}"
            )
            print(
                f"\nML Probability:\n{explanation['bug_probability']:.0%}"
            )

        if self.technical_debt is not None:
            debt_match = self.technical_debt[
                self.technical_debt["file"] == normalized_path
            ]
            if not debt_match.empty:
                debt_row = debt_match.iloc[0]
                debt_level = debt_row["technical_debt_level"]
                print(
                    f"\nTechnical Debt:\n"
                    f"{debt_row['technical_debt_score']:.1f}/100 "
                    f"({debt_row['technical_debt_level']})"
                )
                print("Debt evidence:")
                for reason in debt_row["debt_reasons"]:
                    print(f"- {reason}")

        if self.duplicate_pairs is not None:
            matches = self.duplicate_pairs[
                (self.duplicate_pairs["file_a"] == normalized_path)
                | (self.duplicate_pairs["file_b"] == normalized_path)
            ]
            print(f"\nSimilar code pairs: {len(matches)}")

        if self.review_findings is not None:
            findings = self.review_findings[
                self.review_findings["file"] == normalized_path
            ]
            if not findings.empty:
                print("\nCODE REVIEW FINDINGS")
                for _, finding in findings.iterrows():
                    print(f"{finding['severity']} - {finding['rule_id']}")
                    print(f"{finding['evidence']}")
                    print(f"Recommendation: {finding['recommendation']}")

        if explanation and explanation["reasons"]:
            print(
                "\nWhy risky:"
            )
            for reason in explanation["reasons"]:
                print(
                    f"- {reason}"
                )

        self.selected_file_intelligence = {
            "explanation": explanation,
            "debt_level": debt_level,
            "impact": impact,
            "history": history,
            "plan": plan,
        }

        print(
            "\nGit history:"
        )
        print(
            f"{history['commit_count']} commits"
        )
        print(
            f"{history['contributors']} contributors"
        )
        print(
            f"{history['bug_fix_commits']} bug-fix commits"
        )

        print(
            "\nRelated files:"
        )
        if related_files:
            for related in related_files:
                print(
                    f"- {related['file']}"
                )
        else:
            print(
                "- None detected"
            )

        print(
            f"\nDependency impact:\n{impact.get('impact_level', 'Not available')}"
        )

        print(
            "\nRelated GitHub Issues:"
        )
        if issues.get("available") and issues.get("matches"):
            for issue in issues["matches"][:5]:
                print(
                    f"#{issue['number']}  {issue['title']}"
                )
        else:
            print(
                "- None found"
            )

        if plan:
            print(
                f"\nSuggested contribution:\n{plan['contribution_type']}"
            )
            print(
                f"\nDifficulty:\n{plan['difficulty']}"
            )

            print(
                "\nContribution Plan:"
            )
            for number, step in enumerate(
                plan["steps"], start=1
            ):
                print(
                    f"{number}. {step}"
                )

        print(
            "------------------------------------------"
        )

    def option_view_github_issues(self):
        if not self.repo_issues:
            print(
                "\nGitHub issues are not available for this repository."
            )
            return

        print()
        print(
            "=========================================="
        )
        print(
            "          REPOSITORY GITHUB ISSUES"
        )
        print(
            "=========================================="
        )

        if not self.repo_issues.get("available"):
            print(
                f"\n{self.repo_issues.get('message', 'Issues unavailable.')}"
            )
            print(
                "=========================================="
            )
            return

        issues = self.repo_issues.get("issues", [])
        if not issues:
            print(
                "\nNo issues found for this repository."
            )
            print(
                "=========================================="
            )
            return

        print(
            f"\nTotal issues: {len(issues)}\n"
        )
        for issue in issues[:20]:
            labels = ", ".join(
                label.get("name", "")
                for label in issue.get("labels", [])
            )
            print(
                f"#{issue.get('number')}  {issue.get('title')}"
            )
            print(
                f"   Status: {(issue.get('state') or 'unknown').upper()}"
            )
            print(
                f"   Labels: {labels or 'None'}"
            )
            print(
                f"   Author: {(issue.get('user') or {}).get('login', 'unknown')}"
            )
            print(
                f"   URL: {issue.get('html_url')}\n"
            )

        if len(issues) > 20:
            print(
                f"... and {len(issues) - 20} more issues."
            )

        print(
            "=========================================="
        )

    def option_technical_debt(self):
        if not self.technical_debt_summary:
            print("\nTechnical debt analysis is not available.")
            return
        TechnicalDebtAnalyzer.print_report(self.technical_debt_summary)

    def option_duplicate_code(self):
        if not self.duplicate_summary:
            print("\nDuplicate code analysis is not available.")
            return
        DuplicateCodeDetector.print_report(self.duplicate_summary)

    def option_architecture(self):
        if not self.architecture_report:
            print("\nArchitecture analysis is not available.")
            return
        ArchitectureDiagramGenerator.print_report(self.architecture_report)

    def option_code_review(self):
        if not self.review_summary:
            print("\nRule-based code review is not available.")
            return
        RuleBasedCodeReviewer.print_report(self.review_summary)

    def option_generate_html_report(self):
        try:
            output_path = HtmlReportGenerator().generate(
                repository_info=self.repository_info,
                dataset=self.dataset,
                health_report=self.health_report,
                predictions=self.predictions,
                ml_results=self.ml_results,
                technical_debt_summary=self.technical_debt_summary,
                duplicate_summary=self.duplicate_summary,
                architecture_report=self.architecture_report,
                review_summary=self.review_summary,
                opportunities=self.opportunities,
                selected=self.selected_file_intelligence,
            )
            print(f"\nHTML report generated: {output_path}")
        except Exception as error:
            print(f"\nHTML report generation failed: {error}")

    # =========================================================
    # Main Loop
    # =========================================================

    def run(self):
        repo_url = input(
            "\nEnter GitHub repository URL: "
        ).strip()

        if not repo_url:
            print(
                "Repository URL cannot be empty."
            )
            return

        success = self.run_analysis(repo_url)
        if not success:
            return

        while True:
            self.show_main_menu()

            choice = input(
                "\nEnter choice: "
            ).strip()

            if choice == "1":
                self.option_repository_health()
            elif choice == "2":
                self.option_contribution_opportunities()
            elif choice == "3":
                self.option_filter_opportunities("BEGINNER")
            elif choice == "4":
                self.option_filter_opportunities("INTERMEDIATE")
            elif choice == "5":
                self.option_filter_opportunities("ADVANCED")
            elif choice == "6":
                self.option_view_top_risk_files()
            elif choice == "7":
                self.option_analyze_file()
            elif choice == "8":
                self.option_view_github_issues()
            elif choice == "9":
                self.option_technical_debt()
            elif choice == "10":
                self.option_duplicate_code()
            elif choice == "11":
                self.option_architecture()
            elif choice == "12":
                self.option_code_review()
            elif choice == "13":
                self.option_generate_html_report()
            elif choice == "14":
                print(
                    "\nExiting CodePulse AI Contributor Workspace."
                )
                print(
                    "Good luck with your contributions!"
                )
                break
            else:
                print(
                    "\nInvalid choice. Please enter a number between 1 and 14."
                )


def main():
    try:
        workspace = ContributorWorkspace()
        workspace.run()
    except KeyboardInterrupt:
        print(
            "\n\nExiting CodePulse AI Contributor Workspace."
        )
        print(
            "Good luck with your contributions!"
        )
        sys.exit(0)


# Backward-compatible import for existing callers and scripts.
ContributorWorkspace = ContributorPipeline


if __name__ == "__main__":
    main()
