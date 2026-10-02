from pathlib import Path

import pandas as pd


class FileRiskExplainer:
    """Explain file risk using only metrics produced by earlier phases."""

    @staticmethod
    def _cutoff(data, column, quantile=0.75):
        return pd.to_numeric(data[column], errors="coerce").fillna(0).quantile(
            quantile
        )

    @staticmethod
    def _maintainability_by_file(code_metrics, repository_path):
        values = {}
        root = Path(repository_path).resolve()

        for metric in code_metrics or []:
            try:
                relative_path = str(Path(metric["file"]).resolve().relative_to(
                    root
                )).replace("\\", "/")
            except ValueError:
                continue

            if metric.get("maintainability") is not None:
                values[relative_path] = float(metric["maintainability"])

        return values

    def explain(self, file_path, dataset, predictions=None, code_metrics=None,
                repository_path=None):
        normalized_path = file_path.strip().replace("\\", "/")
        matches = dataset[dataset["file"] == normalized_path]

        if matches.empty:
            stripped = normalized_path.lstrip("./").lstrip("/")
            matches = dataset[dataset["file"] == stripped]
            if not matches.empty:
                normalized_path = stripped

        if matches.empty and repository_path:
            try:
                rel = str(Path(file_path).resolve().relative_to(
                    Path(repository_path).resolve()
                )).replace("\\", "/")
                matches = dataset[dataset["file"] == rel]
                if not matches.empty:
                    normalized_path = rel
            except (ValueError, OSError):
                pass

        if matches.empty:
            raise ValueError(
                "File not found in the current analysis dataset: "
                f"{normalized_path}"
            )

        data = dataset.copy()
        row = matches.iloc[0].copy()
        probability = 0.0
        risk_level = "Not available"

        if predictions is not None and not predictions.empty:
            prediction = predictions[predictions["file"] == normalized_path]
            if not prediction.empty:
                probability = float(prediction.iloc[0]["bug_probability"])
                risk_level = prediction.iloc[0]["risk_level"]

        complexity_high = (
            row["complexity"] > 0
            and row["complexity"] >= self._cutoff(data, "complexity")
        )
        loc_high = row["loc"] >= self._cutoff(data, "loc")
        churn_high = (
            row["code_churn"] > 0
            and row["code_churn"] >= self._cutoff(data, "code_churn")
        )
        commits_high = (
            row["commit_count"] > 0
            and row["commit_count"] >= self._cutoff(data, "commit_count")
        )
        bug_fixes_high = (
            row["bug_fix_commits"] > 0
            and row["bug_fix_commits"] >= self._cutoff(data, "bug_fix_commits")
        )
        nesting_high = (
            row["nesting_depth"] > 0
            and row["nesting_depth"] >= self._cutoff(data, "nesting_depth")
        )

        maintainability_dict = self._maintainability_by_file(
            code_metrics, repository_path
        )
        maintainability = maintainability_dict.get(normalized_path)
        maintainability_low = False
        if maintainability is not None and maintainability_dict:
            all_maintainability = list(maintainability_dict.values())
            maintainability_low = maintainability <= pd.Series(
                all_maintainability
            ).quantile(0.25)

        reasons = []
        if complexity_high:
            reasons.append("High cyclomatic complexity")
        if loc_high:
            reasons.append("Large file")
        if churn_high:
            reasons.append("Frequently modified (high code churn)")
        if bug_fixes_high:
            reasons.append("Repeated historical bug-fix activity")
        if commits_high:
            reasons.append("Frequently modified across commits")
        if maintainability_low:
            reasons.append("Low maintainability")
        if probability >= 0.50:
            reasons.append("Model predicts elevated historical defect risk")
        if nesting_high:
            reasons.append("Deep nesting may reduce readability")

        if complexity_high:
            recommendation = (
                "Consider reviewing and refactoring the high-complexity "
                "functions before making larger changes."
            )
        elif churn_high or bug_fixes_high:
            recommendation = (
                "Consider reviewing recent changes and historical bug-fix "
                "commits before contributing to this file."
            )
        elif probability >= 0.50:
            recommendation = (
                "Suggested investigation: review this file carefully and "
                "make a small, well-tested improvement if appropriate."
            )
        else:
            recommendation = (
                "No critical rule-based risk factors were found. Consider a "
                "small documentation or cleanup contribution if needed."
            )

        return {
            "file": normalized_path,
            "risk_level": risk_level,
            "bug_probability": probability,
            "metrics": {
                "loc": int(row["loc"]),
                "complexity": int(row["complexity"]),
                "nesting_depth": int(row["nesting_depth"]),
                "commit_count": int(row["commit_count"]),
                "bug_fix_commits": int(row["bug_fix_commits"]),
                "contributors": int(row["contributors"]),
                "code_churn": int(row["code_churn"]),
                "maintainability": maintainability,
            },
            "reasons": reasons,
            "recommendation": recommendation,
            "complexity_high": complexity_high,
            "churn_high": churn_high,
        }

    @staticmethod
    def print_report(explanation):
        metrics = explanation["metrics"]
        print("\n==========================================")
        print("           FILE RISK ANALYSIS")
        print("==========================================")
        print(f"File: {explanation['file']}")
        print(f"Risk: {explanation['risk_level'].upper()}")
        print(
            f"ML Historical-Risk Probability: "
            f"{explanation['bug_probability']:.0%}"
        )
        print("\nPotential risk because:")
        if explanation["reasons"]:
            for reason in explanation["reasons"]:
                print(f"- {reason}")
        else:
            print("- No high-risk rule-based factors were detected.")

        print("\nMetrics:")
        print(f"LOC:                 {metrics['loc']}")
        print(f"Complexity:          {metrics['complexity']}")
        print(f"Nesting Depth:       {metrics['nesting_depth']}")
        print(f"Commit Count:        {metrics['commit_count']}")
        print(f"Bug-Fix Commits:     {metrics['bug_fix_commits']}")
        print(f"Contributors:        {metrics['contributors']}")
        print(f"Code Churn:          {metrics['code_churn']}")
        if metrics["maintainability"] is not None:
            print(f"Maintainability:     {metrics['maintainability']:.1f}")
        else:
            print("Maintainability:     Not available")

        print("\nRecommendation:")
        print(explanation["recommendation"])
        print("==========================================")
