"""Contributor guide: onboarding, explanations, tests, readiness and issue->file inference."""

import pytest

from app.services import guide


@pytest.fixture
def analyzed(client, auth_headers, fake_engine):
    body = client.post("/api/repositories", json={"url": "octo/shop"}, headers=auth_headers).json()
    return body["repository"]["id"]


def get(client, auth_headers, repo_id, path, **params):
    response = client.get(f"/api/repositories/{repo_id}/{path}", headers=auth_headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_guide_onboarding(client, auth_headers, analyzed):
    data = get(client, auth_headers, analyzed, "guide")
    assert data["facts"]["files"] == 4
    assert data["facts"]["lines_of_code"] == 200 + 170 + 140 + 110
    group_ids = {group["id"] for group in data["groups"]["groups"]}
    assert {"src/core", "src/api", "web"} <= group_ids
    # Directory-to-directory edges come from real file imports only.
    assert {"source": "src/api", "target": "src/core", "count": 2} in data["groups"]["edges"]
    starts = {item["file"]: item["label"] for item in data["start_here"]}
    assert starts["src/api/routes.py"] == "Possible entry point"
    assert data["roadmap"]["ADVANCED"][0]["file"] == "src/core/payment.py"
    assert data["roadmap"]["BEGINNER"][0]["file"] == "src/core/user.py"


def test_opportunities_explain_why_and_difficulty(client, auth_headers, analyzed):
    data = get(client, auth_headers, analyzed, "opportunities")
    top = data["items"][0]
    assert top["issue_status"] == "ISSUE_AVAILABLE"
    assert data["items"][1]["issue_status"] == "NO_ISSUE"
    checks = {check["key"]: check["met"] for check in top["why"]["checks"]}
    assert checks["debt"] is True and checks["review"] is True and checks["issues"] is True
    assert top["why"]["why_it_matters"].startswith("This matters because")
    basis = top["difficulty_basis"]
    assert basis["level"] == "ADVANCED"
    assert basis["conditions_met"]
    assert "estimates" in basis["summary"]


def test_file_intelligence_has_contributor_sections(client, auth_headers, analyzed):
    data = get(client, auth_headers, analyzed, "files/intelligence", path="src/core/payment.py")
    keys = {item["key"]: item["status"] for item in data["readiness"]}
    assert keys["issue"] == "ok" and keys["history"] == "ok"
    assert keys["tests"] == "unavailable"  # the fixture has no test files
    impact = data["change_impact"]
    assert impact["available"] is True
    assert set(impact["downstream"]) == {"src/api/routes.py", "src/core/user.py"}
    assert data["directory"] == "src/core"


def test_issue_related_files_are_labelled_inferred(client, auth_headers, analyzed):
    data = get(client, auth_headers, analyzed, "issues/7/files")
    assert data["files"][0]["file"] == "src/core/payment.py"
    assert data["files"][0]["evidence"]
    assert "inferred" in data["basis"].lower()
    missing = client.get(f"/api/repositories/{analyzed}/issues/999/files", headers=auth_headers)
    assert missing.status_code == 404


def test_architecture_nodes_have_roles(client, auth_headers, analyzed):
    data = get(client, auth_headers, analyzed, "architecture")
    payment = next(node for node in data["nodes"] if node["id"] == "src/core/payment.py")
    assert payment["opportunity"]["difficulty"] == "ADVANCED"
    assert payment["connectivity"]


def test_related_tests_detected_and_heuristic():
    graph = guide.Graph({
        "available": True,
        "nodes": [],
        "edges": [{"source": "tests/test_other.py", "target": "src/util.py"}],
    })
    files = ["src/util.py", "tests/test_util.py", "tests/test_other.py", "web/util.spec.ts"]
    result = guide.related_tests("src/util.py", files, graph)
    assert [item["file"] for item in result["detected"]] == ["tests/test_other.py"]
    assert {item["file"] for item in result["heuristic"]} == {"tests/test_util.py", "web/util.spec.ts"}
    none = guide.related_tests("src/util.py", ["src/util.py", "src/other.py"], graph)
    assert none["available"] is False


def test_is_test_file():
    assert guide.is_test_file("tests/test_api.py")
    assert guide.is_test_file("pkg/api_test.py")
    assert guide.is_test_file("src/button.test.tsx")
    assert guide.is_test_file("src/main/FooTest.java")
    assert not guide.is_test_file("src/contest.py")


def test_difficulty_basis_matches_engine_rule():
    engine = pytest.importorskip("analysis.contribution_opportunities")
    rows = [
        {"file": f"f{i}.py", "complexity": c, "code_churn": ch, "loc": loc, "nesting_depth": 1,
         "bug_fix_commits": 0, "risk_probability": 0.1}
        for i, (c, ch, loc) in enumerate([(2, 5, 40), (8, 30, 120), (35, 90, 400), (4, 10, 60)])
    ]
    thresholds = guide.Thresholds(rows)
    generator = engine.ContributionOpportunityGenerator()
    graph = guide.Graph({"available": True, "nodes": [], "edges": []})
    for row in rows:
        expected = generator.classify_difficulty(
            {"complexity": row["complexity"], "code_churn": row["code_churn"], "loc": row["loc"],
             "bug_fix_commits": 0, "bug_probability": 0.1, "nesting_depth": 1,
             "impact_level": "", "related_count": 0},
            thresholds.complexity_75, thresholds.complexity_50, thresholds.churn_75,
            thresholds.churn_50, thresholds.loc_75, thresholds.loc_50,
        )
        basis = guide.difficulty_basis(row, {"difficulty": expected}, graph, thresholds)
        if expected == "BEGINNER":
            assert basis["conditions_met"][0].startswith("None of the conditions")
        else:
            assert basis["conditions_met"], (row, expected)


def test_issues_have_signals_and_difficulty(client, auth_headers, analyzed):
    data = get(client, auth_headers, analyzed, "issues")
    by_number = {issue["number"]: issue for issue in data["issues"]}
    seven = by_number[7]
    assert seven["match_count"] == 1
    assert seven["difficulty"]["status"] == "ESTIMATED"
    # payment.py is rated ADVANCED by the engine, so the estimate cannot be lower.
    assert seven["difficulty"]["level"] == "ADVANCED"
    assert seven["difficulty"]["match_strength"] == "strong"
    assert by_number[3]["difficulty"]["status"] == "UNAVAILABLE"
    assert by_number[3]["difficulty"]["level"] is None
    assert "difficulty_note" in data


def test_issue_work_plan(client, auth_headers, analyzed):
    data = get(client, auth_headers, analyzed, "issues/7/work")
    assert data["issue"]["number"] == 7
    assert data["files"][0]["file"] == "src/core/payment.py"
    assert data["files"][0]["primary"] is True
    keys = [step["key"] for step in data["steps"]]
    assert keys[0] == "read_issue" and keys[-1] == "pull_request"
    assert "read_files" in keys and "impact:src/core/payment.py" in keys
    tests_step = next(step for step in data["steps"] if step["key"] == "tests")
    assert tests_step["title"] == "No related test was found"
    assert "Fixes #7" in data["steps"][-1]["detail"]

    unmatched = get(client, auth_headers, analyzed, "issues/3/work")
    assert unmatched["files"] == []
    assert any(step["key"] == "find_code" for step in unmatched["steps"])
    assert unmatched["search"]["terms"] == ["crash"]
    assert "octo/shop" in unmatched["search"]["url"]
    assert "closed" in unmatched["steps"][0]["detail"]
    assert client.get(f"/api/repositories/{analyzed}/issues/999/work", headers=auth_headers).status_code == 404


def test_label_signals():
    signals = guide.label_signals(["good first issue", "help wanted", "Documentation", "bug", "Type: Easy"])
    assert [item["kind"] for item in signals] == ["beginner", "help_wanted", "documentation", "beginner"]


def test_issue_difficulty_raises_for_caution_signals():
    graph = guide.Graph({"available": True, "nodes": [], "edges": []})
    matches = [{"file": "a.py", "relevance": "HIGH", "score": 8, "evidence": ["File name found in issue body"], "direct": True}]
    opp = {"a.py": {"difficulty": "BEGINNER"}}
    plain = guide.issue_difficulty(matches, {"a.py": {"risk_level": "Low"}}, opp, graph)
    assert plain["level"] == "BEGINNER" and plain["raised"] is False
    risky = guide.issue_difficulty(matches, {"a.py": {"risk_level": "High"}}, opp, graph)
    assert risky["level"] == "INTERMEDIATE" and risky["raised"] is True
    assert any("High historical risk" in line for line in risky["basis"])
    weak = guide.issue_difficulty(
        [{**matches[0], "evidence": ["Matching module keywords: pay"], "direct": False, "relevance": "MEDIUM"}],
        {}, opp, graph,
    )
    assert weak["match_strength"] == "weak" and weak["reason"]
