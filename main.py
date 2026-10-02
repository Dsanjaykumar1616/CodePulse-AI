from analyzer.repository_analyzer import (
    RepositoryAnalyzer
)
from ml.feature_engineering import (
    FeatureEngineer
)
from ml.defect_prediction import (
    DefectPredictionModel
)
from git_analysis.git_history_analyzer import (
    GitHistoryAnalyzer
)
from metrics.code_metrics import (
    CodeMetricsExtractor
)
from analysis.health_score import (
    RepositoryHealthScore
)
from analysis.contribution_opportunities import (
    ContributionOpportunityGenerator
)
from analysis.risk_explanation import (
    FileRiskExplainer
)
from analysis.contribution_plan import (
    ContributionPlanGenerator
)
from analysis.dependency_analyzer import (
    StaticDependencyAnalyzer
)
from analysis.related_files import (
    RelatedFilesFinder
)
from analysis.dependency_impact import (
    DependencyImpactAnalyzer
)
from analysis.git_history_context import (
    GitHistoryContext
)
from analysis.contributor_view import (
    ContributorView
)
from analysis.contributor_workspace import (
    ContributorWorkspace
)
from github.issue_analyzer import (
    GitHubIssueAnalyzer
)
from analysis.technical_debt import TechnicalDebtAnalyzer
from analysis.duplicate_code import DuplicateCodeDetector
from analysis.architecture_diagram import ArchitectureDiagramGenerator
from analysis.code_review import RuleBasedCodeReviewer
from codepulse_runtime import (
    FEATURES_PATH,
    PREDICTIONS_PATH,
    dataset_is_valid_for_run,
    invalidate_analysis_artifacts,
    predictions_are_valid_for_run,
    write_run_metadata,
)


def main():

    print()
    print(
        "=========================================="
    )
    print(
        "              CODEPULSE AI"
    )
    print(
        "   Intelligent Codebase Health Analyzer"
    )
    print(
        "=========================================="
    )

    repo_url = input(
        "\nEnter GitHub repository URL: "
    ).strip()

    if not repo_url:

        print(
            "Repository URL cannot be empty."
        )

        return

    try:

        # =====================================
        # PHASE 2
        # =====================================

        analyzer = RepositoryAnalyzer(
            repo_url
        )

        repository_info = (
            analyzer.analyze()
        )

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
            f"Repository : "
            f"{repository_info['repository_name']}"
        )

        print(
            f"Total Files: "
            f"{repository_info['total_files']}"
        )

        print(
            "\nLanguages Detected:"
        )

        for language, count in (
            repository_info["languages"].items()
        ):

            print(
                f"{language:<12}: "
                f"{count} files"
            )

        print(
            f"\nCommits      : "
            f"{repository_info['commits']}"
        )

        print(
            f"Contributors : "
            f"{repository_info['contributors']}"
        )

        # =====================================
        # PHASE 3
        # =====================================

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

        metrics_extractor = (
            CodeMetricsExtractor(
                analyzer.repo_path
            )
        )

        metrics = (
            metrics_extractor
            .analyze_repository()
        )

        # =====================================
        # PHASE 4
        # Git History Intelligence
        # =====================================

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
            source_files=[item["file"] for item in metrics],
        )

        git_metrics = (
            git_analyzer.analyze_repository()
        )

        # =====================================
        # PHASE 5
        # Feature Engineering
        # =====================================

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

        dataset = feature_engineer.prepare_dataset(
            metrics,
            git_metrics
        )

        dataset_path = FEATURES_PATH
        invalidate_analysis_artifacts("starting a new repository analysis")

        if dataset.empty:

            print(
                "\nFeature dataset could not be created; ML will be skipped."
            )

        else:

            print(
                f"\nFeature dataset created."
            )

            print(
                f"Total samples: "
                f"{len(dataset)}"
            )

            print(
                f"Total features: "
                f"{len(dataset.columns)}"
            )

            print(
                "\nDataset preview:"
            )

            print(
                dataset.head(10).to_string(
                    index=False
                )
            )

            feature_engineer.save_dataset(
                dataset,
                dataset_path
            )
            write_run_metadata(repo_url, dataset_path, PREDICTIONS_PATH)

        # =====================================
        # PHASE 6
        # ML DEFECT PREDICTION
        # =====================================

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

        predictions = None

        try:
            if not dataset_is_valid_for_run(dataset, repo_url):
                raise ValueError(
                    "Current analysis has no valid repository-owned feature dataset."
                )
            ml_model = DefectPredictionModel(dataset_path)
            ml_results = ml_model.run()
            predictions = ml_model.predictions
            if not predictions_are_valid_for_run(predictions, dataset, repo_url):
                invalidate_analysis_artifacts("ML predictions did not match the current repository")
                predictions = None

        except ValueError as error:

            print(
                "\nPhase 6 is not run for this repository."
            )

            print(
                f"Reason: {error}"
            )

        if dataset.empty or not dataset_is_valid_for_run(dataset, repo_url):
            print(
                "\nRepository-dependent health, contribution, and file-risk "
                "reports are skipped because the current feature dataset is invalid."
            )
            return

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

        for metric in git_metrics:

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
                f"Bug-Fix Commits: "
                f"{metric['bug_fix_commits']}"
            )

            print(
                f"File Age (days): "
                f"{metric['file_age_days']}"
            )

            print(
                f"Last Modified: "
                f"{metric['last_modified']}"
            )

        # =====================================
        # SUMMARY
        # =====================================

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

        for metric in metrics:

            print(
                "\n------------------------------------------"
            )

            print(
                f"File: {metric['file']}"
            )

            print(
                f"Language: "
                f"{metric['language']}"
            )

            print(
                f"LOC: "
                f"{metric['loc']}"
            )

            print(
                f"Complexity: "
                f"{metric['complexity']}"
            )

            print(
                f"Maintainability: "
                f"{metric['maintainability']}"
            )

            print(
                f"Functions: "
                f"{metric['functions']}"
            )

            print(
                f"Classes: "
                f"{metric['classes']}"
            )

            print(
                f"Nesting Depth: "
                f"{metric['nesting_depth']}"
            )

            print(
                f"Comment Ratio: "
                f"{metric['comment_ratio']}"
            )

            if metric["elements"] > 0:

                print(
                    f"HTML Elements: "
                    f"{metric['elements']}"
                )

            if metric["selectors"] > 0:

                print(
                    f"CSS Selectors: "
                    f"{metric['selectors']}"
                )

            if metric["declarations"] > 0:

                print(
                    f"CSS Declarations: "
                    f"{metric['declarations']}"
                )

            if metric["important_count"] > 0:

                print(
                    f"!important Usage: "
                    f"{metric['important_count']}"
                )

        print()
        print(
            "=========================================="
        )

        print(
            f"Successfully analyzed "
            f"{len(metrics)} source files."
        )

        print(
            "=========================================="
        )

        # =====================================
        # REPOSITORY HEALTH SCORE
        # =====================================

        health_calculator = RepositoryHealthScore()
        health_report = health_calculator.calculate(
            dataset,
            predictions,
            metrics,
            analyzer.repo_path
        )
        health_calculator.print_report(
            repository_info["repository_name"],
            health_report
        )

        duplicate_detector = DuplicateCodeDetector(analyzer.repo_path)
        duplicate_pairs = duplicate_detector.analyze()
        duplicate_summary = duplicate_detector.summarize(duplicate_pairs)
        duplicate_signal = duplicate_detector.per_file_signal(duplicate_pairs)
        duplicate_detector.save(duplicate_pairs)
        duplicate_detector.print_report(duplicate_summary)

        debt_analyzer = TechnicalDebtAnalyzer()
        debt_data = debt_analyzer.analyze(
            dataset,
            predictions,
            metrics,
            duplication=duplicate_signal,
            repository_path=analyzer.repo_path,
        )
        debt_summary = debt_analyzer.summarize(debt_data)
        debt_analyzer.save(debt_data)
        debt_analyzer.print_report(debt_summary)

        dependency_graph = StaticDependencyAnalyzer(
            analyzer.repo_path,
            dataset["file"].tolist(),
        ).build()
        architecture_report = ArchitectureDiagramGenerator(
            dependency_graph
        ).generate()
        ArchitectureDiagramGenerator.print_report(architecture_report)

        issue_matches = {}
        issue_analyzer = GitHubIssueAnalyzer(repository_info["repository_url"])
        issue_result = issue_analyzer.fetch_issues()
        if issue_result.get("available"):
            issue_matches = {
                file_path: issue_analyzer.match_issues(
                    file_path, issue_result.get("issues", [])
                )
                for file_path in dataset["file"].tolist()
            }

        reviewer = RuleBasedCodeReviewer()
        review_findings = reviewer.review(
            dataset,
            code_metrics=metrics,
            duplicate_pairs=duplicate_pairs,
            repository_path=analyzer.repo_path,
        )
        review_summary = reviewer.summarize(
            review_findings,

            files_reviewed=len(dataset),
        )
        reviewer.save(review_findings)
        reviewer.print_report(review_summary)

        # =====================================
        # CONTRIBUTION OPPORTUNITIES
        # =====================================

        opportunity_generator = ContributionOpportunityGenerator()
        opportunities = opportunity_generator.generate(
            dataset,
            predictions,
            technical_debt=debt_data,
            dependency_graph=dependency_graph,
            issue_matches=issue_matches,
            review_findings=review_findings,
        )
        opportunity_generator.interactive_filter(opportunities)

        # =====================================
        # FILE RISK EXPLANATION + CONTRIBUTION PLAN
        # =====================================

        selected_file = input(
            "\nEnter a file path for risk analysis and a contribution plan "
            "(or press Enter to finish): "
        ).strip()

        if selected_file:
            risk_explainer = FileRiskExplainer()
            explanation = risk_explainer.explain(
                selected_file,
                dataset,
                predictions,
                metrics,
                analyzer.repo_path
            )
            risk_explainer.print_report(explanation)

            related_finder = RelatedFilesFinder()
            related_files = related_finder.find(
                explanation["file"],
                dependency_graph
            )
            related_finder.print_report(
                explanation["file"],
                related_files
            )

            impact_analyzer = DependencyImpactAnalyzer()
            impact = impact_analyzer.analyze(
                explanation["file"],
                dependency_graph,
                risk_level=explanation.get("risk_level")
            )
            impact_analyzer.print_report(
                impact,
                risk_level=explanation.get("risk_level")
            )

            history_context = GitHistoryContext().get_context(
                explanation["file"],
                git_metrics
            )
            GitHistoryContext.print_report(history_context)

            issue_report = GitHubIssueAnalyzer(
                repository_info["repository_url"]
            ).analyze_file(explanation["file"])
            GitHubIssueAnalyzer.print_report(
                explanation["file"],
                issue_report,
                risk_level=explanation.get("risk_level")
            )

            open_issue = next(
                (
                    issue for issue in issue_report.get("matches", [])
                    if str(issue.get("state", "UNKNOWN")).upper() == "OPEN"
                ),
                None,
            )
            plan = ContributionPlanGenerator().create_plan(
                explanation,
                analyzer.repo_path,
                context={
                    "related_files": related_files,
                    "impact": impact,
                    "history": history_context,
                    "open_issue": open_issue,
                },
            )
            ContributionPlanGenerator.print_report(plan)

            ContributorView.print_report(
                explanation,
                related_files,
                impact,
                history_context,
                plan
            )


    except Exception as error:

        print()
        print(
            "Analysis failed."
        )

        print(
            f"Error: {error}"
        )


if __name__ == "__main__":

    main()
