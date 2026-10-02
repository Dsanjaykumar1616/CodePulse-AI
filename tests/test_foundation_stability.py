import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from git import Repo

from analyzer.repository_analyzer import RepositoryAnalyzer
from codepulse_runtime import (
    FEATURES_PATH,
    MODEL_METADATA_PATH,
    MODEL_PATH,
    PREDICTIONS_PATH,
    RUN_METADATA_PATH,
    dataset_is_valid_for_run,
    invalidate_analysis_artifacts,
    predictions_are_valid_for_run,
    repository_identity,
)
from github.issue_analyzer import GitHubIssueAnalyzer
from ml.defect_prediction import DefectPredictionModel
from ml.feature_engineering import FeatureEngineer


class TestFoundationStability(unittest.TestCase):
    def tearDown(self):
        invalidate_analysis_artifacts("test cleanup")

    def test_empty_dataset_invalidates_previous_artifacts(self):
        FEATURES_PATH.parent.mkdir(parents=True, exist_ok=True)
        FEATURES_PATH.write_text("stale", encoding="utf-8")
        PREDICTIONS_PATH.write_text("stale", encoding="utf-8")
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        MODEL_PATH.write_text("stale", encoding="utf-8")
        MODEL_METADATA_PATH.write_text("stale", encoding="utf-8")
        RUN_METADATA_PATH.write_text("{}", encoding="utf-8")

        invalidate_analysis_artifacts("empty current analysis")

        self.assertFalse(FEATURES_PATH.exists())
        self.assertFalse(PREDICTIONS_PATH.exists())
        self.assertFalse(MODEL_PATH.exists())
        self.assertFalse(MODEL_METADATA_PATH.exists())
        self.assertFalse(RUN_METADATA_PATH.exists())

    def test_dataset_and_predictions_must_belong_to_current_repository(self):
        dataset = pd.DataFrame([
            {"file": "src/app.py", "language": "Python", "bug_label": 0}
        ])
        predictions = pd.DataFrame([
            {"file": "src/app.py", "bug_probability": 0.1, "risk_level": "Low"}
        ])
        write_metadata = {
            "repository": repository_identity("https://github.com/example/current")
        }
        RUN_METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        RUN_METADATA_PATH.write_text(json.dumps(write_metadata), encoding="utf-8")

        self.assertTrue(dataset_is_valid_for_run(dataset, "example/current"))
        self.assertTrue(predictions_are_valid_for_run(
            predictions, dataset, "https://github.com/example/current"
        ))
        self.assertFalse(dataset_is_valid_for_run(dataset, "example/old"))
        self.assertFalse(predictions_are_valid_for_run(
            predictions.assign(file="old.py"), dataset,
            "https://github.com/example/current"
        ))

    def test_repository_name_collision_uses_owner_identity(self):
        first = RepositoryAnalyzer("https://github.com/one/project")
        second = RepositoryAnalyzer("https://github.com/two/project")
        same = RepositoryAnalyzer("https://github.com/one/project.git")

        self.assertNotEqual(first.repo_path, second.repo_path)
        self.assertEqual(first.repo_path, same.repo_path)
        self.assertEqual(first.repo_name, second.repo_name)

    def test_matching_legacy_repository_is_reused(self):
        with tempfile.TemporaryDirectory() as temporary:
            legacy_path = Path(temporary) / "project"
            legacy_path.mkdir()
            repository = Repo.init(legacy_path)
            repository.create_remote(
                "origin", "https://github.com/one/project.git"
            )

            analyzer = RepositoryAnalyzer(
                "https://github.com/one/project",
                clone_directory=temporary,
            )

            self.assertEqual(analyzer.repo_path, str(legacy_path))

    def test_ml_skips_one_class_and_invalid_datasets(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "features.csv"
            pd.DataFrame([
                {"file": "a.py", "language": "Python", "bug_label": 0,
                 **{feature: 0 for feature in DefectPredictionModel.FEATURES}}
            ]).to_csv(path, index=False)
            model = DefectPredictionModel(path)
            model.load_dataset()
            with self.assertRaisesRegex(ValueError, "no files with the historical bug-fix"):
                model.prepare_data()

            invalid_path = Path(temporary) / "invalid.csv"
            pd.DataFrame([{"file": "a.py"}]).to_csv(invalid_path, index=False)
            invalid_model = DefectPredictionModel(invalid_path)
            invalid_model.load_dataset()
            with self.assertRaisesRegex(ValueError, "Missing columns"):
                invalid_model.prepare_data()

    def test_output_paths_are_project_root_relative(self):
        dataset = pd.DataFrame([{"file": "a.py", "language": "Python"}])
        with tempfile.TemporaryDirectory() as temporary:
            previous = Path.cwd()
            try:
                os.chdir(temporary)
                FeatureEngineer(temporary).save_dataset(dataset, "data/datasets/path-test.csv")
            finally:
                os.chdir(previous)

        self.assertTrue((Path(__file__).parents[1] / "data/datasets/path-test.csv").exists())
        (Path(__file__).parents[1] / "data/datasets/path-test.csv").unlink()

    def test_closed_issue_is_context_not_active_recommendation(self):
        analyzer = GitHubIssueAnalyzer("https://github.com/example/repo")
        report = {
            "available": True,
            "matches": [
                {"number": 7, "title": "Old app.py issue", "state": "CLOSED",
                 "labels": [], "relevance": "HIGH", "evidence": []}
            ]
        }
        with patch("builtins.print") as output:
            analyzer.print_report("app.py", report)
            text = "\n".join(
                " ".join(str(argument) for argument in call.args)
                for call in output.call_args_list
            )
        self.assertIn("historical context only", text)
        self.assertIn("No open related issue", text)
        self.assertNotIn("Work on an existing issue", text)


if __name__ == "__main__":
    unittest.main()
