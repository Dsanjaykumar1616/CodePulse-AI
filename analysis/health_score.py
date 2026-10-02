from pathlib import Path

import pandas as pd


class RepositoryHealthScore:
    """Calculate an explainable 0-100 repository health score.

    Higher complexity, nesting, churn, commit activity, bug-fix activity, and
    predicted defect probability reduce health. Each metric is min-max
    normalized within the analyzed repository, so no artificial repository
    data or fixed metric values are introduced.

    Component weights are Code Quality 30%, Git Stability 30%, Defect Risk
    25%, and Maintainability 15%. If maintainability is unavailable for every
    analyzed language, that component is omitted and the remaining weights are
    proportionally rebalanced.
    """

    COMPONENT_WEIGHTS = {
        "code_quality": 0.30,
        "git_stability": 0.30,
        "defect_risk": 0.25,
        "maintainability": 0.15,
    }

    @staticmethod
    def _normalize(series):
        values = pd.to_numeric(series, errors="coerce").fillna(0)
        minimum = values.min()
        maximum = values.max()

        if maximum == minimum:
            return pd.Series(0.0, index=values.index)

        return (values - minimum) / (maximum - minimum)

    @staticmethod
    def _health_level(score):
        if score >= 90:
            return "Excellent"
        if score >= 75:
            return "Good"
        if score >= 60:
            return "Moderate"
        if score >= 40:
            return "Poor"
        return "Critical"

    @staticmethod
    def _relative_path(path, repository_path):
        try:
            return str(Path(path).resolve().relative_to(
                Path(repository_path).resolve()
            )).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")

    def _maintainability_score(self, code_metrics, repository_path):
        values = []

        for metric in code_metrics:
            value = metric.get("maintainability")
            if value is not None:
                values.append(float(value))

        if not values:
            return None

        # Radon's maintainability index is already on a 0-100 scale.
        return round(max(0, min(100, sum(values) / len(values))), 1)

    def calculate(self, dataset, predictions=None, code_metrics=None,
                  repository_path=None):
        if dataset.empty:
            raise ValueError("A non-empty feature dataset is required.")

        data = dataset.copy()

        # Code Quality: lower complexity/nesting and more comments are better.
        complexity_risk = self._normalize(data["complexity"])
        nesting_risk = self._normalize(data["nesting_depth"])
        comment_ratio = pd.to_numeric(
            data["comment_ratio"], errors="coerce"
        ).fillna(0).clip(lower=0, upper=1)
        documentation_risk = 1 - comment_ratio
        code_quality = 100 * (1 - (
            0.50 * complexity_risk
            + 0.30 * nesting_risk
            + 0.20 * documentation_risk
        ).mean())

        # Git Stability: lower churn, fewer repeated changes, and fewer
        # historical bug-fix commits indicate a more stable history.
        git_risk = (
            0.50 * self._normalize(data["code_churn"])
            + 0.25 * self._normalize(data["commit_count"])
            + 0.25 * self._normalize(data["bug_fix_commits"])
        )
        git_stability = 100 * (1 - git_risk.mean())

        components = {
            "code_quality": round(code_quality, 1),
            "git_stability": round(git_stability, 1),
        }

        if predictions is not None and not predictions.empty:
            defect_risk = pd.to_numeric(
                predictions["bug_probability"], errors="coerce"
            ).fillna(0).mean() * 100
            components["defect_risk"] = round(100 - defect_risk, 1)

        maintainability = self._maintainability_score(
            code_metrics or [], repository_path
        )
        if maintainability is not None:
            components["maintainability"] = maintainability

        available_weight = sum(
            self.COMPONENT_WEIGHTS[name]
            for name in components
        )
        overall_score = sum(
            components[name] * self.COMPONENT_WEIGHTS[name]
            for name in components
        ) / available_weight

        return {
            "overall_score": round(overall_score, 1),
            "health_level": self._health_level(overall_score),
            "components": components,
            "maintainability_available": maintainability is not None,
        }

    def print_report(self, repository_name, report):
        components = report["components"]
        print("\n==========================================")
        print("       CODEPULSE REPOSITORY HEALTH")
        print("==========================================")
        print(f"Repository: {repository_name}")
        print(f"Overall Health Score: {report['overall_score']:.1f} / 100")
        print(f"Health Level: {report['health_level'].upper()}")
        print(f"Code Quality:       {components['code_quality']:.1f} / 100")
        print(f"Git Stability:      {components['git_stability']:.1f} / 100")

        if "maintainability" in components:
            print(f"Maintainability:    {components['maintainability']:.1f} / 100")
        else:
            print("Maintainability:    Not available for analyzed languages")

        if "defect_risk" in components:
            print(f"Defect Risk Health: {components['defect_risk']:.1f} / 100")
        else:
            print("Defect Risk Health: Not available (ML training skipped)")

        print("==========================================")
