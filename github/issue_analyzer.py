import os
import re
from urllib.parse import urlparse

import requests

# On Windows, use the operating system certificate store when available.
# This keeps HTTPS certificate verification enabled for GitHub API requests.
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass


class GitHubIssueAnalyzer:
    """Retrieve public GitHub issues and match them to a selected source file.

    Matching is intentionally conservative and explainable. It uses only
    issue title/body text and does not claim that a matching issue confirms a
    bug in the selected file.
    """

    API_URL = "https://api.github.com/repos/{owner}/{repository}/issues"

    def __init__(self, repository_url):
        self.repository_url = repository_url
        self.owner, self.repository = self.parse_repository_url(repository_url)

    @staticmethod
    def parse_repository_url(repository_url):
        if not repository_url or not isinstance(repository_url, str):
            return None, None

        url = repository_url.strip().rstrip("/\\")

        if url.startswith("git@github.com:"):
            path = url.split(":", 1)[1]
        else:
            if not url.startswith("http://") and not url.startswith("https://"):
                if url.startswith("github.com/"):
                    url = "https://" + url
                elif "/" in url and len(url.split("/")) == 2:
                    parts = url.removesuffix(".git").split("/")
                    if parts[0] and parts[1]:
                        return parts[0], parts[1]
                    return None, None
                else:
                    url = "https://" + url

            parsed = urlparse(url)
            if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
                return None, None
            path = parsed.path.lstrip("/")

        parts = path.removesuffix(".git").split("/")
        if len(parts) < 2 or not parts[0] or not parts[1]:
            return None, None

        return parts[0], parts[1]

    def fetch_issues(self):
        if not self.owner or not self.repository:
            return {
                "available": False,
                "message": "GitHub issue analysis unavailable: invalid GitHub repository URL.",
                "issues": [],
            }

        headers = {"Accept": "application/vnd.github+json"}
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = requests.get(
                self.API_URL.format(owner=self.owner, repository=self.repository),
                headers=headers,
                params={"state": "all", "per_page": 100},
                timeout=15,
            )
        except requests.RequestException:
            return {
                "available": False,
                "message": "GitHub issue analysis unavailable.",
                "issues": [],
            }

        if response.status_code == 404:
            message = "GitHub issue analysis unavailable: repository is missing or private."
        elif response.status_code in {401, 403}:
            message = "GitHub issue analysis unavailable: API access or rate limit reached."
        elif not response.ok:
            message = "GitHub issue analysis unavailable."
        else:
            # GitHub returns pull requests from this endpoint; exclude them.
            issues = [
                issue for issue in response.json()
                if isinstance(issue, dict) and "pull_request" not in issue
            ]
            return {
                "available": True,
                "message": None,
                "issues": issues,
            }

        return {"available": False, "message": message, "issues": []}

    @staticmethod
    def _keywords(file_path):
        raw_parts = re.split(r"[/.\\_-]+", file_path)
        keywords = set()
        ignored = {
            "src", "app", "backend", "frontend", "controllers", "controller",
            "models", "model", "routes", "route", "services", "service",
            "components", "component", "utils", "index", "lib", "main",
            "test", "tests", "spec", "specs", "py", "js", "ts", "jsx",
            "tsx", "html", "css", "java", "json", "md", "txt", "yml", "yaml",
        }

        for part in raw_parts:
            # Split camelCase, PascalCase, and numeric boundaries
            for word in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\d+", part):
                normalized = word.lower()
                if len(normalized) >= 4 and normalized not in ignored:
                    keywords.add(normalized)

        return keywords

    def match_issues(self, file_path, issues):
        normalized_path = file_path.replace("\\", "/").lower()
        file_name = normalized_path.rsplit("/", 1)[-1]
        file_stem = file_name.rsplit(".", 1)[0]
        keywords = self._keywords(file_path)
        matches = []

        # Directory / component names
        path_components = [
            comp.lower() for comp in normalized_path.split("/")[:-1]
            if comp and comp not in {"src", "app", "lib", "pkg"}
        ]

        for issue in issues:
            title = issue.get("title") or ""
            body = issue.get("body") or ""
            title_lower = title.lower()
            body_lower = body.lower()
            text = f"{title_lower}\n{body_lower}"
            score = 0
            evidence = []

            # 1. Full file path match
            if normalized_path in text:
                score += 8
                if normalized_path in title_lower:
                    evidence.append("File path found in issue title")
                else:
                    evidence.append("File path found in issue body")
            # 2. Exact file name match
            elif file_name in text:
                score += 6
                if file_name in title_lower:
                    score += 2
                    evidence.append("File name found in issue title")
                else:
                    evidence.append("File name found in issue body")
            # 3. File stem / class / module name match
            elif len(file_stem) >= 4:
                stem_pattern = rf"\b{re.escape(file_stem)}\b"
                if re.search(stem_pattern, title_lower):
                    score += 6
                    evidence.append("File/module name found in issue title")
                elif re.search(stem_pattern, body_lower):
                    score += 4
                    evidence.append("File/module name found in issue body")

            # 4. Component / directory name match
            matched_components = []
            for comp in path_components:
                if len(comp) >= 4 and re.search(rf"\b{re.escape(comp)}\b", text):
                    matched_components.append(comp)
            if matched_components:
                score += min(len(matched_components) * 2, 4)
                evidence.append(
                    "Repository component keyword: " + ", ".join(matched_components)
                )

            # 5. File/module domain keywords match
            matched_keywords = []
            for keyword in sorted(keywords):
                if re.search(rf"\b{re.escape(keyword)}\b", text):
                    matched_keywords.append(keyword)
            if matched_keywords:
                score += min(len(matched_keywords) * 2, 6)
                evidence.append(
                    "Matching module keywords: " + ", ".join(matched_keywords[:3])
                )

            # Relevance assignment
            if score >= 6:
                relevance = "HIGH"
            elif score >= 3:
                relevance = "MEDIUM"
            else:
                continue

            matches.append({
                "number": issue.get("number"),
                "title": title,
                "body": body,
                "state": (issue.get("state") or "UNKNOWN").upper(),
                "labels": [
                    label.get("name", "") if isinstance(label, dict) else str(label)
                    for label in issue.get("labels", [])
                ],
                "created_at": issue.get("created_at"),
                "updated_at": issue.get("updated_at"),
                "url": issue.get("html_url"),
                "author": (issue.get("user") or {}).get("login", "unknown"),
                "relevance": relevance,
                "score": score,
                "evidence": evidence,
            })

        return sorted(matches, key=lambda item: item["score"], reverse=True)

    def analyze_file(self, file_path):
        result = self.fetch_issues()
        if not result["available"]:
            return {**result, "matches": []}

        matches = self.match_issues(file_path, result["issues"])
        return {**result, "matches": matches}

    @staticmethod
    def print_report(file_path, issue_report, risk_level=None):
        print("\n==========================================")
        print("          RELATED GITHUB ISSUES")
        print("==========================================")
        print(f"File:\n{file_path}")
        if risk_level:
            print(f"\nRisk:\n{str(risk_level).upper()}")

        if not issue_report["available"]:
            print(f"\n{issue_report['message']}")
            print("CodePulse analysis continues without issue information.")
            print("==========================================")
            return

        matches = issue_report["matches"]
        if not matches:
            print("\nNo strongly related GitHub issues were found by CodePulse.")
            print("==========================================")
            return

        print("\nRelated Issues:\n")
        for issue in matches[:5]:
            labels = ", ".join(issue["labels"]) or "None"
            print(f"#{issue['number']}")
            print(f"{issue['title']}")
            print(f"Status: {issue['state']}")
            print(f"Labels: {labels}")
            print(f"Relevance: {issue['relevance']}")
            if issue.get("evidence"):
                print("Match Evidence:")
                for item in issue["evidence"]:
                    print(f"  ✓ {item}")
            if issue.get("url"):
                print(f"URL: {issue['url']}")
            print()

        print("==========================================")
        print("Recommendation:")
        open_matches = [issue for issue in matches if issue.get("state") == "OPEN"]
        closed_matches = [issue for issue in matches if issue.get("state") == "CLOSED"]
        unknown_matches = [
            issue for issue in matches
            if issue.get("state") not in {"OPEN", "CLOSED"}
        ]

        if open_matches:
            print("\nOpen related issues may be potential contribution opportunities.")
            print("Review their scope and contribution guidelines before working on them.")
            print("Possible contribution: review and work on an appropriate open issue.")
        if closed_matches:
            print("\nClosed related issues are shown as historical context only.")
        if unknown_matches:
            print("\nSome related issue states are unknown; verify their current status on GitHub.")
        if not open_matches:
            print("\nNo open related issue is available for an automatic contribution recommendation.")
        print("==========================================")
