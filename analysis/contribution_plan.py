from pathlib import Path


class ContributionPlanGenerator:
    """Create generic, non-destructive contribution plans from file evidence."""

    @staticmethod
    def _tests_detected(repository_path):
        root = Path(repository_path)
        return any((root / name).exists() for name in (
            "tests", "test", "__tests__"
        ))

    def create_plan(self, explanation, repository_path, context=None):
        metrics = explanation["metrics"]
        context = context or {}

        if explanation["complexity_high"]:
            contribution_type = "Refactoring"
        elif explanation["churn_high"]:
            contribution_type = "Stability improvement"
        else:
            contribution_type = "Documentation or small cleanup"

        probability = explanation["bug_probability"]
        if probability >= 0.75:
            priority = "HIGH"
        elif probability >= 0.50:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        if (explanation["complexity_high"] and explanation["churn_high"]
                and probability >= 0.75):
            difficulty = "ADVANCED"
        elif explanation["complexity_high"] or explanation["churn_high"]:
            difficulty = "INTERMEDIATE"
        else:
            difficulty = "BEGINNER"

        steps = [
            "Read the file and understand its responsibility before changing it.",
        ]
        if explanation["complexity_high"]:
            steps.append("Inspect the high-complexity functions and their callers.")
        elif explanation["churn_high"]:
            steps.append("Inspect recent changes to understand why this file changes often.")
        else:
            steps.append("Identify one small, clearly scoped improvement.")

        if metrics["bug_fix_commits"] > 0:
            steps.append("Review historical bug-fix commits for context and regressions.")

        if context.get("related_files"):
            steps.append("Inspect the related and dependent files before choosing the smallest change.")
        if context.get("history") and context["history"].get("commit_count", 0) > 0:
            steps.append("Review the target file's Git history and recent changes.")
        if context.get("open_issue"):
            steps.append("Review the related OPEN GitHub issue and its contribution requirements.")

        steps.extend([
            "Plan a small isolated change; avoid unrelated refactoring.",
            "Implement the improvement and review the changed code.",
        ])

        if context.get("impact"):
            steps.append("Review dependency impact and check affected callers before submitting.")

        if self._tests_detected(repository_path):
            steps.append(
                "Run the repository's available test suite before submitting the contribution."
            )
        else:
            steps.append(
                "Consider adding focused unit tests for the changed behavior before submitting the contribution."
            )

        steps.append("Prepare a clear Pull Request describing the limited change.")

        return {
            "target": explanation["file"],
            "contribution_type": contribution_type,
            "difficulty": difficulty,
            "priority": priority,
            "steps": steps,
        }

    @staticmethod
    def print_report(plan):
        print("\n==========================================")
        print("           CONTRIBUTION PLAN")
        print("==========================================")
        print(f"Target: {plan['target']}")
        print(f"Contribution Type: {plan['contribution_type']}")
        print(f"Difficulty: {plan['difficulty']}")
        print(f"Priority: {plan['priority']}\n")
        for number, step in enumerate(plan["steps"], start=1):
            print(f"STEP {number}")
            print(step)
        print("==========================================")
