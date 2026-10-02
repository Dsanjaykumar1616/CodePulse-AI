import unittest
import pandas as pd

from analysis.contribution_opportunities import ContributionOpportunityGenerator


class TestOpportunityFiltering(unittest.TestCase):

    def setUp(self):
        self.sample_dataset = pd.DataFrame([
            {
                "file": "src/core/payment_engine.py",
                "complexity": 120,
                "code_churn": 4500,
                "loc": 650,
                "comment_ratio": 0.05,
                "bug_fix_commits": 25,
                "nesting_depth": 5,
            },
            {
                "file": "src/services/auth_service.py",
                "complexity": 25,
                "code_churn": 300,
                "loc": 120,
                "comment_ratio": 0.10,
                "bug_fix_commits": 4,
                "nesting_depth": 3,
            },
            {
                "file": "src/utils/string_helpers.py",
                "complexity": 2,
                "code_churn": 20,
                "loc": 35,
                "comment_ratio": 0.02,
                "bug_fix_commits": 0,
                "nesting_depth": 1,
            },
            {
                "file": "src/models/user_dto.py",
                "complexity": 1,
                "code_churn": 10,
                "loc": 25,
                "comment_ratio": 0.20,
                "bug_fix_commits": 0,
                "nesting_depth": 1,
            },
        ])

        self.sample_predictions = pd.DataFrame([
            {
                "file": "src/core/payment_engine.py",
                "bug_probability": 0.92,
                "risk_level": "Critical"
            },
            {
                "file": "src/services/auth_service.py",
                "bug_probability": 0.55,
                "risk_level": "High"
            },
            {
                "file": "src/utils/string_helpers.py",
                "bug_probability": 0.05,
                "risk_level": "Low"
            },
            {
                "file": "src/models/user_dto.py",
                "bug_probability": 0.02,
                "risk_level": "Low"
            },
        ])

        self.generator = ContributionOpportunityGenerator()

    def test_difficulty_classification(self):
        opportunities = self.generator.generate(self.sample_dataset, self.sample_predictions)
        self.assertEqual(len(opportunities), 4)

        op_map = {op["file"]: op for op in opportunities}

        # Payment engine -> Advanced
        self.assertEqual(op_map["src/core/payment_engine.py"]["difficulty"], "ADVANCED")
        self.assertEqual(op_map["src/core/payment_engine.py"]["priority"], "CRITICAL")
        self.assertEqual(op_map["src/core/payment_engine.py"]["suggested_for"], "Suggested for Advanced")

        # Auth service -> Intermediate
        self.assertEqual(op_map["src/services/auth_service.py"]["difficulty"], "INTERMEDIATE")
        self.assertEqual(op_map["src/services/auth_service.py"]["suggested_for"], "Suggested for Intermediate")

        # String helpers & user dto -> Beginner
        self.assertEqual(op_map["src/utils/string_helpers.py"]["difficulty"], "BEGINNER")
        self.assertEqual(op_map["src/utils/string_helpers.py"]["suggested_for"], "Suggested for Beginner")
        self.assertEqual(op_map["src/models/user_dto.py"]["difficulty"], "BEGINNER")

    def test_filtering_by_level(self):
        opportunities = self.generator.generate(self.sample_dataset, self.sample_predictions)

        # Filter Beginner
        beginner_ops = ContributionOpportunityGenerator.filter_by_level(opportunities, "BEGINNER")
        self.assertTrue(all(op["difficulty"] == "BEGINNER" for op in beginner_ops))
        self.assertEqual(len(beginner_ops), 2)

        # Filter Intermediate
        intermediate_ops = ContributionOpportunityGenerator.filter_by_level(opportunities, "INTERMEDIATE")
        self.assertTrue(all(op["difficulty"] == "INTERMEDIATE" for op in intermediate_ops))
        self.assertEqual(len(intermediate_ops), 1)

        # Filter Advanced
        advanced_ops = ContributionOpportunityGenerator.filter_by_level(opportunities, "ADVANCED")
        self.assertTrue(all(op["difficulty"] == "ADVANCED" for op in advanced_ops))
        self.assertEqual(len(advanced_ops), 1)

        # Filter All
        all_ops = ContributionOpportunityGenerator.filter_by_level(opportunities, "ALL")
        self.assertEqual(len(all_ops), 4)

    def test_ranking_and_scoring(self):
        opportunities = self.generator.generate(self.sample_dataset, self.sample_predictions)

        # Highest priority/impact should be first
        self.assertEqual(opportunities[0]["file"], "src/core/payment_engine.py")
        self.assertEqual(opportunities[0]["priority"], "CRITICAL")

        # Check that score and impact_score exist
        for op in opportunities:
            self.assertIn("score", op)
            self.assertIn("impact_score", op)
            self.assertIn("reasons", op)
            self.assertGreater(len(op["reasons"]), 0)

    def test_print_grouped_report(self):
        import io
        import sys

        opportunities = self.generator.generate(self.sample_dataset, self.sample_predictions)

        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            ContributionOpportunityGenerator.print_grouped_report(opportunities, level_filter="BEGINNER")
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        self.assertIn("SUGGESTED CONTRIBUTION OPPORTUNITIES", output)
        self.assertIn("BEGINNER OPPORTUNITIES", output)
        self.assertIn("Suggested for Beginner", output)
        self.assertNotIn("ADVANCED OPPORTUNITIES", output)


if __name__ == "__main__":
    unittest.main()
