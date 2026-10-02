"""Strict validation of user-supplied GitHub repository URLs."""

from __future__ import annotations

import re
from dataclasses import dataclass

_NAME = r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,99})"
_PATTERNS = (
    re.compile(rf"^https?://(?:www\.)?github\.com/(?P<owner>{_NAME})/(?P<repo>{_NAME})(?:\.git)?/?$"),
    re.compile(rf"^(?:www\.)?github\.com/(?P<owner>{_NAME})/(?P<repo>{_NAME})(?:\.git)?/?$"),
    re.compile(rf"^git@github\.com:(?P<owner>{_NAME})/(?P<repo>{_NAME})(?:\.git)?$"),
    re.compile(rf"^(?P<owner>{_NAME})/(?P<repo>{_NAME})$"),
)


class InvalidRepositoryUrl(ValueError):
    pass


@dataclass(frozen=True)
class GitHubRepo:
    owner: str
    name: str

    @property
    def canonical_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.name}".lower()

    @property
    def clone_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.name}"


def parse_github_url(value: str) -> GitHubRepo:
    text = (value or "").strip()
    # Accept links copied from a sub-page (e.g. /tree/main) by trimming them.
    text = re.sub(r"(github\.com/[^/\s]+/[^/\s]+)/(?:tree|blob|issues|pulls|wiki)(?:/.*)?$", r"\1", text)
    for pattern in _PATTERNS:
        match = pattern.match(text)
        if match:
            owner = match.group("owner")
            repo = match.group("repo")
            if repo.endswith(".git"):
                repo = repo[:-4]
            if not repo or repo in {".", ".."} or owner in {".", ".."}:
                break
            return GitHubRepo(owner=owner, name=repo)
    raise InvalidRepositoryUrl(
        "Enter a GitHub repository URL such as https://github.com/psf/requests"
    )
