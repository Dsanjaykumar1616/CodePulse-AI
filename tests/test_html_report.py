import tempfile
import unittest
from pathlib import Path

import pandas as pd

from analysis.html_report import HtmlReportGenerator


class TestHtmlReportGenerator(unittest.TestCase):
    def setUp(self):
        self.dataset = pd.DataFrame([
            {"file": "src/app.py", "language": "Python", "bug_label": 0},
            {"file": "src/utils.py", "language": "Python", "bug_label": 1},
        ])
        self.repository = {
            "repository_name": "demo",
            "repository_url": "https://github.com/example/demo",
            "commits": 12,
            "contributors": 3,
            "languages": {"Python": 2},
        }

    def generate(self, **kwargs):
        directory = tempfile.TemporaryDirectory()
        output = Path(directory.name) / "codepulse_report.html"
        path = HtmlReportGenerator(output).generate(
            repository_info=self.repository,
            dataset=self.dataset,
            health_report={"overall_score": 81.5, "health_level": "Good"},
            **kwargs,
        )
        return directory, path

    def test_html_generation_and_repository_health(self):
        directory, path = self.generate()
        try:
            html = path.read_text(encoding="utf-8")
            self.assertTrue(html.startswith("<!doctype html>"))
            self.assertIn("Repository Overview", html)
            self.assertIn("demo", html)
            self.assertIn("81.5", html)
            self.assertIn("Repository Health", html)
        finally:
            directory.cleanup()

    def test_ml_unavailable_is_explicit(self):
        directory, path = self.generate(predictions=None, ml_results=None)
        try:
            html = path.read_text(encoding="utf-8")
            self.assertIn("ML Defect Risk", html)
            self.assertIn("ML training was skipped", html)
            self.assertNotIn("ROC-AUC: 0", html)
        finally:
            directory.cleanup()

    def test_all_analysis_sections_render(self):
        directory, path = self.generate(
            predictions=pd.DataFrame([
                {"file": "src/app.py", "bug_probability": 0.8, "risk_level": "Critical"}
            ]),
            ml_results={"Random Forest": {"f1": 0.8, "roc_auc": 0.9}},
            technical_debt_summary={
                "repository_debt_score": 64,
                "debt_level": "HIGH",
                "top_files": [{"file": "src/app.py", "technical_debt_score": 80, "technical_debt_level": "HIGH", "debt_reasons": ["High churn"]}],
            },
            duplicate_summary={"duplicate_groups": 1, "high_similarity_groups": 1, "top_pairs": [{"file_a": "a.py", "file_b": "b.py", "similarity_score": 95, "similarity_level": "HIGH"}]},
            architecture_report={"files_in_dependency_graph": 2, "dependency_relationships": 1, "unresolved_dependencies": 0, "centrality": [], "rendered_paths": [], "dot_path": "architecture.dot"},
            review_summary={"total_findings": 1, "critical_count": 1, "high_count": 0, "top_findings": [{"severity": "CRITICAL", "rule_id": "COMPLEXITY_HIGH", "file": "src/app.py", "recommendation": "Refactor"}]},
            opportunities=[{"file": "src/app.py", "opportunity_score": 8.5, "difficulty": "INTERMEDIATE", "impact": "HIGH", "reasons": ["High debt"]}],
        )
        try:
            html = path.read_text(encoding="utf-8")
            for section in ("Technical Debt", "Duplicate Code", "Architecture", "Rule-Based Code Review", "Contributor Opportunities"):
                self.assertIn(section, html)
            self.assertIn("COMPLEXITY_HIGH", html)
            self.assertIn("95.0%", html)
        finally:
            directory.cleanup()

    def test_missing_optional_data_has_no_fake_values(self):
        directory, path = self.generate(
            technical_debt_summary=None,
            duplicate_summary=None,
            architecture_report=None,
            review_summary=None,
            opportunities=None,
        )
        try:
            html = path.read_text(encoding="utf-8")
            self.assertGreaterEqual(html.count("Not available"), 4)
            self.assertNotIn("Technical Debt Score: 64", html)
            self.assertIn("No selected-file analysis was available", html)
        finally:
            directory.cleanup()

    def test_selected_file_section(self):
        directory, path = self.generate(
            selected={
                "explanation": {"file": "src/app.py", "risk_level": "HIGH", "reasons": ["High churn"]},
                "debt_level": "HIGH",
                "impact": {"impact_level": "MEDIUM"},
                "history": {"commit_count": 4},
                "plan": {"steps": ["Review related files"]},
            }
        )
        try:
            html = path.read_text(encoding="utf-8")
            self.assertIn("Selected File Intelligence", html)
            self.assertIn("Review related files", html)
        finally:
            directory.cleanup()

    def test_architecture_overview_section_uses_overview_image(self):
        directory, path = self.generate(
            architecture_report={
                "files_in_dependency_graph": 3,
                "dependency_relationships": 2,
                "unresolved_dependencies": 5,
                "centrality": [
                    {"file": "src/models.py", "incoming_dependencies": 2,
                     "outgoing_dependencies": 0, "total_connections": 2},
                ],
                "rendered_paths": ["/tmp/codepulse_architecture.png"],
                "overview_rendered_paths": ["/tmp/codepulse_architecture_overview.png"],
                "dot_path": "architecture.dot",
            },
        )
        try:
            html = path.read_text(encoding="utf-8")
            self.assertIn("Architecture Overview", html)
            self.assertIn("Most Connected Files", html)
            self.assertIn("Full Dependency Graph", html)
            self.assertIn("codepulse_architecture_overview.png", html)
            self.assertIn("codepulse_architecture.png", html)
            self.assertIn("src/models.py", html)
        finally:
            directory.cleanup()


if __name__ == "__main__":
    unittest.main()
