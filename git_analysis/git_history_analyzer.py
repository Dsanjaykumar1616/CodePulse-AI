from datetime import datetime
from pathlib import Path

from git import Repo


class GitHistoryAnalyzer:
    """Aggregate per-file Git history using repository-level git log."""

    SUPPORTED_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".java"
    }

    IGNORED_DIRECTORIES = {
        ".git",
        "node_modules",
        "dist",
        "build",
        "venv",
        ".venv",
        "__pycache__",
        "coverage",
        ".cache",
    }

    BUG_KEYWORDS = (
        "bug",
        "fix",
        "fixed",
        "fixes",
        "error",
        "issue",
        "patch",
        "defect",
        "crash",
    )

    def __init__(
        self,
        repository_path,
        history_depth=None,
        commit_limit=None,
        source_files=None,
    ):
        self.repository_path = Path(repository_path).resolve()
        self.repo = Repo(self.repository_path)
        self.history_depth = history_depth
        self.commit_limit = commit_limit
        self._source_files = source_files

        self.history_commit_count = 0
        self.history_limited = bool(
            history_depth or commit_limit
        )

    def get_source_files(self):
        if self._source_files is not None:
            return [Path(path) for path in self._source_files]

        files = []

        for file_path in self.repository_path.rglob("*"):
            if not file_path.is_file():
                continue

            if any(
                directory in file_path.parts
                for directory in self.IGNORED_DIRECTORIES
            ):
                continue

            if file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                files.append(file_path)

        return files

    def get_relative_path(self, file_path):
        relative_path = (
            Path(file_path)
            .resolve()
            .relative_to(self.repository_path)
        )

        return str(relative_path).replace("\\", "/")

    @staticmethod
    def _empty_metric(relative_path):
        return {
            "file": relative_path,
            "commit_count": 0,
            "contributors": 0,
            "lines_added": 0,
            "lines_deleted": 0,
            "code_churn": 0,
            "bug_fix_commits": 0,
            "file_age_days": 0,
            "first_modified": None,
            "last_modified": None,
        }

    @staticmethod
    def _is_bug_fix(message):
        message = message.lower()

        return any(
            keyword in message
            for keyword in GitHistoryAnalyzer.BUG_KEYWORDS
        )

    @staticmethod
    def _normalize_git_path(path):
        """Normalize a path returned by git."""

        path = path.strip()

        # Remove surrounding quotes added by Git
        if len(path) >= 2 and path[0] == '"' and path[-1] == '"':
            path = path[1:-1]

        # Normalize separators
        path = path.replace("\\", "/")

        # Remove leading ./ if present
        while path.startswith("./"):
            path = path[2:]

        return path

    def _iter_history_numstat(self):
        """
        Read Git history using one repository-level git log command.

        This avoids GitPython commit.stats, which performs expensive
        per-commit diff operations.
        """

        max_count = self.commit_limit or self.history_depth

        args = [
            "--all",
            "--numstat",
            "--format=CODEPULSE_COMMIT%x00%H%x00%ct%x00%ae%x00%s",
        ]

        if max_count:
            args.extend([
                "-n",
                str(int(max_count)),
            ])

        output = self.repo.git.log(*args)

        current_commit = None

        for line in output.splitlines():

            # ---------------------------------------------------------
            # Commit header
            # ---------------------------------------------------------
            if line.startswith("CODEPULSE_COMMIT\x00"):

                if current_commit is not None:
                    yield current_commit

                parts = line.split("\x00", 4)

                if len(parts) != 5:
                    current_commit = None
                    continue

                _, sha, timestamp, email, subject = parts

                try:
                    commit_date = datetime.fromtimestamp(
                        int(timestamp)
                    )
                except (TypeError, ValueError):
                    current_commit = None
                    continue

                current_commit = {
                    "sha": sha,
                    "date": commit_date,
                    "email": email,
                    "message": subject,
                    "files": [],
                }

                self.history_commit_count += 1

                continue

            # ---------------------------------------------------------
            # Ignore lines before first commit
            # ---------------------------------------------------------
            if current_commit is None:
                continue

            if not line.strip():
                continue

            # ---------------------------------------------------------
            # Git numstat format:
            #
            # additions TAB deletions TAB filename
            # ---------------------------------------------------------
            parts = line.split("\t", 2)

            if len(parts) != 3:
                continue

            added, deleted, changed_path = parts

            try:
                insertions = (
                    int(added)
                    if added != "-"
                    else 0
                )
            except ValueError:
                insertions = 0

            try:
                deletions = (
                    int(deleted)
                    if deleted != "-"
                    else 0
                )
            except ValueError:
                deletions = 0

            changed_path = self._normalize_git_path(
                changed_path
            )

            current_commit["files"].append(
                (
                    changed_path,
                    insertions,
                    deletions,
                )
            )

        # -------------------------------------------------------------
        # Yield the final commit
        # -------------------------------------------------------------
        if current_commit is not None:
            yield current_commit

    def analyze_repository(self):
        source_files = self.get_source_files()

        source_paths = {
            self.get_relative_path(file_path)
            for file_path in source_files
        }

        if not source_paths:
            return []

        aggregates = {
            relative_path: {
                "contributors": set(),
                "first_modified": None,
                "last_modified": None,
                "commit_count": 0,
                "lines_added": 0,
                "lines_deleted": 0,
                "bug_fix_commits": 0,
            }
            for relative_path in source_paths
        }

        print(
            f"\nFound {len(source_paths)} source files for Git analysis."
        )

        # -------------------------------------------------------------
        # Repository-level history traversal
        # -------------------------------------------------------------
        for commit in self._iter_history_numstat():

            commit_date = commit["date"]

            bug_fix = self._is_bug_fix(
                commit["message"]
            )

            author_email = commit["email"]

            for changed_path, insertions, deletions in commit["files"]:

                # Normalize one more time before matching
                changed_path = self._normalize_git_path(
                    changed_path
                )

                if changed_path not in aggregates:
                    continue

                aggregate = aggregates[changed_path]

                aggregate["commit_count"] += 1

                if author_email:
                    aggregate["contributors"].add(
                        author_email
                    )

                if (
                    aggregate["first_modified"] is None
                    or commit_date
                    < aggregate["first_modified"]
                ):
                    aggregate["first_modified"] = commit_date

                if (
                    aggregate["last_modified"] is None
                    or commit_date
                    > aggregate["last_modified"]
                ):
                    aggregate["last_modified"] = commit_date

                if bug_fix:
                    aggregate["bug_fix_commits"] += 1

                aggregate["lines_added"] += insertions
                aggregate["lines_deleted"] += deletions

        # -------------------------------------------------------------
        # Create final output
        # -------------------------------------------------------------
        results = []

        for relative_path in sorted(source_paths):

            aggregate = aggregates[relative_path]

            first_modified = aggregate["first_modified"]

            file_age_days = 0

            if first_modified is not None:
                now = datetime.now(
                    first_modified.tzinfo
                )

                file_age_days = (
                    now - first_modified
                ).days

            results.append(
                {
                    "file": relative_path,

                    "commit_count": (
                        aggregate["commit_count"]
                    ),

                    "contributors": len(
                        aggregate["contributors"]
                    ),

                    "lines_added": (
                        aggregate["lines_added"]
                    ),

                    "lines_deleted": (
                        aggregate["lines_deleted"]
                    ),

                    "code_churn": (
                        aggregate["lines_added"]
                        + aggregate["lines_deleted"]
                    ),

                    "bug_fix_commits": (
                        aggregate["bug_fix_commits"]
                    ),

                    "file_age_days": file_age_days,

                    "first_modified": (
                        first_modified.isoformat()
                        if first_modified
                        else None
                    ),

                    "last_modified": (
                        aggregate["last_modified"].isoformat()
                        if aggregate["last_modified"]
                        else None
                    ),

                    "history_commit_count": (
                        self.history_commit_count
                    ),

                    "history_limited": (
                        self.history_limited
                    ),
                }
            )

        return results

    def analyze_file_history(self, relative_path):
        """Return history metrics for one file."""

        normalized = self._normalize_git_path(
            relative_path
        )

        results = self.analyze_repository()

        for result in results:
            if result["file"] == normalized:
                return result

        return {
            **self._empty_metric(normalized),
            "history_commit_count": (
                self.history_commit_count
            ),
            "history_limited": (
                self.history_limited
            ),
        }