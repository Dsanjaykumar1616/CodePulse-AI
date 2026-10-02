import os
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from git import Repo

from git_analysis.git_history_analyzer import GitHistoryAnalyzer


class TestGitHistoryAnalyzer(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="codepulse_git_history_")
        self.repo = Repo.init(self.directory)
        self.repo.config_writer().set_value("user", "name", "Test User").release()
        self.repo.config_writer().set_value("user", "email", "test@example.com").release()
        self._commit_files(
            {"a.py": "one\n", "b.py": "one\n"},
            "initial shared files",
        )
        self._commit_files(
            {"a.py": "one\ntwo\nthree\n", "b.py": "one\ntwo\n"},
            "fix: repair shared bug",
        )

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def _commit_files(self, files, message):
        for name, content in files.items():
            path = Path(self.directory) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.repo.git.add(all=True)
        self.repo.index.commit(message)

    def test_per_file_metrics_and_shared_commits(self):
        results = GitHistoryAnalyzer(self.directory).analyze_repository()
        by_file = {item["file"]: item for item in results}
        self.assertEqual(set(by_file), {"a.py", "b.py"})
        self.assertEqual(by_file["a.py"]["commit_count"], 2)
        self.assertEqual(by_file["b.py"]["commit_count"], 2)
        self.assertEqual(by_file["a.py"]["contributors"], 1)
        self.assertEqual(by_file["a.py"]["bug_fix_commits"], 1)
        self.assertEqual(by_file["b.py"]["bug_fix_commits"], 1)
        self.assertGreater(by_file["a.py"]["code_churn"], 0)
        self.assertGreater(by_file["b.py"]["code_churn"], 0)
        self.assertLessEqual(by_file["a.py"]["lines_added"], 3)
        self.assertEqual(by_file["a.py"]["lines_deleted"], 0)
        self.assertIsNotNone(by_file["a.py"]["first_modified"])
        self.assertIsNotNone(by_file["a.py"]["last_modified"])
        self.assertFalse(by_file["a.py"]["history_limited"])

    def test_bounded_history_is_explicit(self):
        results = GitHistoryAnalyzer(self.directory, commit_limit=1).analyze_repository()
        by_file = {item["file"]: item for item in results}
        self.assertTrue(all(item["history_limited"] for item in results))
        self.assertEqual(by_file["a.py"]["history_commit_count"], 1)
        self.assertEqual(by_file["a.py"]["commit_count"], 1)
        self.assertEqual(by_file["a.py"]["bug_fix_commits"], 1)

    def test_empty_repository(self):
        empty_directory = tempfile.mkdtemp(prefix="codepulse_empty_git_")
        try:
            Repo.init(empty_directory)
            results = GitHistoryAnalyzer(empty_directory).analyze_repository()
            self.assertEqual(results, [])
        finally:
            shutil.rmtree(empty_directory, ignore_errors=True)

    def test_output_compatibility(self):
        result = GitHistoryAnalyzer(self.directory).analyze_repository()[0]
        expected = {
            "file", "commit_count", "contributors", "lines_added",
            "lines_deleted", "code_churn", "bug_fix_commits", "file_age_days",
            "first_modified", "last_modified",
        }
        self.assertTrue(expected.issubset(result))


if __name__ == "__main__":
    unittest.main()
