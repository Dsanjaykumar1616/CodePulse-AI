from pathlib import Path

import pandas as pd

from codepulse_runtime import REVIEW_PATH, project_path


class RuleBasedCodeReviewer:
    """Generate deterministic, evidence-based review findings."""

    RULES = {
        "complexity": {"id": "COMPLEXITY_HIGH", "percentile": 0.90, "minimum": 10},
        "loc": {"id": "LARGE_FILE", "percentile": 0.90, "minimum": 200},
        "nesting_depth": {"id": "NESTING_DEEP", "percentile": 0.90, "minimum": 4},
        "maintainability": {"id": "MAINTAINABILITY_LOW", "percentile": 0.25},
        "comment_ratio": {"id": "DOCUMENTATION_LOW", "percentile": 0.25, "minimum": 0.10},
        "code_churn": {"id": "CHURN_HIGH", "percentile": 0.90, "minimum": 20},
        "bug_fix_commits": {"id": "BUG_FIX_ACTIVITY_HIGH", "percentile": 0.90, "minimum": 3},
    }
    SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def __init__(self, percentile_overrides=None):
        self.percentile_overrides = percentile_overrides or {}

    @staticmethod
    def _relative(path, repository_path):
        if not repository_path:
            return str(path).replace("\\", "/")
        try:
            return str(Path(path).resolve().relative_to(
                Path(repository_path).resolve()
            )).replace("\\", "/")
        except (ValueError, OSError):
            return str(path).replace("\\", "/")

    @staticmethod
    def _severity(rule_name, value, cutoff, percentile):
        if rule_name == "maintainability":
            gap = cutoff - value
        else:
            gap = value - cutoff
        spread = abs(cutoff) or 1.0
        if (rule_name == "maintainability" and value <= 20) or (
                rule_name != "maintainability" and value >= max(cutoff * 1.5, cutoff + spread)):
            return "CRITICAL"
        if gap >= spread * 0.5:
            return "HIGH"
        if percentile <= 0.25:
            return "MEDIUM"
        return "MEDIUM"

    @staticmethod
    def _recommendation(rule_name):
        return {
            "complexity": "Split complex logic into smaller, focused functions.",
            "loc": "Consider modularizing the file into smaller responsibilities.",
            "nesting_depth": "Reduce nested branches and extract helper functions.",
            "maintainability": "Refactor maintainability hotspots before larger changes.",
            "comment_ratio": "Add focused documentation for non-obvious behavior.",
            "code_churn": "Review recent changes and make the next change narrowly scoped.",
            "bug_fix_commits": "Review historical bug fixes and add regression coverage.",
            "duplicate": "Consider consolidating repeated implementation carefully.",
        }[rule_name]

    def _finding(self, file_path, rule_id, severity, title, metric, value, recommendation):
        return {
            "file": file_path,
            "rule_id": rule_id,
            "severity": severity,
            "title": title,
            "evidence": f"{metric} = {value}",
            "metric": metric,
            "value": value,
            "recommendation": recommendation,
        }

    def _maintainability_values(self, code_metrics, repository_path):
        values = {}
        for item in code_metrics or []:
            value = item.get("maintainability")
            if value is not None:
                try:
                    values[self._relative(item["file"], repository_path)] = float(value)
                except (KeyError, TypeError, ValueError):
                    continue
        return values

    def review(self, dataset, code_metrics=None, duplicate_pairs=None,
               repository_path=None):
        if dataset is None or dataset.empty:
            return pd.DataFrame(columns=[
                "file", "rule_id", "severity", "title", "evidence",
                "metric", "value", "recommendation",
            ])

        data = dataset.copy()
        data["file"] = data["file"].astype(str).str.replace("\\", "/", regex=False)
        maintainability = self._maintainability_values(code_metrics, repository_path)
        findings = []
        high_rules = {
            "complexity": ("High cyclomatic complexity", "Cyclomatic complexity"),
            "loc": ("Large source file", "Lines of code"),
            "nesting_depth": ("Deep nesting", "Nesting depth"),
            "maintainability": ("Low maintainability", "Maintainability index"),
            "comment_ratio": ("Low documentation ratio", "Comment ratio"),
            "code_churn": ("High code churn", "Code churn"),
            "bug_fix_commits": ("Frequent bug-fix activity", "Bug-fix commits"),
        }

        for metric_name, (title, metric_label) in high_rules.items():
            if metric_name != "maintainability" and metric_name not in data:
                continue
            series = (pd.Series({file_path: value for file_path, value in maintainability.items()})
                      if metric_name == "maintainability" else
                      pd.to_numeric(data[metric_name], errors="coerce"))
            if series is None or series.dropna().empty:
                continue
            values = series.dropna()
            config = self.RULES[metric_name]
            percentile = self.percentile_overrides.get(
                metric_name, config["percentile"]
            )
            cutoff = values.quantile(percentile)
            minimum = config.get("minimum")
            for index, value in values.items():
                file_path = index if metric_name == "maintainability" else data.loc[index, "file"]
                if metric_name in {"maintainability", "comment_ratio"}:
                    minimum = config.get("minimum")
                    triggered = value <= cutoff and (minimum is None or value <= minimum)
                else:
                    triggered = value >= cutoff and (minimum is None or value >= minimum)
                if not triggered:
                    continue
                severity = self._severity(metric_name, float(value), float(cutoff), percentile)
                findings.append(self._finding(
                    file_path,
                    config["id"],
                    severity,
                    title,
                    metric_label,
                    round(float(value), 3),
                    self._recommendation(metric_name),
                ))

        if duplicate_pairs is not None and not duplicate_pairs.empty:
            for _, pair in duplicate_pairs.iterrows():
                similarity = float(pair["similarity_score"])
                if similarity < 80:
                    continue
                severity = "CRITICAL" if similarity >= 90 else "HIGH"
                for file_path in (pair["file_a"], pair["file_b"]):
                    findings.append(self._finding(
                        file_path,
                        "DUPLICATE_CODE",
                        severity,
                        "Similar implementation detected",
                        "Similarity score",
                        similarity,
                        self._recommendation("duplicate"),
                    ))

        return pd.DataFrame(findings, columns=[
            "file", "rule_id", "severity", "title", "evidence",
            "metric", "value", "recommendation",
        ]).sort_values(
            by=["severity", "value", "file"],
            key=lambda column: column.map({level: index for index, level in enumerate(self.SEVERITIES)})
            if column.name == "severity" else column,
            ascending=[False, False, True],
        ).reset_index(drop=True) if findings else pd.DataFrame(columns=[
            "file", "rule_id", "severity", "title", "evidence",
            "metric", "value", "recommendation",
        ])

    def summarize(self, findings, top_n=10, files_reviewed=None):
        counts = findings["severity"].value_counts() if findings is not None and not findings.empty else {}
        return {
            "files_reviewed": (
                int(files_reviewed)
                if files_reviewed is not None
                else (0 if findings is None or findings.empty else findings["file"].nunique())
            ),
            "total_findings": 0 if findings is None else len(findings),
            "critical_count": int(counts.get("CRITICAL", 0)),
            "high_count": int(counts.get("HIGH", 0)),
            "medium_count": int(counts.get("MEDIUM", 0)),
            "low_count": int(counts.get("LOW", 0)),
            "top_findings": [] if findings is None else findings.head(top_n).to_dict("records"),
        }

    def save(self, findings, output_path=REVIEW_PATH):
        output_path = project_path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        findings.to_csv(output_path, index=False)
        return output_path

    @staticmethod
    def print_report(summary, limit=10):
        print("\n==========================================")
        print("        RULE-BASED CODE REVIEW")
        print("==========================================")
        print(f"Files reviewed: {summary['files_reviewed']}")
        print(f"Total findings: {summary['total_findings']}")
        print(f"CRITICAL: {summary['critical_count']}  HIGH: {summary['high_count']}  "
              f"MEDIUM: {summary['medium_count']}  LOW: {summary['low_count']}")
        if not summary["top_findings"]:
            print("No rule violations detected.")
        else:
            print("\nTop Issues:")
            for rank, finding in enumerate(summary["top_findings"][:limit], start=1):
                print(f"{rank}. {finding['severity']} - {finding['rule_id']} - {finding['file']}")
                print(f"   {finding['evidence']}")
                print(f"   {finding['recommendation']}")
        print("==========================================")