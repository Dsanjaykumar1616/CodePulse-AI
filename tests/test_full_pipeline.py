import os
import shutil
import tempfile
import unittest
from pathlib import Path
from git import Repo
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


class TestCodePulsePipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="codepulse_test_")
        cls.repo_dir = os.path.join(cls.test_dir, "test_repo")
        os.makedirs(cls.repo_dir, exist_ok=True)

        repo = Repo.init(cls.repo_dir)
        repo.config_writer().set_value("user", "name", "Test User").release()
        repo.config_writer().set_value("user", "email", "test@example.com").release()

        # Create multiple files across languages
        files_content = {
            "payment_service.py": (
                "class PaymentService:\n"
                "    def process(self, amount):\n"
                "        if amount > 0:\n"
                "            return True\n"
                "        return False\n"
            ),
            "user_service.py": (
                "from payment_service import PaymentService\n"
                "class UserService:\n"
                "    def pay(self):\n"
                "        return PaymentService().process(100)\n"
            ),
            "app.js": (
                "function main() {\n"
                "    console.log('App started');\n"
                "}\n"
            ),
            "index.html": (
                "<!DOCTYPE html>\n"
                "<html>\n"
                "<body>\n"
                "<h1>Hello</h1>\n"
                "</body>\n"
                "</html>\n"
            ),
            "styles.css": (
                "body { color: red; }\n"
            ),
        }

        for filename, content in files_content.items():
            file_path = os.path.join(cls.repo_dir, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

        repo.git.add(all=True)
        repo.index.commit("Initial commit with services")

        # Bug fix commit
        with open(os.path.join(cls.repo_dir, "payment_service.py"), "a", encoding="utf-8") as f:
            f.write("\n    def validate(self): pass\n")
        repo.git.add("payment_service.py")
        repo.index.commit("fix: fix bug in payment validation")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_phases_1_to_6_and_all_features(self):
        # 1. Repository Analyzer
        analyzer = RepositoryAnalyzer(self.repo_dir, clone_directory=os.path.dirname(self.repo_dir))
        analyzer.repo_path = self.repo_dir
        (total_files, languages, unsupported) = analyzer.detect_languages()
        git_info = analyzer.get_git_information()
        self.assertGreater(total_files, 0)
        self.assertIn("Python", languages)
        self.assertEqual(git_info["commits"], 2)

        # 2. Multi-Language Code Metrics
        metrics_extractor = CodeMetricsExtractor(self.repo_dir)
        metrics = metrics_extractor.analyze_repository()
        self.assertGreater(len(metrics), 0)

        # 3. Git History Intelligence
        git_analyzer = GitHistoryAnalyzer(self.repo_dir)
        git_metrics = git_analyzer.analyze_repository()
        self.assertGreater(len(git_metrics), 0)

        # 4. Feature Engineering
        feature_engineer = FeatureEngineer(self.repo_dir)
        dataset = feature_engineer.prepare_dataset(metrics, git_metrics)
        self.assertFalse(dataset.empty)
        self.assertIn("bug_label", dataset.columns)

        # 5. Defect Prediction (test classifier / helper logic)
        risk = DefectPredictionModel.classify_risk(0.85)
        self.assertEqual(risk, "Critical")
        risk_low = DefectPredictionModel.classify_risk(0.10)
        self.assertEqual(risk_low, "Low")

        # 6. Repository Health Score
        health_calc = RepositoryHealthScore()
        health_report = health_calc.calculate(dataset, None, metrics, self.repo_dir)
        self.assertIn("overall_score", health_report)
        self.assertIn("health_level", health_report)

        # 7. Contribution Opportunities
        opp_gen = ContributionOpportunityGenerator()
        opportunities = opp_gen.generate(dataset, None)
        self.assertIsInstance(opportunities, list)

        # 8. File Risk Explanation
        explainer = FileRiskExplainer()
        target_file = dataset.iloc[0]["file"]
        explanation = explainer.explain(target_file, dataset, None, metrics, self.repo_dir)
        self.assertEqual(explanation["file"], target_file)
        self.assertIn("metrics", explanation)

        # 9. Contribution Plan
        plan_gen = ContributionPlanGenerator()
        plan = plan_gen.create_plan(explanation, self.repo_dir)
        self.assertIn("contribution_type", plan)
        self.assertIn("steps", plan)

        # 10. Related Files & Dependency Graph
        dep_graph = StaticDependencyAnalyzer(self.repo_dir, dataset["file"].tolist()).build()
        related_finder = RelatedFilesFinder()
        related_files = related_finder.find(explanation["file"], dep_graph)
        self.assertIsInstance(related_files, list)

        # 11. Dependency Impact
        impact_analyzer = DependencyImpactAnalyzer()
        impact = impact_analyzer.analyze(explanation["file"], dep_graph)
        self.assertIn("impact_level", impact)

        # 12. Git History Context & Contributor View
        history_context = GitHistoryContext().get_context(explanation["file"], git_metrics)
        self.assertEqual(history_context["file"], explanation["file"])

        # Contributor View
        ContributorView.print_report(explanation, related_files, impact, history_context, plan)

        # 13. GitHub Issue Intelligence
        issue_analyzer = GitHubIssueAnalyzer("https://github.com/pallets/flask")
        mock_issues = [
            {
                "number": 1,
                "title": "Payment service throws exception",
                "body": "Issue in payment_service.py",
                "state": "open",
                "labels": [{"name": "bug"}],
                "html_url": "https://github.com/pallets/flask/issues/1",
                "user": {"login": "user1"},
            }
        ]
        matches = issue_analyzer.match_issues("payment_service.py", mock_issues)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["number"], 1)
        self.assertEqual(matches[0]["relevance"], "HIGH")


if __name__ == "__main__":
    unittest.main()
