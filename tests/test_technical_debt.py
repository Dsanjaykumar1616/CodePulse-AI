import unittest
import os
import tempfile
from pathlib import Path

import pandas as pd

from analysis.technical_debt import TechnicalDebtAnalyzer
from analysis.contribution_opportunities import ContributionOpportunityGenerator


class TestTechnicalDebtAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = TechnicalDebtAnalyzer()
        self.dataset = pd.DataFrame([
            {"file": "low.py", "complexity": 1, "loc": 10, "code_churn": 1, "comment_ratio": 0.5, "bug_fix_commits": 0, "nesting_depth": 0},
            {"file": "high.py", "complexity": 100, "loc": 1000, "code_churn": 100, "comment_ratio": 0.1, "bug_fix_commits": 10, "nesting_depth": 5},
            {"file": "medium.py", "complexity": 40, "loc": 300, "code_churn": 30, "comment_ratio": 0.3, "bug_fix_commits": 2, "nesting_depth": 2},
        ])

    def test_normalization_is_repository_relative(self):
        values = self.analyzer.normalize(pd.Series([10, 20, 30]))
        self.assertEqual(values.iloc[0], 0.0)
        self.assertEqual(values.iloc[2], 1.0)

    def test_score_and_classification_use_available_signals(self):
        predictions = pd.DataFrame([
            {"file": "low.py", "bug_probability": 0.0},
            {"file": "high.py", "bug_probability": 1.0},
            {"file": "medium.py", "bug_probability": 0.4},
        ])
        result = self.analyzer.analyze(self.dataset, predictions)
        self.assertGreater(result.iloc[0]["technical_debt_score"], 90)
        self.assertEqual(result.iloc[0]["technical_debt_level"], "CRITICAL")
        self.assertEqual(result.iloc[0]["file"], "high.py")
        self.assertFalse(result["duplication_available"].any())

    def test_missing_ml_and_duplication_are_explicit(self):
        result = self.analyzer.analyze(self.dataset)
        self.assertTrue(result["ml_component"].isna().all())
        self.assertTrue(result["duplication_component"].isna().all())
        self.assertFalse(result["duplication_available"].any())
        self.assertTrue(result["technical_debt_score"].notna().all())

    def test_missing_optional_metric_columns_do_not_crash(self):
        dataset = pd.DataFrame([{"file": "only.py"}])
        result = self.analyzer.analyze(dataset)
        self.assertEqual(result.iloc[0]["technical_debt_score"], 0.0)
        self.assertEqual(result.iloc[0]["technical_debt_level"], "LOW")

    def test_maintainability_is_converted_to_debt(self):
        metrics = [
            {"file": "low.py", "maintainability": 90},
            {"file": "high.py", "maintainability": 10},
            {"file": "medium.py", "maintainability": 50},
        ]
        result = self.analyzer.analyze(self.dataset, code_metrics=metrics)
        high = result[result["file"] == "high.py"].iloc[0]
        self.assertEqual(high["maintainability_component"], 100.0)

    def test_repository_summary_and_top_ranking(self):
        result = self.analyzer.analyze(self.dataset)
        summary = self.analyzer.summarize(result, top_n=2)
        self.assertEqual(len(summary["top_files"]), 2)
        self.assertEqual(summary["top_files"][0]["file"], "high.py")
        self.assertEqual(
            summary["low_count"] + summary["medium_count"]
            + summary["high_count"] + summary["critical_count"],
            3,
        )
        self.assertGreaterEqual(summary["repository_debt_score"], 0)
        self.assertLessEqual(summary["repository_debt_score"], 100)

    def test_empty_dataset(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            self.analyzer.analyze(pd.DataFrame())

    def test_save_uses_project_dataset_artifact(self):
        result = self.analyzer.analyze(self.dataset)
        previous = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                os.chdir(temporary)
                output = self.analyzer.save(result, "data/datasets/test_technical_debt.csv")
                os.chdir(previous)
        finally:
            os.chdir(previous)
        self.assertEqual(output, Path(__file__).parents[1] / "data/datasets/test_technical_debt.csv")
        self.assertTrue(output.exists())
        output.unlink()

    def test_explanations_are_evidence_based(self):
        predictions = pd.DataFrame([
            {"file": "high.py", "bug_probability": 1.0},
        ])
        result = self.analyzer.analyze(self.dataset, predictions)
        high = result[result["file"] == "high.py"].iloc[0]
        self.assertIn("Elevated ML historical defect risk", high["debt_reasons"])
        self.assertIn("High historical code churn", high["debt_reasons"])

    def test_debt_evidence_enriches_existing_opportunities(self):
        debt = self.analyzer.analyze(self.dataset)
        opportunities = ContributionOpportunityGenerator().generate(
            self.dataset,
            technical_debt=debt,
        )
        high = next(item for item in opportunities if item["file"] == "high.py")
        self.assertTrue(any("Technical debt score" in reason for reason in high["reasons"]))


if __name__ == "__main__":
    unittest.main()
