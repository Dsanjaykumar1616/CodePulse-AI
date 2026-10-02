import shutil
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from analysis.duplicate_code import DuplicateCodeDetector
from analysis.technical_debt import TechnicalDebtAnalyzer


class TestDuplicateCodeDetector(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="codepulse_duplicates_"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_identical_code_detection(self):
        content = """
        def calculate_total(items):
            total = 0
            for item in items:
                total += item
            return total
        """
        self._write("one.py", content)
        self._write("two.py", content)
        pairs = DuplicateCodeDetector(self.root).analyze()
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs.iloc[0]["similarity_score"], 100.0)
        self.assertEqual(pairs.iloc[0]["similarity_level"], "HIGH")

    def test_comments_and_whitespace_are_ignored(self):
        self._write("one.py", """
        # first version
        def add_values(values):
            result = 0
            for value in values:
                result += value
            return result
        """)
        self._write("two.py", """
        def add_values(numbers):
          # different formatting
          result=0
          for number in numbers: result += number
          return result
        """)
        pairs = DuplicateCodeDetector(self.root).analyze()
        self.assertEqual(len(pairs), 1)
        self.assertGreaterEqual(pairs.iloc[0]["similarity_score"], 80)

    def test_different_code_is_not_marked_duplicate(self):
        self._write("one.py", "def alpha(value):\n    return value + 1\n" * 8)
        self._write("two.py", "def omega(value):\n    return value * value - 9\n" * 8)
        pairs = DuplicateCodeDetector(self.root).analyze()
        self.assertTrue(pairs.empty)

    def test_small_files_and_empty_repository(self):
        self._write("tiny.py", "x = 1\n")
        pairs = DuplicateCodeDetector(self.root).analyze()
        self.assertTrue(pairs.empty)
        summary = DuplicateCodeDetector(self.root).summarize(pairs)
        self.assertEqual(summary["duplicate_groups"], 0)
        self.assertEqual(summary["high_similarity_groups"], 0)

    def test_ignored_and_unsupported_files_are_not_scanned(self):
        content = "def shared(value):\n    return value + 1\n" * 8
        self._write("one.py", content)
        self._write("node_modules/two.py", content)
        self._write("notes.txt", content)
        pairs = DuplicateCodeDetector(self.root).analyze()
        self.assertTrue(pairs.empty)

    def test_per_file_signal_and_debt_integration(self):
        content = "def shared(value):\n    return value + 1\n" * 8
        self._write("one.py", content)
        self._write("two.py", content)
        pairs = DuplicateCodeDetector(self.root).analyze()
        signal = DuplicateCodeDetector.per_file_signal(pairs)
        dataset = pd.DataFrame([
            {"file": "one.py", "complexity": 1, "loc": 50, "code_churn": 1},
            {"file": "two.py", "complexity": 1, "loc": 50, "code_churn": 1},
        ])
        debt = TechnicalDebtAnalyzer().analyze(dataset, duplication=signal)
        self.assertTrue(debt["duplication_available"].all())
        self.assertTrue(debt["duplication_component"].notna().all())


if __name__ == "__main__":
    unittest.main()
