import os
from pathlib import Path

from git import Repo

from codepulse_runtime import PROJECT_ROOT, repository_identity


class RepositoryAnalyzer:

    # Supported file extensions
    SUPPORTED_EXTENSIONS = {

        ".py": "Python",

        ".js": "JavaScript",

        ".ts": "TypeScript",

        ".jsx": "React",

        ".tsx": "React",

        ".html": "HTML",

        ".css": "CSS",

        ".java": "Java"
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
        ".cache"
    }

    def __init__(
        self,
        repo_url,
        clone_directory=None
    ):

        self.repo_url = repo_url

        self.clone_directory = str(
            Path(clone_directory) if clone_directory else PROJECT_ROOT / "data" / "repositories"
        )

        os.makedirs(
            self.clone_directory,
            exist_ok=True
        )

        # Get repository name (handles Windows paths, trailing slashes, and URLs)
        raw_name = (
            repo_url
            .strip()
            .rstrip("/\\")
            .replace("\\", "/")
            .split("/")[-1]
        )

        # Remove .git
        if raw_name.endswith(".git"):

            raw_name = raw_name[:-4]

        identity = repository_identity(repo_url)
        self.repo_name = identity["repository_name"] or raw_name
        self.repository_key = identity["key"]

        self.repo_path = os.path.join(
            self.clone_directory,
            self.repository_key
        )

        # Reuse the pre-hash layout only when its Git remote proves identity.
        # A same-name directory from another owner is never accepted.
        legacy_path = os.path.join(self.clone_directory, raw_name)
        if not os.path.exists(self.repo_path) and os.path.isdir(legacy_path):
            try:
                legacy_repo = Repo(legacy_path)
                expected = identity["canonical_url"]
                remote_urls = [
                    remote.url.rstrip("/").removesuffix(".git").lower()
                    for remote in legacy_repo.remotes
                ]
                if expected in remote_urls:
                    self.repo_path = legacy_path
            except (OSError, ValueError):
                pass

    # =========================================
    # Clone Repository
    # =========================================

    def clone_repository(self):

        if os.path.exists(
            self.repo_path
        ):

            try:
                existing = Repo(self.repo_path)
                remote_urls = [
                    remote.url.rstrip("/").removesuffix(".git").lower()
                    for remote in existing.remotes
                ]
                expected = repository_identity(self.repo_url)["canonical_url"]
                if expected not in remote_urls:
                    raise ValueError("local directory belongs to another repository")
                print("Repository already exists.")
            except (ValueError, OSError):
                raise RuntimeError(
                    f"Repository path collision detected: {self.repo_path}"
                )

            return

        print(
            f"Cloning repository: "
            f"{self.repo_url}"
        )

        Repo.clone_from(
            self.repo_url,
            self.repo_path
        )

        print(
            "Repository cloned successfully."
        )

    # =========================================
    # Detect Languages
    # =========================================

    def detect_languages(self):

        language_counts = {}

        total_files = 0

        unsupported_files = 0

        for root, dirs, files in os.walk(
            self.repo_path
        ):

            # Prune ignored directories in place
            dirs[:] = [
                d for d in dirs
                if d not in self.IGNORED_DIRECTORIES
            ]

            for file in files:

                total_files += 1

                extension = (
                    os.path.splitext(file)[1]
                    .lower()
                )

                if extension in (
                    self.SUPPORTED_EXTENSIONS
                ):

                    language = (
                        self.SUPPORTED_EXTENSIONS[
                            extension
                        ]
                    )

                    if language not in (
                        language_counts
                    ):

                        language_counts[
                            language
                        ] = 0

                    language_counts[
                        language
                    ] += 1

                else:

                    unsupported_files += 1

        return (
            total_files,
            language_counts,
            unsupported_files
        )

    # =========================================
    # Get Git Information
    # =========================================

    def get_git_information(self):

        repo = Repo(
            self.repo_path
        )

        contributors = set()
        commit_count = 0

        for commit in repo.iter_commits():

            commit_count += 1

            if commit.author.email:

                contributors.add(
                    commit.author.email
                )

        return {

            "commits":
                commit_count,

            "contributors":
                len(contributors)
        }

    # =========================================
    # Complete Analysis
    # =========================================

    def analyze(self):

        # Clone repository
        self.clone_repository()

        # Detect languages
        (
            total_files,
            language_counts,
            unsupported_files
        ) = self.detect_languages()

        # Git information
        git_info = (
            self.get_git_information()
        )

        return {

            "repository_name":
                self.repo_name,

            "repository_url":
                self.repo_url,

            "repository_path":
                self.repo_path,

            "total_files":
                total_files,

            "languages":
                language_counts,

            "unsupported_files":
                unsupported_files,

            "commits":
                git_info[
                    "commits"
                ],

            "contributors":
                git_info[
                    "contributors"
                ]
        }