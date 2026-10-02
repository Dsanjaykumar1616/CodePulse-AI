import os
from pathlib import Path

import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    classification_report
)

from codepulse_runtime import MODEL_DIR, PREDICTIONS_PATH, project_path


class DefectPredictionModel:

    # =========================================
    # Features used by ML
    # =========================================

    FEATURES = [
        "loc",
        "complexity",
        "functions",
        "classes",
        "nesting_depth",
        "comment_ratio",
        "commit_count",
        "contributors",
        "code_churn",
        "file_age_days"
    ]

    TARGET = "bug_label"

    # =========================================
    # Constructor
    # =========================================

    def __init__(
        self,
        dataset_path,
        model_directory=None
    ):

        self.dataset_path = project_path(dataset_path)

        self.model_directory = Path(model_directory) if model_directory else MODEL_DIR
        self.model_directory = project_path(self.model_directory)

        os.makedirs(
            self.model_directory,
            exist_ok=True
        )

        self.data = None

        self.X_train = None
        self.X_test = None

        self.y_train = None
        self.y_test = None

        self.models = {}

        self.results = {}

        self.predictions = None

        self.class_distribution = {}

    # =========================================
    # Load Dataset
    # =========================================

    def load_dataset(self):

        print(
            "\nLoading ML dataset..."
        )

        self.data = pd.read_csv(
            self.dataset_path
        )

        print(
            f"Dataset loaded successfully."
        )

        print(
            f"Total rows: "
            f"{len(self.data)}"
        )

        print(
            f"Total columns: "
            f"{len(self.data.columns)}"
        )

        return self.data

    # =========================================
    # Prepare Dataset
    # =========================================

    def prepare_data(self):

        print(
            "\nPreparing data for ML..."
        )

        # Check required columns

        missing_columns = [

            column

            for column in self.FEATURES
            + [self.TARGET]

            if column not in self.data.columns
        ]

        if missing_columns:

            raise ValueError(
                "Missing columns: "
                + str(missing_columns)
            )

        X = self.data[
            self.FEATURES
        ].copy()

        y = self.data[
            self.TARGET
        ].copy()

        # Replace invalid values

        X = X.replace(
            [float("inf"), float("-inf")],
            0
        )

        # Fill missing values

        X = X.fillna(0)

        y = y.fillna(0).astype(int)

        print(
            "\nClass distribution:"
        )

        print(
            y.value_counts()
        )

        self.class_distribution = {
            int(label): int(count)
            for label, count in y.value_counts().items()
        }

        # Check whether both classes exist

        if y.nunique() < 2:

            raise ValueError(
                "ML training was skipped: this repository has no files "
                "with the historical bug-fix proxy label. Choose a "
                "repository with richer bug-fix history or combine data "
                "from multiple repositories."
            )

        # Train-test split

        # =========================================
        # Train-Test Split
        # =========================================

        class_counts = y.value_counts()

        minimum_class_count = class_counts.min()

        if minimum_class_count < 5:

            raise ValueError(
                "ML training was skipped: each class needs at least 5 "
                "files for a minimally meaningful stratified split. "
                f"Current smallest class contains {minimum_class_count}."
            )

        if minimum_class_count < 20:

            print(
                "\nWarning: the minority class has fewer than 20 files. "
                "The model can be demonstrated, but its evaluation is "
                "not reliable enough for a final conclusion."
            )

        if minimum_class_count >= 5:

            print(
                "\nUsing stratified train-test split."
            )

            self.X_train, self.X_test, \
            self.y_train, self.y_test = (
                train_test_split(
                    X,
                    y,
                    test_size=0.20,
                    random_state=42,
                    stratify=y
                )
            )

        print(
            f"\nTraining samples: "
            f"{len(self.X_train)}"
        )

        print(
            f"Testing samples: "
            f"{len(self.X_test)}"
        )

    # =========================================
    # Build Models
    # =========================================

    def build_models(self):

        # Logistic Regression
        #
        # Baseline model

        logistic_model = Pipeline(
            [
                (
                    "scaler",
                    StandardScaler()
                ),

                (
                    "classifier",
                    LogisticRegression(
                        max_iter=1000,
                        random_state=42
                    )
                )
            ]
        )

        # Random Forest
        #
        # Main model

        random_forest = RandomForestClassifier(
            n_estimators=200,
            random_state=42,
            class_weight="balanced"
        )

        # XGBoost
        #
        # Gradient-boosted tree model for comparison.

        xgboost_model = XGBClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=42,
            n_jobs=1
        )

        self.models = {

            "Logistic Regression":
                logistic_model,

            "Random Forest":
                random_forest,

            "XGBoost":
                xgboost_model
        }

    # =========================================
    # Train Models
    # =========================================

    def train_models(self):

        print(
            "\nTraining ML models..."
        )

        for name, model in (
            self.models.items()
        ):

            print(
                f"\nTraining: {name}"
            )

            model.fit(
                self.X_train,
                self.y_train
            )

            print(
                f"{name} training completed."
            )

    # =========================================
    # Evaluate Model
    # =========================================

    def evaluate_model(
        self,
        name,
        model
    ):

        predictions = model.predict(
            self.X_test
        )

        try:
            probabilities = (
                model.predict_proba(
                    self.X_test
                )[:, 1]
            )
            roc_auc = roc_auc_score(
                self.y_test,
                probabilities
            )
        except Exception:
            roc_auc = 0.0

        accuracy = accuracy_score(
            self.y_test,
            predictions
        )

        precision = precision_score(
            self.y_test,
            predictions,
            zero_division=0
        )

        recall = recall_score(
            self.y_test,
            predictions,
            zero_division=0
        )

        f1 = f1_score(
            self.y_test,
            predictions,
            zero_division=0
        )

        self.results[name] = {
            "accuracy":
                accuracy,

            "precision":
                precision,

            "recall":
                recall,

            "f1":
                f1,

            "roc_auc":
                roc_auc
        }

        print(
            f"\n========== {name} =========="
        )

        print(
            f"Accuracy : "
            f"{accuracy:.4f}"
        )

        print(
            f"Precision: "
            f"{precision:.4f}"
        )

        print(
            f"Recall   : "
            f"{recall:.4f}"
        )

        print(
            f"F1 Score : "
            f"{f1:.4f}"
        )

        print(
            f"ROC-AUC  : "
            f"{roc_auc:.4f}"
        )

        print(
            "\nClassification Report:"
        )

        print(
            classification_report(
                self.y_test,
                predictions,
                zero_division=0
            )
        )

    # =========================================
    # Evaluate All Models
    # =========================================

    def evaluate_models(self):

        print(
            "\nEvaluating models..."
        )

        for name, model in (
            self.models.items()
        ):

            self.evaluate_model(
                name,
                model
            )

    # =========================================
    # Select Best Model
    # =========================================

    def select_best_model(self):

        best_model_name = max(
            self.results,
            key=lambda name:
                self.results[name]["f1"]
        )

        best_model = self.models[
            best_model_name
        ]

        print(
            "\n=========================================="
        )

        print(
            "          BEST MODEL"
        )

        print(
            "=========================================="
        )

        print(
            f"Selected Model: "
            f"{best_model_name}"
        )

        print(
            f"F1 Score: "
            f"{self.results[best_model_name]['f1']:.4f}"
        )

        print(
            f"ROC-AUC: "
            f"{self.results[best_model_name]['roc_auc']:.4f}"
        )

        return (
            best_model_name,
            best_model
        )

    # =========================================
    # Save Best Model
    # =========================================

    def save_model(
        self,
        model,
        model_name
    ):

        model_path = os.path.join(
            self.model_directory,
            "codepulse_defect_model.pkl"
        )

        joblib.dump(
            model,
            model_path
        )

        print(
            f"\nModel saved to:"
        )

        print(
            model_path
        )

        # Save model metadata

        metadata = {

            "model":
                model_name,

            "features":
                self.FEATURES,

            "target":
                self.TARGET,

            "label_definition": (
                "bug_label = 1 when bug_fix_commits > 0; "
                "Git commit-message keyword proxy"
            ),

            "excluded_feature": (
                "bug_fix_commits is intentionally excluded from model "
                "inputs because it directly defines the target label."
            ),

            "class_distribution":
                self.class_distribution,

            "results":
                self.results
        }

        metadata_path = os.path.join(
            self.model_directory,
            "model_metadata.pkl"
        )

        joblib.dump(
            metadata,
            metadata_path
        )

        print(
            f"Model metadata saved to:"
        )

        print(
            metadata_path
        )

    # =========================================
    # Generate File-Level Risk Predictions
    # =========================================

    @staticmethod
    def classify_risk(probability):

        if probability >= 0.75:

            return "Critical"

        if probability >= 0.50:

            return "High"

        if probability >= 0.25:

            return "Medium"

        return "Low"

    def save_predictions(
        self,
        model,
        output_path=PREDICTIONS_PATH
    ):

        output_path = project_path(output_path)

        X = self.data[self.FEATURES].copy()

        X = X.replace(
            [float("inf"), float("-inf")],
            0
        ).fillna(0)

        probabilities = model.predict_proba(X)[:, 1]

        prediction_columns = [
            column
            for column in ["file", "language"]
            if column in self.data.columns
        ]

        predictions = self.data[
            prediction_columns
        ].copy()

        predictions["bug_probability"] = probabilities.round(4)

        predictions["risk_level"] = predictions[
            "bug_probability"
        ].apply(self.classify_risk)

        predictions = predictions.sort_values(
            "bug_probability",
            ascending=False
        )

        Path(output_path).parent.mkdir(
            parents=True,
            exist_ok=True
        )

        predictions.to_csv(
            output_path,
            index=False
        )

        print(
            "\nTop predicted high-risk files:"
        )

        print(
            predictions.head(10).to_string(
                index=False
            )
        )

        print(
            f"\nPredictions saved to: {output_path}"
        )

        self.predictions = predictions

        return predictions

    # =========================================
    # Complete ML Pipeline
    # =========================================

    def run(self):

        self.load_dataset()

        self.prepare_data()

        self.build_models()

        self.train_models()

        self.evaluate_models()

        (
            best_name,
            best_model
        ) = self.select_best_model()

        self.save_model(
            best_model,
            best_name
        )

        self.save_predictions(
            best_model
        )

        return self.results
