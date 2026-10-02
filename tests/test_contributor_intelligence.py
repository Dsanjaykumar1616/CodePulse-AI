import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from analysis.contribution_opportunities import ContributionOpportunityGenerator
from analysis.contribution_plan import ContributionPlanGenerator


class Graph:
    def __init__(self, dependencies, used_by):
        self.dependencies = dependencies
        self.used_by = used_by


class TestContributorIntelligence(unittest.TestCase):
    def setUp(self):
        self.dataset = pd.DataFrame([
            {
                "file": "core.py", "complexity": 25, "loc": 300,
                "comment_ratio": 0.1, "code_churn": 80,
                "bug_fix_commits": 8, "nesting_depth": 4,
            },
            {
                "file": "small.py", "complexity": 2, "loc": 20,
                "comment_ratio": 0.8, "code_churn": 1,
                "bug_fix_commits": 0, "nesting_depth": 1,
            },
            {
                "file": "risky_isolated.py", "complexity": 30, "loc": 350,
                "comment_ratio": 0.05, "code_churn": 70,
                "bug_fix_commits": 7, "nesting_depth": 5,
            },
        ])

    def test_high_opportunity_is_not_only_high_risk(self):
        predictions = pd.DataFrame([
            {"file": "core.py", "bug_probability": 0.55, "risk_level": "High"},
            {"file": "small.py", "bug_probability": 0.95, "risk_level": "Critical"},
            {"file": "risky_isolated.py", "bug_probability": 0.90, "risk_level": "Critical"},
        ])
        debt = pd.DataFrame([
            {"file": "core.py", "technical_debt_score": 85, "technical_debt_level": "HIGH"},
            {"file": "small.py", "technical_debt_score": 5, "technical_debt_level": "LOW"},
            {"file": "risky_isolated.py", "technical_debt_score": 70, "technical_debt_level": "MEDIUM"},
        ])
        graph = Graph(
            {"core.py": {"base.py"}, "small.py": set(), "risky_isolated.py": set()},
            {"core.py": {"app.py", "service.py", "api.py"}, "small.py": set(), "risky_isolated.py": set()},
        )
        opportunities = ContributionOpportunityGenerator().generate(
            self.dataset, predictions, technical_debt=debt, dependency_graph=graph
        )
        self.assertEqual(opportunities[0]["file"], "core.py")
        self.assertGreater(opportunities[0]["opportunity_score"], opportunities[1]["opportunity_score"])
        self.assertIn("Central dependency", " ".join(opportunities[0]["reasons"]))

    def test_open_issue_adds_signal_closed_issue_does_not(self):
        issue_matches = {
            "core.py": [{"state": "OPEN", "relevance": "HIGH", "number": 1}],
            "small.py": [{"state": "CLOSED", "relevance": "HIGH", "number": 2}],
        }
        opportunities = ContributionOpportunityGenerator().generate(
            self.dataset, issue_matches=issue_matches
        )
        core = next(item for item in opportunities if item["file"] == "core.py")
        small = next(item for item in opportunities if item["file"] == "small.py")
        self.assertEqual(core["open_issue_count"], 1)
        self.assertEqual(core["related_issue_status"], "OPEN")
        self.assertEqual(small["open_issue_count"], 0)
        self.assertEqual(small["related_issue_status"], "CLOSED")
        self.assertIn("CLOSED issue", " ".join(small["reasons"]))

    def test_missing_optional_evidence_is_explicit(self):
        opportunities = ContributionOpportunityGenerator().generate(self.dataset)
        for opportunity in opportunities:
            self.assertEqual(opportunity["related_issue_status"], "NONE/UNAVAILABLE")
            self.assertIsNone(opportunity["centrality"])

    def test_difficulty_uses_dependency_centrality(self):
        graph = Graph(
            {"core.py": set(), "small.py": set(), "risky_isolated.py": set()},
            {"core.py": {"a.py", "b.py", "c.py", "d.py", "e.py", "f.py"}, "small.py": set(), "risky_isolated.py": set()},
        )
        opportunities = ContributionOpportunityGenerator().generate(
            self.dataset, dependency_graph=graph
        )
        core = next(item for item in opportunities if item["file"] == "core.py")
        self.assertEqual(core["difficulty"], "ADVANCED")
        self.assertEqual(core["impact"], "HIGH")

    def test_plan_uses_actual_context_without_claiming_changes(self):
        explanation = {
            "file": "core.py",
            "metrics": {"bug_fix_commits": 2},
            "complexity_high": True,
            "churn_high": True,
            "bug_probability": 0.6,
        }
        with TemporaryDirectory() as directory:
            Path(directory, "tests").mkdir()
            plan = ContributionPlanGenerator().create_plan(
                explanation,
                directory,
                context={
                    "related_files": [{"file": "app.py"}],
                    "impact": {"impact_level": "HIGH"},
                    "history": {"commit_count": 4},
                    "open_issue": {"number": 10, "state": "OPEN"},
                },
            )
        joined = " ".join(plan["steps"])
        self.assertIn("related and dependent files", joined)
        self.assertIn("Git history", joined)
        self.assertIn("OPEN GitHub issue", joined)
        self.assertIn("dependency impact", joined)
        self.assertNotIn("implemented", joined.lower())


if __name__ == "__main__":
    unittest.main()
