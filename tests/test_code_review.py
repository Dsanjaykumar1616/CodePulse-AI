import shutil
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from analysis.code_review import RuleBasedCodeReviewer


class TestRuleBasedCodeReviewer(unittest.TestCase):
    def setUp(self):
        self.reviewer = RuleBasedCodeReviewer()
        self.dataset = pd.DataFrame([
            {
                "file": "small.py", "complexity": 1, "loc": 20,
                "nesting_depth": 1, "comment_ratio": 0.6,
                "code_churn": 1, "bug_fix_commits": 0,
            },
            {
                "file": "risky.py", "complexity": 40, "loc": 900,
                "nesting_depth": 8, "comment_ratio": 0.01,
                "code_churn": 500, "bug_fix_commits": 20,
            },
            {
                "file": "normal.py", "complexity": 4, "loc": 100,
                "nesting_depth": 2, "comment_ratio": 0.3,
                "code_churn": 10, "bug_fix_commits": 1,
            },
        ])

    def test_metric_rules_generate_evidence_based_findings(self):
        metrics = [
            {"file": "small.py", "maintainability": 80},
            {"file": "risky.py", "maintainability": 10},
            {"file": "normal.py", "maintainability": 60},
        ]
        findings = self.reviewer.review(self.dataset, code_metrics=metrics)
        risky_rules = set(findings[findings["file"] == "risky.py"]["rule_id"])
        self.assertIn("COMPLEXITY_HIGH", risky_rules)
        self.assertIn("LARGE_FILE", risky_rules)
        self.assertIn("NESTING_DEEP", risky_rules)
        self.assertIn("MAINTAINABILITY_LOW", risky_rules)
        self.assertIn("DOCUMENTATION_LOW", risky_rules)
        self.assertIn("CHURN_HIGH", risky_rules)
        self.assertIn("BUG_FIX_ACTIVITY_HIGH", risky_rules)
        self.assertTrue(findings["evidence"].str.contains("=").all())

    def test_duplicate_finding_and_severity(self):
        pairs = pd.DataFrame([{
            "file_a": "small.py", "file_b": "normal.py",
            "similarity_score": 95.0,
        }])
        findings = self.reviewer.review(self.dataset, duplicate_pairs=pairs)
        duplicate = findings[findings["rule_id"] == "DUPLICATE_CODE"]
        self.assertEqual(len(duplicate), 2)
        self.assertTrue((duplicate["severity"] == "CRITICAL").all())

    def test_missing_metrics_are_skipped(self):
        dataset = pd.DataFrame([{"file": "only.py"}])
        findings = self.reviewer.review(dataset)
        self.assertTrue(findings.empty)
        summary = self.reviewer.summarize(findings)
        self.assertEqual(summary["total_findings"], 0)

    def test_no_findings_and_empty_dataset(self):
        findings = self.reviewer.review(pd.DataFrame([{
            "file": "clean.py", "complexity": 1, "loc": 10,
            "nesting_depth": 1, "comment_ratio": 0.8,
            "code_churn": 0, "bug_fix_commits": 0,
        }]))
        self.assertTrue(findings.empty)
        self.assertTrue(self.reviewer.review(pd.DataFrame()).empty)

    def test_summary_counts_and_output(self):
        findings = self.reviewer.review(self.dataset)
        summary = self.reviewer.summarize(findings, top_n=2)
        self.assertEqual(summary["total_findings"], len(findings))
        self.assertLessEqual(len(summary["top_findings"]), 2)
        with tempfile.TemporaryDirectory() as temporary:
            output = self.reviewer.save(findings, Path(temporary) / "review.csv")
            self.assertTrue(output.exists())
            self.assertIn("rule_id", output.read_text(encoding="utf-8").splitlines()[0])

    def test_empty_repository_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = self.reviewer.save(
                self.reviewer.review(pd.DataFrame()),
                Path(temporary) / "empty-review.csv",
            )
            self.assertTrue(output.exists())
            self.assertEqual(len(output.read_text(encoding="utf-8").splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
