"""Contributor guidance derived from stored analysis results.

Everything here is computed from sections the analysis engine already
produced (file metrics, dependency graph, opportunities, issues, review
findings). Nothing here analyses source code again, and nothing is invented:

* "Detected" items come straight from engine output (for example a static
  import from a test file to the target file).
* "Heuristic" items come from simple, documented rules over that output
  (for example a test file whose name matches the target file's name).
  They are always labelled as heuristic in the response.

The only engine code reused directly is ContributionOpportunityGenerator's
threshold and difficulty functions, so the difficulty explanation uses the
exact rule that produced the difficulty.
"""

from __future__ import annotations

import posixpath
import re
from collections import Counter, defaultdict
from typing import Any, Iterable

from app.services.engine_runner import ENGINE_ROOT  # noqa: F401  (puts the engine on sys.path)

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs", "testing"}
ENTRY_NAMES = {
    "main.py", "__main__.py", "app.py", "cli.py", "manage.py", "wsgi.py", "asgi.py", "server.py", "run.py",
    "index.js", "index.ts", "index.jsx", "index.tsx", "main.js", "main.ts", "main.jsx", "main.tsx",
    "app.js", "app.ts", "app.jsx", "app.tsx", "server.js", "server.ts", "cli.js", "cli.ts",
    "index.html", "Main.java", "Application.java", "App.java",
}

# Directory names with a widely used conventional meaning. The label is only a
# hint taken from the name and is always presented as such.
DIRECTORY_HINTS = {
    "Tests": {"test", "tests", "__tests__", "spec", "specs", "testing"},
    "Documentation": {"doc", "docs", "documentation"},
    "Examples": {"example", "examples", "sample", "samples", "demo", "demos"},
    "Scripts and tools": {"script", "scripts", "bin", "tools", "tooling"},
    "Configuration": {"config", "configs", "conf", "settings"},
    "Shared utilities": {"util", "utils", "helper", "helpers", "common", "shared", "lib", "libs"},
    "API and request handling": {"api", "apis", "routes", "router", "routers", "controllers", "handlers", "views", "endpoints"},
    "Data models": {"model", "models", "schema", "schemas", "entities", "domain"},
    "Services": {"service", "services"},
    "UI components": {"component", "components", "pages", "ui", "widgets", "layouts", "templates"},
    "Styles": {"css", "styles", "style", "scss", "sass"},
    "Database": {"db", "database", "migrations", "migration"},
    "Static assets": {"static", "public", "assets"},
}
_HINT_BY_NAME = {name: label for label, names in DIRECTORY_HINTS.items() for name in names}


def _quantile(values: Iterable[float], q: float) -> float:
    """Linear-interpolation quantile (the same method as pandas' default)."""
    data = sorted(float(v) for v in values)
    if not data:
        return 0.0
    position = (len(data) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(data) - 1)
    return data[lower] + (data[upper] - data[lower]) * (position - lower)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def directory_of(path: str) -> str:
    return posixpath.dirname(path) or "(root)"


def is_test_file(path: str) -> bool:
    original = path.split("/")[-1]
    parts = path.lower().split("/")
    name = parts[-1]
    if any(part in TEST_DIRS for part in parts[:-1]):
        return True
    stem = name.rsplit(".", 1)[0]
    original_stem = original.rsplit(".", 1)[0]
    return (
        stem.startswith("test_")
        or stem.endswith("_test")
        or stem.endswith("_tests")
        or ".test" in name
        or ".spec" in name
        or (name.endswith(".java") and (original_stem.endswith("Test") or original_stem.endswith("Tests")))
    )


def _stem(path: str) -> str:
    name = posixpath.basename(path)
    name = re.sub(r"\.(test|spec)(?=\.[^.]+$)", "", name)
    stem = name.rsplit(".", 1)[0]
    for prefix in ("test_",):
        if stem.lower().startswith(prefix):
            stem = stem[len(prefix):]
    for suffix in ("_tests", "_test", "Tests", "Test"):
        if stem.endswith(suffix) and len(stem) > len(suffix):
            stem = stem[: -len(suffix)]
            break
    return stem.lower()


# ---------------------------------------------------------------------------
# Graph facts
# ---------------------------------------------------------------------------

class Graph:
    """Adjacency built from the stored architecture section."""

    def __init__(self, architecture: dict | None):
        architecture = architecture or {}
        self.available = bool(architecture.get("available"))
        self.nodes: dict[str, dict] = {node["id"]: node for node in architecture.get("nodes", [])}
        self.depends_on: dict[str, set[str]] = defaultdict(set)
        self.used_by: dict[str, set[str]] = defaultdict(set)
        for edge in architecture.get("edges", []):
            self.depends_on[edge["source"]].add(edge["target"])
            self.used_by[edge["target"]].add(edge["source"])
        self.unresolved = {item["file"]: item.get("imports", []) for item in architecture.get("unresolved", [])}
        totals = [node.get("total", 0) for node in self.nodes.values()]
        incoming = [node.get("incoming", 0) for node in self.nodes.values()]
        self.total_p90 = _quantile(totals, 0.9)
        self.incoming_p90 = _quantile(incoming, 0.9)
        self.max_total = max(totals, default=0)


def connectivity_label(total: int, graph: Graph) -> str:
    if total == 0:
        return "No local dependencies detected"
    if total >= max(3, graph.total_p90):
        return "Highly connected"
    if total >= 2:
        return "Moderately connected"
    return "Low connectivity"


def file_roles(path: str, graph: Graph) -> list[dict]:
    """Structural roles with the evidence for each. All are estimates."""
    node = graph.nodes.get(path)
    roles: list[dict] = []
    name = posixpath.basename(path)
    incoming = node.get("incoming", 0) if node else 0
    outgoing = node.get("outgoing", 0) if node else 0
    if is_test_file(path):
        roles.append({"role": "Test file", "basis": "Located in a test directory or named like a test file."})
    if not is_test_file(path):
        if name in ENTRY_NAMES:
            roles.append({"role": "Possible entry point", "basis": f"Named {name}, a common entry-point file name."})
        elif node and incoming == 0 and outgoing >= 2:
            roles.append({
                "role": "Possible entry point",
                "basis": f"Imports {outgoing} local files but no local file imports it.",
            })
    if node and incoming >= max(3, graph.incoming_p90):
        roles.append({"role": "Core dependency", "basis": f"Imported by {incoming} local files."})
    if node and node.get("total", 0) >= max(3, graph.total_p90):
        roles.append({
            "role": "Highly connected",
            "basis": f"{node['total']} direct dependency relationships, among the most in this repository.",
        })
    if node and node.get("total", 0) == 0:
        roles.append({"role": "Isolated", "basis": "No static import relationships with other repository files were found."})
    return roles


# ---------------------------------------------------------------------------
# Directory groups (architecture level 1)
# ---------------------------------------------------------------------------

def _group_key(path: str, depth: int) -> str:
    parts = path.split("/")[:-1]
    if not parts:
        return "(root)"
    return "/".join(parts[:depth])


def choose_group_depth(paths: list[str]) -> int:
    """Group by top-level directory, going one level deeper while one
    directory holds most of the files (e.g. everything lives under src/)."""
    depth = 1
    for _ in range(3):
        counts = Counter(_group_key(path, depth) for path in paths)
        if not counts:
            return depth
        largest, size = counts.most_common(1)[0]
        deeper = {_group_key(path, depth + 1) for path in paths if _group_key(path, depth) == largest}
        if size / len(paths) > 0.7 and len(deeper) > 1 and largest != "(root)":
            depth += 1
        else:
            break
    return depth


def directory_groups(file_rows: list[dict], graph: Graph, opportunities: list[dict]) -> dict:
    paths = [row["file"] for row in file_rows]
    depth = choose_group_depth(paths)
    rows_by_file = {row["file"]: row for row in file_rows}
    opp_files = {item["file"]: item for item in opportunities}
    members: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        members[_group_key(path, depth)].append(path)
    group_of = {path: key for key, files in members.items() for path in files}

    edge_counts: Counter = Counter()
    for source, targets in graph.depends_on.items():
        for target in targets:
            a, b = group_of.get(source), group_of.get(target)
            if a and b and a != b:
                edge_counts[(a, b)] += 1

    groups = []
    for key, files in members.items():
        rows = [rows_by_file[path] for path in files]
        name = key.rsplit("/", 1)[-1].lower()
        hint = _HINT_BY_NAME.get(name)
        test_share = sum(1 for path in files if is_test_file(path)) / len(files)
        if test_share >= 0.8:
            hint = "Tests"
        incoming = sum(count for (a, b), count in edge_counts.items() if b == key)
        outgoing = sum(count for (a, b), count in edge_counts.items() if a == key)
        internal = sum(
            1 for source in files for target in graph.depends_on.get(source, set()) if group_of.get(target) == key
        )
        if incoming == 0 and outgoing == 0 and internal == 0:
            structure = "No local dependencies detected"
        elif incoming >= max(2, 2 * outgoing):
            structure = "Mostly used by other directories"
        elif outgoing >= max(2, 2 * incoming):
            structure = "Mostly depends on other directories"
        elif incoming or outgoing:
            structure = "Both uses and is used by other directories"
        else:
            structure = "Self-contained (dependencies stay inside this directory)"
        languages = Counter(row.get("language") or "Other" for row in rows)
        key_files = sorted(
            files,
            key=lambda path: (-(graph.nodes.get(path, {}).get("total", 0)), path),
        )[:5]
        groups.append({
            "id": key,
            "label": key,
            "name_hint": hint,
            "structure": structure,
            "file_count": len(files),
            "test_files": sum(1 for path in files if is_test_file(path)),
            "loc": int(sum(_num(row.get("loc")) for row in rows)),
            "languages": dict(languages.most_common()),
            "high_risk_files": sum(1 for row in rows if (row.get("risk_level") or "") in ("High", "Critical")),
            "high_debt_files": sum(1 for row in rows if (row.get("debt_level") or "") in ("HIGH", "CRITICAL")),
            "opportunities": sum(1 for path in files if path in opp_files),
            "incoming": incoming,
            "outgoing": outgoing,
            "internal_dependencies": internal,
            "key_files": [
                {
                    "file": path,
                    "total": graph.nodes.get(path, {}).get("total", 0),
                    "roles": [role["role"] for role in file_roles(path, graph)],
                }
                for path in key_files
            ],
        })
    groups.sort(key=lambda group: (-(group["incoming"] + group["outgoing"] + group["internal_dependencies"]), -group["file_count"], group["id"]))
    return {
        "depth": depth,
        "groups": groups,
        "edges": [
            {"source": a, "target": b, "count": count}
            for (a, b), count in sorted(edge_counts.items(), key=lambda item: -item[1])
        ],
        "basis": (
            "Groups are directories. Name hints come from common directory names only; "
            "relationships are counted from static imports between files."
        ),
    }


# ---------------------------------------------------------------------------
# Start here, roadmap, repository facts
# ---------------------------------------------------------------------------

def start_here(graph: Graph, file_rows: list[dict], limit: int = 6) -> list[dict]:
    if not graph.available:
        return []
    picks: list[dict] = []
    seen: set[str] = set()

    def add(path: str, label: str, reason: str):
        if path in seen or len(picks) >= limit:
            return
        seen.add(path)
        picks.append({"file": path, "label": label, "reason": reason})

    candidates = [path for path in graph.nodes if not is_test_file(path)]
    entries = [
        path for path in candidates
        if any(role["role"] == "Possible entry point" for role in file_roles(path, graph))
    ]
    entries.sort(key=lambda path: (-graph.nodes[path].get("outgoing", 0), path))
    for path in entries[:2]:
        node = graph.nodes[path]
        basis = next(role["basis"] for role in file_roles(path, graph) if role["role"] == "Possible entry point")
        outgoing = node.get("outgoing", 0)
        extra = f" It imports {outgoing} local files, so reading it shows how parts of the project are wired together." if outgoing else ""
        add(path, "Possible entry point", basis + extra)

    core = sorted(candidates, key=lambda path: (-graph.nodes[path].get("incoming", 0), path))
    for path in core[:3]:
        incoming = graph.nodes[path].get("incoming", 0)
        if incoming >= 2:
            add(path, "Core dependency", f"Imported by {incoming} local files, so much of the code builds on it.")

    central = sorted(candidates, key=lambda path: (-graph.nodes[path].get("total", 0), path))
    for path in central[:3]:
        total = graph.nodes[path].get("total", 0)
        if total >= 2:
            add(path, "Highly connected module", f"{total} direct dependency relationships connect it to the rest of the code.")
    return picks


def roadmap(opportunities: list[dict], per_level: int = 3) -> dict:
    result = {}
    for level in ("BEGINNER", "INTERMEDIATE", "ADVANCED"):
        items = [item for item in opportunities if item.get("difficulty") == level]
        result[level] = [
            {
                "file": item["file"],
                "title": item.get("title"),
                "opportunity_score": item.get("opportunity_score"),
                "open_issue_count": item.get("open_issue_count", 0),
            }
            for item in items[:per_level]
        ]
        result[f"{level}_total"] = len(items)
    return result


# ---------------------------------------------------------------------------
# Tests, readiness, why-this-file, difficulty basis, change impact
# ---------------------------------------------------------------------------

def related_tests(path: str, all_files: list[str], graph: Graph) -> dict:
    tests = [candidate for candidate in all_files if is_test_file(candidate) and candidate != path]
    if not tests:
        return {
            "available": False,
            "detected": [],
            "heuristic": [],
            "reason": "No test files were identified among the analyzed files.",
        }
    if is_test_file(path):
        return {
            "available": True,
            "detected": [],
            "heuristic": [],
            "reason": "This file is itself a test file.",
        }
    detected = sorted(test for test in tests if path in graph.depends_on.get(test, set()))
    stem = _stem(path)
    heuristic = sorted(
        test for test in tests
        if test not in detected and len(stem) >= 3 and _stem(test) == stem
    )
    return {
        "available": True,
        "detected": [{"file": test, "basis": "This test file imports the selected file (static import)."} for test in detected],
        "heuristic": [{"file": test, "basis": f"Test file name matches “{posixpath.basename(path)}”."} for test in heuristic],
        "reason": None if detected or heuristic else "No test file imports this file or matches its name.",
    }


def readiness(doc: dict, tests: dict, issues_available: bool) -> list[dict]:
    """Evidence checklist. There is deliberately no combined score."""
    issues = doc.get("issues") or []
    open_issues = [issue for issue in issues if str(issue.get("state", "")).upper() == "OPEN"]
    history = doc.get("history") or {}
    impact = doc.get("impact") or {}
    related = doc.get("related_files") or []
    findings = doc.get("review_findings") or []
    test_count = len(tests.get("detected", [])) + len(tests.get("heuristic", []))

    def item(key, ok, label_ok, label_missing, state_missing="missing"):
        return {"key": key, "status": "ok" if ok else state_missing, "label": label_ok if ok else label_missing}

    return [
        item(
            "issue",
            bool(open_issues),
            f"Related open issue found (#{open_issues[0].get('number')})" if open_issues else "",
            "No related open issue was identified" if issues_available else "GitHub issue data unavailable for this analysis",
            "missing" if issues_available else "unavailable",
        ),
        item(
            "history",
            _num(history.get("commit_count")) > 0,
            f"Git history available ({int(_num(history.get('commit_count')))} commits)",
            "No Git history was recorded for this file",
        ),
        item(
            "related",
            bool(related),
            f"Related files identified ({len(related)})",
            "No related files found through static imports",
        ),
        item(
            "impact",
            bool(impact.get("available")),
            f"Dependency impact available ({impact.get('impact_level', '').title()})",
            "Dependency impact not available",
            "unavailable",
        ),
        item(
            "review",
            bool(findings),
            f"Review findings available ({len(findings)})",
            "No review findings for this file",
        ),
        item(
            "tests",
            test_count > 0,
            f"Potentially related tests found ({test_count})",
            "Test relationship not identified" if tests.get("available") else "No test files found in the analyzed code",
            "missing" if tests.get("available") else "unavailable",
        ),
    ]


class Thresholds:
    """Repository-relative thresholds, computed exactly as the engine does."""

    def __init__(self, file_rows: list[dict]):
        try:
            import pandas as pd
            from analysis.contribution_opportunities import ContributionOpportunityGenerator as Generator

            self.generator = Generator()
            frame = pd.DataFrame(file_rows) if file_rows else pd.DataFrame(columns=["complexity", "code_churn", "loc"])
            threshold = Generator._threshold
            self.complexity_75 = threshold(frame.get("complexity", pd.Series(dtype=float)), 0.75)
            self.complexity_50 = threshold(frame.get("complexity", pd.Series(dtype=float)), 0.50)
            self.churn_75 = threshold(frame.get("code_churn", pd.Series(dtype=float)), 0.75)
            self.churn_50 = threshold(frame.get("code_churn", pd.Series(dtype=float)), 0.50)
            self.loc_75 = threshold(frame.get("loc", pd.Series(dtype=float)), 0.75)
            self.loc_50 = threshold(frame.get("loc", pd.Series(dtype=float)), 0.50)
        except ImportError:  # pragma: no cover - engine always present in deployments
            self.generator = None
            values = lambda key: [_num(row.get(key)) for row in file_rows]  # noqa: E731
            self.complexity_75 = _quantile(values("complexity"), 0.75)
            self.complexity_50 = _quantile(values("complexity"), 0.50)
            self.churn_75 = _quantile(values("code_churn"), 0.75)
            self.churn_50 = _quantile(values("code_churn"), 0.50)
            self.loc_75 = _quantile(values("loc"), 0.75)
            self.loc_50 = _quantile(values("loc"), 0.50)


def difficulty_basis(row: dict, opportunity: dict | None, graph: Graph, thresholds: Thresholds) -> dict | None:
    """Which of the engine's difficulty conditions apply to this file."""
    if row is None:
        return None
    node = graph.nodes.get(row["file"], {})
    total = node.get("total", 0)
    incoming = node.get("incoming", 0)
    impact = (
        "CRITICAL" if incoming >= 8 or total >= 12 else
        "HIGH" if incoming >= 4 or total >= 6 else
        "MEDIUM" if incoming >= 2 or total >= 3 else "LOW"
    ) if graph.available and node else ""
    complexity = _num(row.get("complexity"))
    churn = _num(row.get("code_churn"))
    loc = _num(row.get("loc"))
    bug_fixes = int(_num(row.get("bug_fix_commits")))
    probability = _num(row.get("risk_probability"))
    nesting = int(_num(row.get("nesting_depth")))
    t = thresholds

    advanced = [
        (complexity >= t.complexity_75 and complexity >= 30, f"Complexity {complexity:.0f} is in the top quarter and at least 30"),
        (complexity >= t.complexity_50 and churn >= t.churn_75, f"Above-median complexity ({complexity:.0f}) with top-quarter churn ({churn:.0f})"),
        (probability >= 0.75 and (complexity >= t.complexity_50 or churn >= t.churn_50), f"Historical risk signal {probability:.0%} with above-median complexity or churn"),
        (loc >= t.loc_75 and complexity >= t.complexity_75, f"Large file ({loc:.0f} lines) with top-quarter complexity"),
        (bug_fixes >= 20, f"{bug_fixes} historical bug-fix commits (20 or more)"),
        (impact in {"CRITICAL", "HIGH"}, f"{impact.title()} dependency impact ({total} direct relationships, used by {incoming})"),
        (total >= 6, f"{total} related files through static imports (6 or more)"),
    ]
    intermediate = [
        (complexity >= t.complexity_50, f"Complexity {complexity:.0f} is at or above the repository median ({t.complexity_50:.0f})"),
        (churn >= t.churn_50, f"Churn {churn:.0f} is at or above the repository median ({t.churn_50:.0f})"),
        (loc >= t.loc_50, f"{loc:.0f} lines, at or above the repository median ({t.loc_50:.0f})"),
        (nesting >= 3, f"Nesting depth {nesting} (3 or more)"),
        (bug_fixes >= 3, f"{bug_fixes} historical bug-fix commits (3 or more)"),
        (probability >= 0.40, f"Historical risk signal {probability:.0%} (40% or more)"),
    ]
    level = (opportunity or {}).get("difficulty")
    if level == "ADVANCED":
        met = [text for ok, text in advanced if ok]
    elif level == "INTERMEDIATE":
        met = [text for ok, text in intermediate if ok]
    else:
        met = []
    beginner_note = (
        "None of the conditions CodePulse uses for Intermediate or Advanced applied: "
        f"complexity {complexity:.0f}, churn {churn:.0f}, {loc:.0f} lines, nesting {nesting}."
    )
    return {
        "level": level,
        "summary": (
            f"CodePulse estimates this opportunity as {level.title()} based on repository evidence."
            if level else None
        ),
        "conditions_met": met if level in ("ADVANCED", "INTERMEDIATE") else [beginner_note],
        "factors": {
            "complexity": complexity,
            "churn": churn,
            "lines": loc,
            "nesting_depth": nesting,
            "bug_fix_commits": bug_fixes,
            "dependency_relationships": total,
            "used_by": incoming,
            "dependency_impact": impact or None,
        },
        "rule": (
            "Advanced when any advanced condition applies; otherwise Intermediate when any intermediate "
            "condition applies; otherwise Beginner. Thresholds are relative to this repository."
        ),
        "disclaimer": "This is an estimate from metrics, not a judgement of the actual work involved.",
    }


def why_this_file(row: dict | None, doc: dict | None, opportunity: dict | None, graph: Graph,
                  thresholds: Thresholds | None = None) -> dict:
    row = row or {}
    doc = doc or {}
    explanation = doc.get("explanation") or {}
    path = row.get("file") or doc.get("file")
    node = graph.nodes.get(path, {}) if path else {}
    issues = doc.get("issues") or []
    open_count = sum(1 for i in issues if str(i.get("state", "")).upper() == "OPEN")
    closed_count = sum(1 for i in issues if str(i.get("state", "")).upper() == "CLOSED")
    if not issues and opportunity:
        open_count = int(opportunity.get("open_issue_count") or 0)
        closed_count = int(opportunity.get("closed_issue_count") or 0)
    findings = doc.get("review_findings")
    finding_count = len(findings) if findings is not None else int(row.get("review_findings") or 0)
    debt_level = row.get("debt_level")
    probability = row.get("risk_probability")
    total = node.get("total", 0)
    incoming = node.get("incoming", 0)
    complexity = _num(row.get("complexity"))
    if explanation:
        complexity_high = bool(explanation.get("complexity_high"))
    else:  # same rule as FileRiskExplainer: non-zero and in the top quarter
        complexity_high = thresholds is not None and complexity > 0 and complexity >= thresholds.complexity_75

    checks = [
        {"key": "complexity", "label": "High complexity", "met": bool(complexity_high),
         "detail": f"Cyclomatic complexity {complexity:.0f}" + (" is in this repository's top quarter." if complexity_high else ".")},
        {"key": "debt", "label": "High technical debt", "met": debt_level in ("HIGH", "CRITICAL"),
         "detail": f"Technical debt {_num(row.get('debt_score')):.0f}/100 ({(debt_level or '').title()})."},
        {"key": "connected", "label": "Highly connected", "met": graph.available and total >= max(3, graph.total_p90),
         "detail": f"{total} direct dependency relationships; used by {incoming} local files."},
        {"key": "review", "label": "Related review findings", "met": finding_count > 0,
         "detail": f"{finding_count} rule-based review findings."},
        {"key": "issues", "label": "Related GitHub activity", "met": bool(open_count or closed_count),
         "detail": (
             f"{open_count} open and {closed_count} closed issues mention this file (CodePulse inferred)."
         )},
        {"key": "history", "label": "Historical bug-fix activity", "met": _num(row.get("bug_fix_commits")) > 0,
         "detail": f"{int(_num(row.get('bug_fix_commits')))} commits with bug-fix keywords touched this file."},
        {"key": "risk", "label": "Elevated historical risk signal", "met": probability is not None and probability >= 0.5,
         "detail": (
             f"Historical risk signal {probability:.0%}." if probability is not None else "Historical risk signal unavailable."
         )},
    ]
    met = [check for check in checks if check["met"]]
    parts = []
    if any(c["key"] == "connected" for c in met):
        parts.append(f"it is used by {incoming} other files, so an improvement here can benefit several parts of the code, and a mistake can affect them too")
    if any(c["key"] in ("complexity", "debt") for c in met):
        parts.append("its complexity and debt make it harder to read and change, which is where refactoring or tests tend to help most")
    if any(c["key"] in ("history", "risk") for c in met):
        parts.append("its history shows repeated bug-fix activity, which suggests it has been fragile in the past")
    if any(c["key"] == "issues" for c in met) and open_count:
        parts.append("an open issue mentions it, so there may be a concrete, wanted change")
    if any(c["key"] == "review" for c in met) and not parts:
        parts.append("review rules flagged concrete improvements that can be made without deep knowledge of the project")
    if parts:
        matters = "This matters because " + "; ".join(parts) + "."
    elif opportunity and opportunity.get("difficulty") == "BEGINNER":
        matters = "Few risk factors apply, which makes it a lower-risk place for a first, small contribution such as documentation, cleanup or tests."
    else:
        matters = "No strong risk factors were detected; the recommendation is based on the opportunity score's smaller components."
    return {
        "checks": checks,
        "why_it_matters": matters,
        "engine_reasons": (opportunity or {}).get("reasons") or explanation.get("reasons") or [],
        "note": "Based on static analysis, Git history and issue text matching. These are signals, not certainties.",
    }


def change_impact(path: str, graph: Graph, limit: int = 60) -> dict:
    if not graph.available or path not in graph.nodes:
        return {"available": False, "reason": "This file is not part of the dependency graph."}
    upstream = sorted(graph.depends_on.get(path, set()))
    downstream = sorted(graph.used_by.get(path, set()))
    second = sorted({
        source for dependent in downstream for source in graph.used_by.get(dependent, set())
    } - set(downstream) - {path})
    areas = Counter(directory_of(item) for item in downstream + second)
    return {
        "available": True,
        "file": path,
        "upstream": upstream[:limit],
        "downstream": downstream[:limit],
        "indirect": second[:limit],
        "affected_areas": [{"directory": key, "files": count} for key, count in areas.most_common(12)],
        "unresolved_imports": graph.unresolved.get(path, [])[:30],
        "truncated": max(len(upstream), len(downstream), len(second)) > limit,
        "note": (
            "Upstream: files this file imports. Downstream: files that import it. Indirect: files that import "
            "those dependents. Based on static imports only; dynamic imports, plugins and runtime wiring are "
            "not determined by static analysis."
        ),
    }


# ---------------------------------------------------------------------------
# Section-level builders used by the API
# ---------------------------------------------------------------------------

def build_guide(overview: dict, risk: dict, architecture: dict, opportunities: dict, issues: dict) -> dict:
    graph = Graph(architecture)
    file_rows = (risk or {}).get("files", [])
    items = (opportunities or {}).get("items", [])
    churn_sorted = sorted(file_rows, key=lambda row: -_num(row.get("commit_count")))[:5]
    return {
        "repository": overview.get("repository"),
        "facts": {
            "languages": overview.get("analyzed_languages") or {},
            "files": overview.get("analyzed_files"),
            "total_files": overview.get("total_files"),
            "lines_of_code": int(sum(_num(row.get("loc")) for row in file_rows)),
            "contributors": (overview.get("metrics") or {}).get("contributors", {}).get("value"),
            "commits": overview.get("commits"),
            "test_files": sum(1 for row in file_rows if is_test_file(row["file"])),
            "most_changed_files": [
                {"file": row["file"], "commits": int(_num(row.get("commit_count")))}
                for row in churn_sorted if _num(row.get("commit_count")) > 0
            ],
            "issues_available": bool((issues or {}).get("available")),
            "open_issues": ((issues or {}).get("counts") or {}).get("OPEN"),
        },
        "architecture_available": graph.available,
        "architecture_reason": None if graph.available else (architecture or {}).get("reason"),
        "groups": directory_groups(file_rows, graph, items) if file_rows else {"depth": 1, "groups": [], "edges": []},
        "start_here": start_here(graph, file_rows),
        "high_risk_areas": [
            {"file": row["file"], "risk_level": row.get("risk_level"), "risk_probability": row.get("risk_probability")}
            for row in file_rows if (row.get("risk_level") or "") in ("Critical", "High")
        ][:6],
        "roadmap": roadmap(items),
        "unresolved_dependencies": (architecture or {}).get("unresolved_dependencies"),
        "notes": [
            "Directory descriptions come from directory names and import structure only; CodePulse does not read code semantics.",
            "Start-here picks and roles are estimates from the dependency structure.",
        ],
    }


def issue_status(item: dict, issues_available: bool) -> str:
    if not issues_available:
        return "UNAVAILABLE"
    return "ISSUE_AVAILABLE" if item.get("open_issue_count", 0) > 0 else "NO_ISSUE"


def enrich_opportunities(opportunities: dict, risk: dict, architecture: dict, issues: dict) -> dict:
    graph = Graph(architecture)
    rows = {row["file"]: row for row in (risk or {}).get("files", [])}
    thresholds = Thresholds(list(rows.values()))
    issues_available = bool((issues or {}).get("available"))
    enriched = []
    for item in (opportunities or {}).get("items", []):
        row = rows.get(item["file"])
        node = graph.nodes.get(item["file"], {})
        enriched.append({
            **item,
            "risk_probability": (row or {}).get("risk_probability"),
            "risk_level": (row or {}).get("risk_level"),
            "debt_score": (row or {}).get("debt_score"),
            "debt_level": (row or {}).get("debt_level"),
            "connectivity": connectivity_label(node.get("total", 0), graph) if graph.available else None,
            "used_by": node.get("incoming"),
            "depends_on": node.get("outgoing"),
            "issue_status": issue_status(item, issues_available),
            "roles": [role["role"] for role in file_roles(item["file"], graph)],
            "why": why_this_file(row, None, item, graph, thresholds),
            "difficulty_basis": difficulty_basis(row, item, graph, thresholds) if row else None,
        })
    return {**(opportunities or {}), "items": enriched, "issues_available": issues_available}


def enrich_file(doc: dict, path: str, risk: dict, architecture: dict, opportunities: dict, issues: dict) -> dict:
    graph = Graph(architecture)
    file_rows = (risk or {}).get("files", [])
    rows = {row["file"]: row for row in file_rows}
    row = rows.get(path)
    opportunity = next((item for item in (opportunities or {}).get("items", []) if item["file"] == path), None)
    tests = related_tests(path, list(rows), graph)
    thresholds = Thresholds(file_rows)
    issues_available = bool((issues or {}).get("available"))
    node = graph.nodes.get(path, {})
    return {
        **doc,
        "roles": file_roles(path, graph),
        "connectivity": connectivity_label(node.get("total", 0), graph) if graph.available and node else None,
        "directory": directory_of(path),
        "tests": tests,
        "readiness": readiness(doc, tests, issues_available),
        "why": why_this_file(row, doc, opportunity, graph, thresholds),
        "difficulty_basis": difficulty_basis(row, opportunity, graph, thresholds) if row and opportunity else None,
        "change_impact": change_impact(path, graph),
        "issues_available": issues_available,
    }


def annotate_nodes(nodes: list[dict], graph_section: dict, opportunities: dict) -> list[dict]:
    graph = Graph(graph_section)
    opp = {item["file"]: item for item in (opportunities or {}).get("items", [])}
    out = []
    for node in nodes:
        item = opp.get(node["id"])
        out.append({
            **node,
            "connectivity": connectivity_label(node.get("total", 0), graph),
            "roles": [role["role"] for role in file_roles(node["id"], graph)],
            "opportunity": (
                {"difficulty": item.get("difficulty"), "score": item.get("opportunity_score"), "rank": item.get("rank")}
                if item else None
            ),
        })
    return out


def issue_related_files(issue_number: int, documents: dict, risk: dict, opportunities: dict) -> list[dict]:
    rows = {row["file"]: row for row in (risk or {}).get("files", [])}
    opp = {item["file"]: item for item in (opportunities or {}).get("items", [])}
    related = []
    for path, doc in (documents or {}).items():
        for match in doc.get("issues") or []:
            if match.get("number") == issue_number:
                row = rows.get(path, {})
                related.append({
                    "file": path,
                    "relevance": match.get("relevance"),
                    "score": match.get("score"),
                    "evidence": match.get("evidence") or [],
                    "risk_level": row.get("risk_level"),
                    "debt_level": row.get("debt_level"),
                    "opportunity": (
                        {"difficulty": opp[path].get("difficulty"), "score": opp[path].get("opportunity_score")}
                        if path in opp else None
                    ),
                })
    related.sort(key=lambda item: (-(item["score"] or 0), item["file"]))
    return related


# ---------------------------------------------------------------------------
# Issues: beginner signals, difficulty estimate and a work plan per issue
# ---------------------------------------------------------------------------

DIFFICULTY_ORDER = ("BEGINNER", "INTERMEDIATE", "ADVANCED")

# Label names maintainers commonly use. A match is reported with the exact
# label text, so the user always sees what was detected on GitHub.
_LABEL_SIGNALS = (
    ("beginner", re.compile(r"good[\s_-]*first|first[\s_-]*timers?|beginner|\beasy\b|starter|newcomer|low[\s_-]*hanging", re.I)),
    ("help_wanted", re.compile(r"help[\s_-]*wanted|contributions?[\s_-]*welcome|up[\s_-]*for[\s_-]*grabs", re.I)),
    ("documentation", re.compile(r"\bdoc(s|umentation)?\b", re.I)),
)

# Evidence strings produced by the engine's issue matcher for direct mentions.
_DIRECT_EVIDENCE = ("File path found", "File name found", "File/module name found")

_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "when", "should", "would", "could", "does", "doesn",
    "not", "into", "have", "has", "are", "was", "were", "will", "can", "cannot", "but", "add", "support",
    "using", "use", "used", "make", "error", "issue", "bug", "fix", "feature", "request", "option", "allow",
    "also", "some", "more", "less", "than", "then", "there", "their", "they", "what", "which", "while",
    "about", "after", "before", "other", "only", "like", "need", "needs", "work", "works", "working",
}


def label_signals(labels: list[str]) -> list[dict]:
    signals = []
    for label in labels or []:
        for kind, pattern in _LABEL_SIGNALS:
            if pattern.search(label):
                signals.append({"kind": kind, "label": label})
                break
    return signals


def issue_file_index(documents: dict) -> dict[int, list[dict]]:
    """issue number -> files the engine matched to it, strongest first."""
    index: dict[int, list[dict]] = defaultdict(list)
    for path, doc in (documents or {}).items():
        for match in doc.get("issues") or []:
            number = match.get("number")
            if number is None:
                continue
            evidence = match.get("evidence") or []
            index[number].append({
                "file": path,
                "relevance": match.get("relevance"),
                "score": match.get("score"),
                "evidence": evidence,
                "direct": any(item.startswith(_DIRECT_EVIDENCE) for item in evidence),
            })
    for matches in index.values():
        matches.sort(key=lambda item: (not item["direct"], -(item["score"] or 0), item["file"]))
    return dict(index)


def _considered(matches: list[dict], limit: int = 5) -> list[dict]:
    """The matches an estimate is based on: direct mentions if any, else HIGH, else all."""
    direct = [item for item in matches if item["direct"]]
    high = [item for item in matches if item["relevance"] == "HIGH"]
    return (direct or high or matches)[:limit]


def issue_difficulty(matches: list[dict], rows: dict, opportunities: dict, graph: Graph) -> dict:
    """Estimated difficulty of an issue from the files it was matched to.

    Rule: start from the hardest engine difficulty among the considered files,
    then raise it one level if any caution signal applies (High/Critical risk,
    a core or highly connected file, or three or more files involved).
    """
    if not matches:
        return {
            "status": "UNAVAILABLE",
            "level": None,
            "reason": "No analyzed file was matched to this issue, so there is nothing to base an estimate on.",
            "basis": [],
            "files_considered": [],
        }
    considered = _considered(matches)
    rated = [(item["file"], opportunities[item["file"]].get("difficulty")) for item in considered
             if item["file"] in opportunities and opportunities[item["file"]].get("difficulty") in DIFFICULTY_ORDER]
    if not rated:
        return {
            "status": "UNAVAILABLE",
            "level": None,
            "reason": "The matched files have no difficulty rating in this analysis.",
            "basis": [],
            "files_considered": [item["file"] for item in considered],
        }
    hardest_file, base = max(rated, key=lambda pair: DIFFICULTY_ORDER.index(pair[1]))
    basis = [f"Hardest matched file, {hardest_file}, is rated {base.title()} by CodePulse's difficulty rule."]
    cautions = []
    for item in considered:
        path = item["file"]
        level = (rows.get(path) or {}).get("risk_level")
        if level in ("High", "Critical"):
            cautions.append(f"{path} has a {level} historical risk signal.")
        roles = {role["role"] for role in file_roles(path, graph)}
        if roles & {"Core dependency", "Highly connected"}:
            count = len(graph.used_by.get(path, set()))
            cautions.append(f"{path} is a central file (used by {count} other files).")
    if len(considered) >= 3:
        cautions.append(f"The issue matches {len(considered)} files, so a change may span several files.")
    level = base
    if cautions and base != "ADVANCED":
        level = DIFFICULTY_ORDER[DIFFICULTY_ORDER.index(base) + 1]
        basis.append(f"Raised one level to {level.title()} because:")
    elif cautions:
        basis.append("Other caution signals:")
    basis.extend(cautions[:4])
    weak = not any(item["direct"] for item in considered)
    return {
        "status": "ESTIMATED",
        "level": level,
        "base_level": base,
        "raised": level != base,
        "basis": basis,
        "files_considered": [item["file"] for item in considered],
        "match_strength": "weak" if weak else "strong",
        "reason": (
            "The issue only shares keywords with these files; it does not name them, so this estimate is less reliable."
            if weak else None
        ),
    }


def _search_terms(title: str, limit: int = 4) -> list[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_.]{2,}", title or "")
    seen, terms = set(), []
    for word in words:
        key = word.lower().strip(".")
        if len(key) < 4 or key in _STOPWORDS or key in seen:
            continue
        seen.add(key)
        terms.append(word.strip("."))
        if len(terms) == limit:
            break
    return terms


def enrich_issues(issues: dict, documents: dict, risk: dict, architecture: dict, opportunities: dict) -> dict:
    if not (issues or {}).get("available"):
        return issues or {}
    graph = Graph(architecture)
    rows = {row["file"]: row for row in (risk or {}).get("files", [])}
    opp = {item["file"]: item for item in (opportunities or {}).get("items", [])}
    index = issue_file_index(documents)
    enriched = []
    for issue in issues.get("issues", []):
        matches = index.get(issue.get("number"), [])
        enriched.append({
            **issue,
            "signals": label_signals(issue.get("labels", [])),
            "difficulty": issue_difficulty(matches, rows, opp, graph),
            "match_count": len(matches),
        })
    return {
        **issues,
        "issues": enriched,
        "difficulty_note": (
            "Estimated from the files CodePulse matched to each issue: the hardest file's difficulty, raised one "
            "level for high risk, central files or several files. It is a starting point, not a promise."
        ),
    }


def issue_work_plan(issue: dict, repo_full_name: str, documents: dict, risk: dict, architecture: dict,
                    opportunities: dict) -> dict:
    """Everything needed to start on one issue, built only from stored results."""
    graph = Graph(architecture)
    rows = {row["file"]: row for row in (risk or {}).get("files", [])}
    opp = {item["file"]: item for item in (opportunities or {}).get("items", [])}
    matches = issue_file_index(documents).get(issue["number"], [])
    considered = {item["file"] for item in _considered(matches)}
    all_files = list(rows)

    files = []
    for match in matches[:12]:
        path = match["file"]
        row = rows.get(path, {})
        node = graph.nodes.get(path, {})
        tests = related_tests(path, all_files, graph)
        files.append({
            **match,
            "primary": path in considered,
            "risk_level": row.get("risk_level"),
            "debt_level": row.get("debt_level"),
            "difficulty": (opp.get(path) or {}).get("difficulty"),
            "roles": [role["role"] for role in file_roles(path, graph)],
            "connectivity": connectivity_label(node.get("total", 0), graph) if graph.available and node else None,
            "used_by": sorted(graph.used_by.get(path, set())),
            "depends_on": sorted(graph.depends_on.get(path, set())),
            "tests": tests,
        })

    number = issue["number"]
    steps: list[dict] = [{
        "key": "read_issue",
        "title": "Read the issue and its discussion",
        "detail": (
            f"Open #{number} on GitHub and read every comment. Check whether someone is already assigned or has "
            "opened a pull request (CodePulse cannot see this), and ask a maintainer if anything is unclear."
        ),
        "files": [],
    }]
    if issue.get("state") != "OPEN":
        steps[0]["detail"] = f"#{number} is closed, so it is shown for learning only. " + steps[0]["detail"]

    search = None
    if not files:
        terms = _search_terms(issue.get("title", ""))
        if terms:
            from urllib.parse import quote_plus
            search = {
                "terms": terms,
                "url": f"https://github.com/{repo_full_name}/search?q={quote_plus(' '.join(terms))}&type=code",
            }
        steps.append({
            "key": "find_code",
            "title": "Find the code involved",
            "detail": (
                "CodePulse could not match this issue to any analyzed file because the issue text does not mention "
                "file or module names. Search the repository for words from the issue title"
                + (f" ({', '.join(terms)})." if terms else ".")
            ),
            "files": [],
        })
    else:
        primary = [item["file"] for item in files if item["primary"]][:3]
        steps.append({
            "key": "read_files",
            "title": "Read the most likely files",
            "detail": "Start with the files the issue mentions most directly. Understand what they do before changing anything.",
            "files": primary,
        })
        for item in files:
            if item["primary"] and item["used_by"]:
                count = len(item["used_by"])
                steps.append({
                    "key": f"impact:{item['file']}",
                    "title": f"Check what uses {posixpath.basename(item['file'])}",
                    "detail": (
                        f"{count} {'file imports' if count == 1 else 'files import'} {item['file']}. "
                        "Keep its behaviour the same for them, or update them too."
                    ),
                    "files": item["used_by"][:6],
                })
        tests = sorted({
            test["file"] for item in files if item["primary"]
            for test in item["tests"]["detected"] + item["tests"]["heuristic"]
        })
        if tests:
            steps.append({
                "key": "tests",
                "title": "Run the related tests before and after your change",
                "detail": "These tests import or are named after the files above. They should pass before and after.",
                "files": tests[:8],
            })
        else:
            steps.append({
                "key": "tests",
                "title": "No related test was found",
                "detail": (
                    "Run the project's full test suite instead, and consider adding a test that reproduces the issue. "
                    "Maintainers usually welcome that."
                ),
                "files": [],
            })
    steps.append({
        "key": "change",
        "title": "Make a small, focused change",
        "detail": "Change only what the issue needs. For a bug, reproduce it first so you can show it is fixed.",
        "files": [],
    })
    steps.append({
        "key": "pull_request",
        "title": "Open a pull request",
        "detail": f"Describe what you changed and write “Fixes #{number}” so GitHub links the pull request to the issue.",
        "files": [],
    })

    return {
        "issue": {**issue, "signals": label_signals(issue.get("labels", []))},
        "difficulty": issue_difficulty(matches, rows, opp, graph),
        "files": files,
        "more_files": max(0, len(matches) - len(files)),
        "steps": steps,
        "search": search,
        "basis": (
            "Related files are a CodePulse inferred relationship: the issue's title or body mentions the file path, "
            "name, module, directory or module keywords. GitHub does not link these files to the issue."
        ),
    }
