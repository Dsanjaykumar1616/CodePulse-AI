import os
from pathlib import Path
import pandas as pd

from analysis.risk_explanation import FileRiskExplainer
from analysis.contribution_plan import ContributionPlanGenerator
from analysis.related_files import RelatedFilesFinder
from analysis.dependency_impact import DependencyImpactAnalyzer
from analysis.git_history_context import GitHistoryContext
from analysis.contribution_opportunities import ContributionOpportunityGenerator
from github.issue_analyzer import GitHubIssueAnalyzer


class ContributorWorkspace:
    """Complete interactive contributor workspace for CodePulse AI."""

    def __init__(self, repository_info, dataset, predictions, metrics,
                 git_metrics, health_report, opportunities, dependency_graph):
        self.repository_info = repository_info
        self.repository_name = repository_info.get("repository_name", "Unknown Repository")
        self.repository_url = repository_info.get("repository_url", "")
        self.repository_path = repository_info.get("repository_path", "")
        self.dataset = dataset if dataset is not None else pd.DataFrame()
        self.predictions = predictions
        self.metrics = metrics or []
        self.git_metrics = git_metrics or []
        self.health_report = health_report or {}
        self.opportunities = opportunities or []
        self.dependency_graph = dependency_graph

        self.risk_explainer = FileRiskExplainer()
        self.plan_generator = ContributionPlanGenerator()
        self.related_finder = RelatedFilesFinder()
        self.impact_analyzer = DependencyImpactAnalyzer()
        self.history_context_analyzer = GitHistoryContext()
        self.issue_analyzer = (
            GitHubIssueAnalyzer(self.repository_url)
            if self.repository_url else None
        )

    def _get_overall_health_score(self):
        score = self.health_report.get("overall_score", 0.0)
        return f"{score:.0f}"

    def show_repository_health(self):
        """Option 1: Show comprehensive repository health overview."""
        print("\n==========================================")
        print("          REPOSITORY HEALTH OVERVIEW")
        print("==========================================")
        print(f"Repository: {self.repository_name}")
        overall = self.health_report.get("overall_score", 0.0)
        level = self.health_report.get("health_level", "Unknown").upper()
        print(f"Overall Health: {overall:.1f} / 100 ({level})")

        components = self.health_report.get("components", {})
        print(f"\nCode Quality:       {components.get('code_quality', 0):.1f} / 100")
        if "maintainability" in components:
            print(f"Maintainability:    {components.get('maintainability', 0):.1f} / 100")
        else:
            print("Maintainability:    Not available for analyzed languages")
        print(f"Git Stability:      {components.get('git_stability', 0):.1f} / 100")
        if "defect_risk" in components:
            print(f"Defect Risk Health: {components.get('defect_risk', 0):.1f} / 100")

        # High-risk and Critical file counts
        critical_count = 0
        high_count = 0
        medium_count = 0
        low_count = 0

        if self.predictions is not None and not self.predictions.empty:
            for _, row in self.predictions.iterrows():
                risk = str(row.get("risk_level", "")).upper()
                if risk == "CRITICAL":
                    critical_count += 1
                elif risk == "HIGH":
                    high_count += 1
                elif risk == "MEDIUM":
                    medium_count += 1
                elif risk == "LOW":
                    low_count += 1

        print(f"\nCritical-Risk Files: {critical_count}")
        print(f"High-Risk Files:     {high_count}")
        print(f"Medium-Risk Files:   {medium_count}")
        print(f"Low-Risk Files:      {low_count}")
        print("==========================================")

    def show_opportunities(self, level=None, limit=10):
        """Option 2-5: Show contribution opportunities with difficulty filtering."""
        if not self.opportunities:
            print("\nNo contribution opportunities available.")
            return

        if level:
            filtered = ContributionOpportunityGenerator.filter_by_level(self.opportunities, level)
            title = f"{level.upper()} CONTRIBUTION OPPORTUNITIES"
        else:
            filtered = self.opportunities
            title = "ALL CONTRIBUTION OPPORTUNITIES"

        print("\n==========================================")
        print(f"        {title}")
        print("==========================================")
        if not filtered:
            print(f"No {level or ''} contribution opportunities found.")
            print("==========================================")
            return

        for index, op in enumerate(filtered[:limit], start=1):
            print(f"\nRank #{index}")
            print(f"File:        {op['file']}")
            print(f"Title:       {op['title']}")
            print(f"Priority:    {op['priority']}")
            print(f"Difficulty:  {op['difficulty']} ({op.get('suggested_for', '')})")
            print("Reasons / Evidence:")
            for reason in op.get("reasons", []):
                print(f"  - {reason}")
            print(f"Action:      {op.get('suggested_action', '')}")

        print("\n==========================================")
        choice = input(
            "\nEnter a rank number to inspect file (or press Enter to return): "
        ).strip()
        if choice.isdigit() and 1 <= int(choice) <= len(filtered[:limit]):
            selected_file = filtered[int(choice) - 1]["file"]
            self.analyze_file(selected_file)

    def show_top_risk_files(self, limit=10):
        """Option 6: View top risk files based on ML predictions and complexity."""
        print("\n==========================================")
        print("             TOP RISK FILES")
        print("==========================================")

        if self.predictions is not None and not self.predictions.empty:
            ranked = self.predictions.head(limit)
            for rank, (_, row) in enumerate(ranked.iterrows(), start=1):
                prob = float(row.get("bug_probability", 0))
                risk = str(row.get("risk_level", "Unknown")).upper()
                print(f"\n#{rank}  {row['file']}")
                print(f"     Risk Level:     {risk}")
                print(f"     ML Probability: {prob:.0%}")
        elif not self.dataset.empty:
            ranked = self.dataset.sort_values(
                by=["complexity", "code_churn"], ascending=False
            ).head(limit)
            for rank, (_, row) in enumerate(ranked.iterrows(), start=1):
                print(f"\n#{rank}  {row['file']}")
                print(f"     Complexity: {row.get('complexity', 0)}")
                print(f"     Code Churn: {row.get('code_churn', 0)}")
        else:
            print("No risk data available.")

        print("\n==========================================")
        selected = input(
            "\nEnter a file path to inspect (or press Enter to return): "
        ).strip()
        if selected:
            self.analyze_file(selected)

    def analyze_file(self, file_path):
        """Option 7: Complete File Contributor Analysis."""
        if not file_path:
            file_path = input("\nEnter file path: ").strip()
            if not file_path:
                return

        try:
            explanation = self.risk_explainer.explain(
                file_path,
                self.dataset,
                self.predictions,
                self.metrics,
                self.repository_path
            )
        except Exception as error:
            print(f"\nCould not analyze file '{file_path}': {error}")
            return

        target = explanation["file"]
        risk_level = explanation.get("risk_level", "Unknown").upper()
        prob = explanation.get("bug_probability", 0.0)

        # Plan
        try:
            plan = self.plan_generator.create_plan(explanation, self.repository_path)
        except Exception:
            plan = {
                "contribution_type": "Refactoring or cleanup",
                "difficulty": "INTERMEDIATE",
                "steps": [
                    "Understand dependencies",
                    "Review recent history",
                    "Make isolated improvement",
                    "Run tests"
                ]
            }

        # Related files
        try:
            related_files = self.related_finder.find(target, self.dependency_graph)
        except Exception:
            related_files = []

        # Dependency impact
        try:
            impact = self.impact_analyzer.analyze(target, self.dependency_graph, risk_level=risk_level)
            impact_level = impact.get("impact_level", "LOW")
        except Exception:
            impact_level = "LOW"

        # Git history context
        try:
            history_context = self.history_context_analyzer.get_context(target, self.git_metrics)
            commit_count = history_context.get("commit_count", 0)
            contributors = history_context.get("contributors", 0)
            bug_fix_commits = history_context.get("bug_fix_commits", 0)
        except Exception:
            commit_count, contributors, bug_fix_commits = 0, 0, 0

        # GitHub Issue Intelligence
        issue_matches = []
        if self.issue_analyzer:
            try:
                issue_report = self.issue_analyzer.analyze_file(target)
                if issue_report.get("available"):
                    issue_matches = issue_report.get("matches", [])
            except Exception:
                issue_matches = []

        # Print standardized File Contributor Analysis
        print("\n------------------------------------------")
        print("FILE CONTRIBUTOR ANALYSIS")
        print("------------------------------------------")
        print(f"\nFile:\n{target}")
        print(f"\nML Risk:\n{risk_level}")
        print(f"\nML Probability:\n{prob:.0%}")

        print("\nWhy risky:")
        if explanation.get("reasons"):
            for reason in explanation["reasons"]:
                print(f"- {reason}")
        else:
            print("- No high-risk rule-based factors detected.")

        print("\nGit history:")
        print(f"{commit_count} commits")
        print(f"{contributors} contributors")
        print(f"{bug_fix_commits} bug-fix commits")

        print("\nRelated files:")
        if related_files:
            for related in related_files:
                print(f"{related['file']}")
        else:
            print("None resolved")

        print(f"\nDependency impact:\n{impact_level}")

        print("\nRelated GitHub Issues:")
        if issue_matches:
            for issue in issue_matches[:3]:
                print(f"#{issue['number']} {issue['title']}")
        else:
            print("No strongly related GitHub issues were found by CodePulse.")

        print(f"\nSuggested contribution:\n{plan.get('contribution_type', 'Refactoring')}")
        print(f"\nDifficulty:\n{plan.get('difficulty', 'INTERMEDIATE')}")

        print("\nContribution Plan:\n")
        for num, step in enumerate(plan.get("steps", []), start=1):
            print(f"{num}. {step}")

        print("------------------------------------------")

    def show_github_issues(self, file_path=None):
        """Option 8: View GitHub issues matching a specific file."""
        if not self.issue_analyzer:
            print("\nGitHub issue analyzer is not available (no GitHub repository URL).")
            return

        if not file_path:
            file_path = input("\nEnter file path to find related GitHub issues: ").strip()
            if not file_path:
                return

        try:
            issue_report = self.issue_analyzer.analyze_file(file_path)
            GitHubIssueAnalyzer.print_report(file_path, issue_report)
        except Exception as error:
            print(f"\nGitHub issue analysis failed: {error}")

    def run(self):
        """Run the main Contributor Workspace loop."""
        while True:
            health_score_str = self._get_overall_health_score()
            print("\n==========================================")
            print("             CODEPULSE AI")
            print("        CONTRIBUTOR WORKSPACE")
            print("==========================================")
            print(f"\nRepository:\n{self.repository_name}")
            print(f"\nHealth Score:\n{health_score_str} / 100")
            print("\nChoose an option:")
            print("\n1. Repository Health")
            print("2. Contribution Opportunities")
            print("3. Find Beginner Opportunities")
            print("4. Find Intermediate Opportunities")
            print("5. Find Advanced Opportunities")
            print("6. View Top Risk Files")
            print("7. Analyze a File")
            print("8. View GitHub Issues")
            print("9. Exit")

            choice = input("\nEnter choice: ").strip()

            try:
                if choice == "1":
                    self.show_repository_health()
                elif choice == "2":
                    self.show_opportunities()
                elif choice == "3":
                    self.show_opportunities(level="BEGINNER")
                elif choice == "4":
                    self.show_opportunities(level="INTERMEDIATE")
                elif choice == "5":
                    self.show_opportunities(level="ADVANCED")
                elif choice == "6":
                    self.show_top_risk_files()
                elif choice == "7":
                    self.analyze_file(None)
                elif choice == "8":
                    self.show_github_issues()
                elif choice == "9" or choice.lower() in {"exit", "quit", "q"}:
                    print("\nExiting CodePulse AI Contributor Workspace. Happy contributing!\n")
                    break
                else:
                    print("\nInvalid choice. Please enter a number between 1 and 9.")
            except Exception as error:
                print(f"\nAn error occurred while processing your request: {error}")
                print("Returning to main menu...")
