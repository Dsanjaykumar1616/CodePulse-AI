import io
import sys
import unittest
from unittest.mock import MagicMock

from analysis.dependency_impact import DependencyImpactAnalyzer
from analysis.dependency_analyzer import StaticDependencyAnalyzer


class TestDependencyImpactAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = DependencyImpactAnalyzer()

    def test_impact_levels(self):
        # 1. Low impact: 0-1 connections
        mock_graph_low = MagicMock()
        mock_graph_low.dependencies = {"utils.py": set()}
        mock_graph_low.used_by = {"utils.py": set()}

        result_low = self.analyzer.analyze("utils.py", mock_graph_low, risk_level="LOW")
        self.assertEqual(result_low["impact_level"], "LOW")

        # 2. Medium impact: 2-3 dependents / connections
        mock_graph_med = MagicMock()
        mock_graph_med.dependencies = {"helper.py": {"config.py"}}
        mock_graph_med.used_by = {"helper.py": {"app.py", "auth.py"}}

        result_med = self.analyzer.analyze("helper.py", mock_graph_med, risk_level="MEDIUM")
        self.assertEqual(result_med["impact_level"], "MEDIUM")
        self.assertEqual(len(result_med["used_by"]), 2)
        self.assertEqual(len(result_med["depends_on"]), 1)

        # 3. High impact: 4+ dependents or 6+ connections
        mock_graph_high = MagicMock()
        mock_graph_high.dependencies = {"PaymentService.java": {"PaymentRepository.java", "PaymentValidator.java"}}
        mock_graph_high.used_by = {
            "PaymentService.java": {"PaymentController.java", "CheckoutService.java", "InvoiceService.java", "RefundService.java"}
        }

        result_high = self.analyzer.analyze("PaymentService.java", mock_graph_high, risk_level="HIGH")
        self.assertEqual(result_high["impact_level"], "HIGH")
        self.assertIn("connected to multiple", result_high["reason"])

        # 4. Critical impact: 8+ dependents or 12+ connections
        mock_graph_crit = MagicMock()
        mock_graph_crit.dependencies = {"core.py": {f"dep_{i}.py" for i in range(5)}}
        mock_graph_crit.used_by = {"core.py": {f"user_{i}.py" for i in range(8)}}

        result_crit = self.analyzer.analyze("core.py", mock_graph_crit, risk_level="CRITICAL")
        self.assertEqual(result_crit["impact_level"], "CRITICAL")
        self.assertIn("central core module", result_crit["reason"])

    def test_print_report_formatting(self):
        mock_graph = MagicMock()
        mock_graph.dependencies = {"PaymentService.java": {"PaymentRepository.java", "PaymentValidator.java"}}
        mock_graph.used_by = {
            "PaymentService.java": {"PaymentController.java", "CheckoutService.java", "InvoiceService.java", "RefundService.java"}
        }
        impact = self.analyzer.analyze("PaymentService.java", mock_graph, risk_level="HIGH")

        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            DependencyImpactAnalyzer.print_report(impact, risk_level="HIGH")
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        self.assertIn("CONTRIBUTION IMPACT ANALYSIS", output)
        self.assertIn("Target:\nPaymentService.java", output)
        self.assertIn("Risk:\nHIGH", output)
        self.assertIn("Files it depends on:", output)
        self.assertIn("PaymentRepository.java", output)
        self.assertIn("Files depending on it:", output)
        self.assertIn("PaymentController.java", output)
        self.assertIn("Potential Impact:\nHIGH", output)
        self.assertIn("Before modifying:", output)
        self.assertIn("✓ Review dependent files", output)
        self.assertIn("✓ Run relevant tests", output)
        self.assertIn("✓ Keep the change isolated", output)
        self.assertIn("static analysis, not runtime prediction", output)

    def test_unreliable_dependency_fallback(self):
        result = self.analyzer.analyze("unknown.py", None)
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "Dependency impact could not be determined reliably.")

        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            DependencyImpactAnalyzer.print_report(result)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        self.assertIn("Dependency impact could not be determined reliably.", output)


if __name__ == "__main__":
    unittest.main()
