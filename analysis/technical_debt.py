from pathlib import Path

import pandas as pd

from codepulse_runtime import TECHNICAL_DEBT_PATH, project_path


class TechnicalDebtAnalyzer:
    """Calculate explainable technical-debt scores from existing analysis data.

    File debt is a weighted average of normalized signals: complexity/size
    (35%), ML historical-risk probability (25%), duplication (20%),
    maintainability debt (10%), and churn (10%). Signals that are unavailable
    are excluded and the remaining weights are renormalized. Duplication is
    remains unavailable when Phase 8 supplies no results.
    """

    WEIGHTS = {
        "complexity": 0.35,
        "ml": 0.25,
        "duplication": 0.20,
        "maintainability": 0.10,
        "churn": 0.10,
    }
    LEVEL_THRESHOLDS = {
        "LOW": 25.0,
        "MEDIUM": 50.0,
        "HIGH": 75.0,
    }
    REQUIRED_COLUMNS = {"file"}

    @staticmethod
    def normalize(series):
        """Min-max normalize a repository-relative metric to 0-1."""
        values = pd.to_numeric(series, errors="coerce")
        available = values.notna()
        if not available.any():
            return pd.Series(pd.NA, index=series.index, dtype="Float64")
        minimum = values[available].min()
        maximum = values[available].max()
        if minimum == maximum:
            normalized = pd.Series(0.0, index=series.index)
            normalized[~available] = pd.NA
            return normalized.astype("Float64")
        normalized = ((values - minimum) / (maximum - minimum)).clip(0, 1)
        return normalized.astype("Float64")

    @staticmethod
    def classify(score):
        if score >= TechnicalDebtAnalyzer.LEVEL_THRESHOLDS["HIGH"]:
            return "CRITICAL" if score >= 90 else "HIGH"
        if score >= TechnicalDebtAnalyzer.LEVEL_THRESHOLDS["MEDIUM"]:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _relative_path(path, repository_path):
        if not repository_path:
            return str(path).replace("\\", "/")
        try:
            return str(Path(path).resolve().relative_to(
                Path(repository_path).resolve()
            )).replace("\\", "/")
        except (ValueError, OSError):
            return str(path).replace("\\", "/")

    def _maintainability_values(self, code_metrics, repository_path):
        values = {}
        for metric in code_metrics or []:
            value = metric.get("maintainability")
            if value is not None:
                try:
                    values[self._relative_path(metric["file"], repository_path)] = float(value)
                except (KeyError, TypeError, ValueError):
                    continue
        if not values:
            return {}
        maximum = max(values.values())
        minimum = min(values.values())
        if maximum == minimum:
            return {path: 0.0 for path in values}
        return {
            path: 1 - ((value - minimum) / (maximum - minimum))
            for path, value in values.items()
        }

    @staticmethod
    def _prediction_values(predictions):
        if predictions is None or predictions.empty or "file" not in predictions:
            return {}
        if "bug_probability" not in predictions:
            return {}
        return {
            str(row["file"]).replace("\\", "/"): float(row["bug_probability"])
            for _, row in predictions.iterrows()
            if pd.notna(row.get("bug_probability"))
        }

    def _duplication_values(self, duplication):
        """Read optional Phase 8-compatible duplication data when supplied."""
        if duplication is None:
            return {}
        if isinstance(duplication, pd.DataFrame):
            if "file" not in duplication or not duplication.shape[0]:
                return {}
            column = next(
                (name for name in (
                    "duplication_score", "duplication_ratio", "duplicate_lines"
                ) if name in duplication),
                None,
            )
            if column is None:
                return {}
            values = pd.to_numeric(duplication[column], errors="coerce")
            if column in {"duplication_score", "duplication_ratio"}:
                normalized = values.clip(0, 1)
            else:
                normalized = self.normalize(values)
            return {
                str(row["file"]).replace("\\", "/"): float(normalized.loc[index])
                for index, row in duplication.iterrows()
                if pd.notna(normalized.loc[index])
            }
        return {}

    def _reasons(self, row):
        reasons = []
        if row["complexity_component"] is not None and row["complexity_component"] >= 0.75:
            reasons.append("Very high relative complexity or file size")
        if row["ml_component"] is not None and row["ml_component"] >= 0.75:
            reasons.append("Elevated ML historical defect risk")
        if row["maintainability_component"] is not None and row["maintainability_component"] >= 0.75:
            reasons.append("Low relative maintainability")
        if row["churn_component"] is not None and row["churn_component"] >= 0.75:
            reasons.append("High historical code churn")
        if row["duplication_component"] is not None and row["duplication_component"] >= 0.75:
            reasons.append("High code duplication")
        if not reasons:
            reasons.append("No strong relative debt indicators")
        return reasons

    def analyze(self, dataset, predictions=None, code_metrics=None,
                duplication=None, repository_path=None):
        if dataset is None or dataset.empty:
            raise ValueError("A non-empty feature dataset is required.")
        missing = self.REQUIRED_COLUMNS - set(dataset.columns)
        if missing:
            raise ValueError(f"Technical debt data is missing columns: {sorted(missing)}")

        data = dataset.copy()
        data["file"] = data["file"].astype(str).str.replace("\\", "/", regex=False)
        ml_values = self._prediction_values(predictions)
        maintainability_values = self._maintainability_values(code_metrics, repository_path)
        duplication_values = self._duplication_values(duplication)

        complexity_values = None
        if "complexity" in data:
            complexity_values = pd.to_numeric(data["complexity"], errors="coerce")
        loc_values = None
        if "loc" in data:
            loc_values = pd.to_numeric(data["loc"], errors="coerce")
        if complexity_values is not None and loc_values is not None:
            complexity_input = complexity_values.fillna(0) + loc_values.fillna(0) / 100
        elif complexity_values is not None:
            complexity_input = complexity_values
        else:
            complexity_input = loc_values
        complexity = self.normalize(complexity_input) if complexity_input is not None else None
        churn = self.normalize(data["code_churn"]) if "code_churn" in data else None

        rows = []
        for index, row in data.iterrows():
            file_path = row["file"]
            components = {
                "complexity": None if complexity is None or pd.isna(complexity.loc[index]) else float(complexity.loc[index]),
                "ml": ml_values.get(file_path),
                "duplication": duplication_values.get(file_path),
                "maintainability": maintainability_values.get(file_path),
                "churn": None if churn is None or pd.isna(churn.loc[index]) else float(churn.loc[index]),
            }
            available = {
                name: value for name, value in components.items()
                if value is not None and pd.notna(value)
            }
            weight_total = sum(self.WEIGHTS[name] for name in available)
            score = 100 * sum(
                available[name] * self.WEIGHTS[name] for name in available
            ) / weight_total if weight_total else 0.0
            result = {
                "file": file_path,
                "technical_debt_score": round(score, 2),
                "technical_debt_level": self.classify(score),
                "complexity_component": None if components["complexity"] is None else round(components["complexity"] * 100, 2),
                "ml_component": None if components["ml"] is None else round(components["ml"] * 100, 2),
                "duplication_component": None if components["duplication"] is None else round(components["duplication"] * 100, 2),
                "maintainability_component": None if components["maintainability"] is None else round(components["maintainability"] * 100, 2),
                "churn_component": None if components["churn"] is None else round(components["churn"] * 100, 2),
                "duplication_available": components["duplication"] is not None,
                "ml_available": components["ml"] is not None,
                "maintainability_available": components["maintainability"] is not None,
            }
            result["debt_reasons"] = self._reasons({
                "complexity_component": components["complexity"],
                "ml_component": components["ml"],
                "duplication_component": components["duplication"],
                "maintainability_component": components["maintainability"],
                "churn_component": components["churn"],
            })
            rows.append(result)

        return pd.DataFrame(rows).sort_values(
            "technical_debt_score", ascending=False
        ).reset_index(drop=True)

    def summarize(self, debt_data, top_n=10):
        if debt_data is None or debt_data.empty:
            raise ValueError("Technical debt data is empty.")
        counts = debt_data["technical_debt_level"].value_counts()
        high_count = int(counts.get("HIGH", 0) + counts.get("CRITICAL", 0))
        score = float(debt_data["technical_debt_score"].mean())
        return {
            "repository_debt_score": round(score, 2),
            "debt_level": self.classify(score),
            "low_count": int(counts.get("LOW", 0)),
            "medium_count": int(counts.get("MEDIUM", 0)),
            "high_count": int(counts.get("HIGH", 0)),
            "critical_count": int(counts.get("CRITICAL", 0)),
            "high_critical_percentage": round(100 * high_count / len(debt_data), 2),
            "top_files": debt_data.head(top_n).to_dict("records"),
            "duplication_available": bool(debt_data["duplication_available"].any()) if "duplication_available" in debt_data else False,
        }

    def save(self, debt_data, output_path=TECHNICAL_DEBT_PATH):
        output_path = project_path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        saved = debt_data.copy()
        saved["debt_reasons"] = saved["debt_reasons"].apply(lambda reasons: " | ".join(reasons))
        saved.to_csv(output_path, index=False)
        return output_path

    @staticmethod
    def print_report(summary, limit=10):
        print("\n==========================================")
        print("        TECHNICAL DEBT ANALYSIS")
        print("==========================================")
        print(f"Repository Debt Score: {summary['repository_debt_score']:.1f} / 100")
        print(f"Debt Level: {summary['debt_level']}")
        print(f"Low: {summary['low_count']}  Medium: {summary['medium_count']}  "
              f"High: {summary['high_count']}  Critical: {summary['critical_count']}")
        print(f"HIGH/CRITICAL files: {summary['high_critical_percentage']:.1f}%")
        duplication_status = (
            "Available"
            if summary.get("duplication_available")
            else "Not available for this run"
        )
        print(f"Duplication: {duplication_status}")
        print("\nTop debt-prone files:")
        for rank, item in enumerate(summary["top_files"][:limit], start=1):
            print(f"{rank}. {item['file']}  {item['technical_debt_score']:.1f}/100  "
                  f"{item['technical_debt_level']}")
            print(f"   {', '.join(item['debt_reasons'])}")
        print("==========================================")