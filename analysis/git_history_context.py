import pandas as pd


class GitHistoryContext:
    """Present existing per-file Git metrics as contributor-friendly context."""

    @staticmethod
    def _activity_level(metric, all_metrics):
        churn_cutoff = pd.Series(
            [item["code_churn"] for item in all_metrics]
        ).quantile(0.75)
        commit_cutoff = pd.Series(
            [item["commit_count"] for item in all_metrics]
        ).quantile(0.75)

        if metric["code_churn"] >= churn_cutoff and metric["commit_count"] >= commit_cutoff:
            return "HIGH"
        if metric["code_churn"] > 0 or metric["commit_count"] > 0:
            return "MODERATE"
        return "LOW"

    def get_context(self, file_path, git_metrics):
        normalized = file_path.strip().replace("\\", "/").lstrip("./")
        metric = next(
            (
                item for item in git_metrics
                if item["file"].replace("\\", "/").lstrip("./") == normalized
            ),
            None
        )
        if metric is None:
            raise ValueError(f"Git history was not found for: {file_path}")

        activity = self._activity_level(metric, git_metrics)
        explanation = "This file has limited recorded activity."
        if metric["bug_fix_commits"] > 0 and activity == "HIGH":
            explanation = (
                "This file has been modified frequently and has historical "
                "bug-fix activity identified from commit-message keywords."
            )
        elif metric["bug_fix_commits"] > 0:
            explanation = (
                "This file has historical bug-fix activity identified from "
                "commit-message keywords."
            )
        elif activity == "HIGH":
            explanation = "This file has been modified frequently."

        return {
            **metric,
            "recent_activity": activity,
            "explanation": explanation,
        }

    @staticmethod
    def print_report(context):
        print("\n==========================================")
        print("            GIT HISTORY CONTEXT")
        print("==========================================")
        print(f"File: {context['file']}")
        print(f"First Modified: {context.get('first_modified') or 'Not available'}")
        print(f"Last Modified: {context.get('last_modified') or 'Not available'}")
        print(f"Total Commits: {context['commit_count']}")
        print(f"Contributors: {context['contributors']}")
        print(f"Code Churn: {context['code_churn']} lines")
        print(f"Bug-Fix Commits: {context['bug_fix_commits']}")
        print(f"Recent Activity: {context['recent_activity']}")
        print(f"\n{context['explanation']}")
        print("==========================================")
