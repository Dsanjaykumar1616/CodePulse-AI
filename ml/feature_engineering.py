import pandas as pd
from pathlib import Path

from codepulse_runtime import project_path


class FeatureEngineer:

    ML_FEATURES = [
        "loc",
        "complexity",
        "functions",
        "classes",
        "nesting_depth",
        "comment_ratio",
        "commit_count",
        "contributors",
        "code_churn",
        "bug_fix_commits",
        "file_age_days"
    ]

    def __init__(self, repository_path):

        self.repository_path = Path(
            repository_path
        )

    # =========================================
    # Convert file path to relative path
    # =========================================

    def normalize_path(self, file_path):

        try:

            return str(
                Path(file_path)
                .resolve()
                .relative_to(
                    self.repository_path.resolve()
                )
            ).replace("\\", "/")

        except ValueError:

            return str(
                file_path
            ).replace("\\", "/")

    # =========================================
    # Combine Code + Git Metrics
    # =========================================

    def combine_metrics(
        self,
        code_metrics,
        git_metrics
    ):

        code_data = {}

        for item in code_metrics:

            relative_path = self.normalize_path(
                item["file"]
            )

            code_data[relative_path] = item

        git_data = {}

        for item in git_metrics:

            relative_path = self.normalize_path(
                item["file"]
            )

            git_data[relative_path] = item

        combined_rows = []

        common_files = (
            set(code_data.keys())
            &
            set(git_data.keys())
        )

        print(
            f"\nCommon files matched: "
            f"{len(common_files)}"
        )

        for file_path in sorted(
            common_files
        ):

            code = code_data[
                file_path
            ]

            git = git_data[
                file_path
            ]

            row = {

                "file":
                    file_path,

                "language":
                    code.get(
                        "language",
                        "Unknown"
                    ),

                "loc":
                    code.get(
                        "loc",
                        0
                    ),

                "complexity":
                    code.get(
                        "complexity",
                        0
                    ),

                "functions":
                    code.get(
                        "functions",
                        0
                    ),

                "classes":
                    code.get(
                        "classes",
                        0
                    ),

                "nesting_depth":
                    code.get(
                        "nesting_depth",
                        0
                    ),

                "comment_ratio":
                    code.get(
                        "comment_ratio",
                        0
                    ),

                "commit_count":
                    git.get(
                        "commit_count",
                        0
                    ),

                "contributors":
                    git.get(
                        "contributors",
                        0
                    ),

                "code_churn":
                    git.get(
                        "code_churn",
                        0
                    ),

                "bug_fix_commits":
                    git.get(
                        "bug_fix_commits",
                        0
                    ),

                "file_age_days":
                    git.get(
                        "file_age_days",
                        0
                    )
            }

            combined_rows.append(
                row
            )

        return pd.DataFrame(
            combined_rows
        )

    # =========================================
    # Create Bug Label
    # =========================================

    def create_bug_label(
        self,
        dataframe
    ):
        """Create the documented proxy defect label.

        A file is labelled 1 only when its Git history contains at least one
        commit whose message matches a bug-fix keyword.  This is a proxy for
        historical defect activity, not a confirmed defect label.
        """

        if dataframe.empty:

            return dataframe

        dataframe = dataframe.copy()

        dataframe["bug_fix_commits"] = pd.to_numeric(
            dataframe["bug_fix_commits"],
            errors="coerce"
        ).fillna(0)

        dataframe["bug_label"] = (
            dataframe["bug_fix_commits"] > 0
        ).astype(int)

        label_counts = dataframe["bug_label"].value_counts()

        print("\nDefect-label proxy distribution:")
        print(label_counts.to_string())
        print(
            "\nLabel rule: bug_fix_commits > 0 means "
            "historical bug-fix activity (label 1)."
        )

        return dataframe

    # =========================================
    # Prepare Dataset
    # =========================================

    def prepare_dataset(
        self,
        code_metrics,
        git_metrics
    ):

        dataframe = self.combine_metrics(
            code_metrics,
            git_metrics
        )

        if dataframe.empty:

            print(
                "\nNo common files found."
            )

            return dataframe

        dataframe = self.create_bug_label(
            dataframe
        )

        return dataframe

    # =========================================
    # Save Dataset
    # =========================================

    def save_dataset(
        self,
        dataframe,
        output_path
    ):

        output_path = project_path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        dataframe.to_csv(
            output_path,
            index=False
        )

        print(
            f"\nDataset saved to: "
            f"{output_path}"
        )
