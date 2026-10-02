import unittest
from unittest.mock import patch, MagicMock
import requests

from github.issue_analyzer import GitHubIssueAnalyzer


class TestGitHubIssueAnalyzer(unittest.TestCase):

    def test_parse_repository_url(self):
        cases = [
            ("https://github.com/pallets/flask", ("pallets", "flask")),
            ("https://github.com/pallets/flask.git", ("pallets", "flask")),
            ("https://github.com/pallets/flask/", ("pallets", "flask")),
            ("http://github.com/psf/requests", ("psf", "requests")),
            ("git@github.com:torvalds/linux.git", ("torvalds", "linux")),
            ("github.com/django/django", ("django", "django")),
            ("pallets/flask", ("pallets", "flask")),
            ("https://gitlab.com/user/repo", (None, None)),
            ("invalid-url", (None, None)),
            ("", (None, None)),
            (None, (None, None)),
        ]
        for url, expected in cases:
            with self.subTest(url=url):
                self.assertEqual(GitHubIssueAnalyzer.parse_repository_url(url), expected)

    def test_keyword_extraction(self):
        keywords = GitHubIssueAnalyzer._keywords("src/services/PaymentProcessorService.java")
        self.assertIn("payment", keywords)
        self.assertIn("processor", keywords)
        # Ignored words
        self.assertNotIn("src", keywords)
        self.assertNotIn("service", keywords)
        self.assertNotIn("services", keywords)

    def test_pull_request_filtering(self):
        raw_issues = [
            {
                "number": 101,
                "title": "PaymentProcessor fails on negative amount",
                "body": "Fix in PaymentProcessor.java",
                "state": "open",
                "labels": [{"name": "bug"}],
                "user": {"login": "alice"},
                "html_url": "https://github.com/org/repo/issues/101",
            },
            {
                "number": 102,
                "title": "PR: Update PaymentProcessor",
                "body": "Contains PR code",
                "pull_request": {"url": "https://api.github.com/repos/org/repo/pulls/102"},
                "state": "open",
                "labels": [],
                "user": {"login": "bob"},
            },
        ]

        analyzer = GitHubIssueAnalyzer("https://github.com/org/repo")
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.json.return_value = raw_issues
            mock_get.return_value = mock_response

            result = analyzer.fetch_issues()
            self.assertTrue(result["available"])
            self.assertEqual(len(result["issues"]), 1)
            self.assertEqual(result["issues"][0]["number"], 101)

    def test_match_issues_high_relevance(self):
        issues = [
            {
                "number": 142,
                "title": "PaymentService validation fails for invalid cards",
                "body": "NullPointerException in PaymentService.java line 42",
                "state": "open",
                "labels": [{"name": "bug"}, {"name": "payment"}],
                "html_url": "https://github.com/example/repo/issues/142",
                "user": {"login": "contributor1"},
            },
            {
                "number": 999,
                "title": "Documentation update for README",
                "body": "Fix typo in install guide",
                "state": "closed",
                "labels": [{"name": "docs"}],
                "html_url": "https://github.com/example/repo/issues/999",
                "user": {"login": "contributor2"},
            },
        ]

        analyzer = GitHubIssueAnalyzer("https://github.com/example/repo")
        matches = analyzer.match_issues("src/services/PaymentService.java", issues)

        self.assertEqual(len(matches), 1)
        match = matches[0]
        self.assertEqual(match["number"], 142)
        self.assertEqual(match["relevance"], "HIGH")
        self.assertTrue(any("File name found" in e or "File path found" in e for e in match["evidence"]))

    def test_match_issues_no_false_positives(self):
        issues = [
            {
                "number": 50,
                "title": "Unrelated database query timeout",
                "body": "Postgres connection pool exhausted",
                "state": "open",
                "labels": [{"name": "database"}],
            }
        ]
        analyzer = GitHubIssueAnalyzer("https://github.com/example/repo")
        matches = analyzer.match_issues("src/auth/UserTokenGenerator.py", issues)
        self.assertEqual(len(matches), 0)

    def test_error_handling_404(self):
        analyzer = GitHubIssueAnalyzer("https://github.com/nonexistent/private-repo")
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.ok = False
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            result = analyzer.fetch_issues()
            self.assertFalse(result["available"])
            self.assertIn("repository is missing or private", result["message"])

    def test_error_handling_rate_limit(self):
        analyzer = GitHubIssueAnalyzer("https://github.com/example/repo")
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.ok = False
            mock_response.status_code = 403
            mock_get.return_value = mock_response

            result = analyzer.fetch_issues()
            self.assertFalse(result["available"])
            self.assertIn("API access or rate limit reached", result["message"])

    def test_error_handling_network_failure(self):
        analyzer = GitHubIssueAnalyzer("https://github.com/example/repo")
        with patch("requests.get", side_effect=requests.RequestException("Connection timed out")):
            result = analyzer.fetch_issues()
            self.assertFalse(result["available"])
            self.assertEqual(result["message"], "GitHub issue analysis unavailable.")

    def test_print_report_with_matches(self):
        import io
        import sys
        report = {
            "available": True,
            "message": None,
            "matches": [
                {
                    "number": 142,
                    "title": "Payment validation failure",
                    "state": "OPEN",
                    "labels": ["bug", "payment"],
                    "relevance": "HIGH",
                    "evidence": ["File name found in issue title"],
                    "url": "https://github.com/example/repo/issues/142",
                }
            ]
        }
        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            GitHubIssueAnalyzer.print_report("PaymentService.java", report, risk_level="HIGH")
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        self.assertIn("RELATED GITHUB ISSUES", output)
        self.assertIn("File:\nPaymentService.java", output)
        self.assertIn("Risk:\nHIGH", output)
        self.assertIn("#142", output)
        self.assertIn("Payment validation failure", output)
        self.assertIn("Status: OPEN", output)
        self.assertIn("Labels: bug, payment", output)
        self.assertIn("Relevance: HIGH", output)
        self.assertIn("Recommendation:", output)
        self.assertIn("Possible contribution:", output)

    def test_print_report_no_matches(self):
        import io
        import sys
        report = {
            "available": True,
            "message": None,
            "matches": []
        }
        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            GitHubIssueAnalyzer.print_report("PaymentService.java", report)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        self.assertIn("No strongly related GitHub issues were found by CodePulse.", output)
        self.assertNotIn("There are no issues.", output)

    def test_print_report_unavailable(self):
        import io
        import sys
        report = {
            "available": False,
            "message": "GitHub issue analysis unavailable: API access or rate limit reached.",
            "matches": []
        }
        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            GitHubIssueAnalyzer.print_report("PaymentService.java", report)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        self.assertIn("GitHub issue analysis unavailable", output)
        self.assertIn("CodePulse analysis continues without issue information.", output)


if __name__ == "__main__":
    unittest.main()
