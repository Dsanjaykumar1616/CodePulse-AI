import pytest

from app.services import engine_runner
from app.services.engine_runner import AnalysisError


@pytest.fixture
def analyzed(client, auth_headers, fake_engine):
    body = client.post("/api/repositories", json={"url": "octo/shop"}, headers=auth_headers).json()
    return body["repository"]["id"]


def get(client, auth_headers, repo_id, path, **params):
    response = client.get(f"/api/repositories/{repo_id}/{path}", headers=auth_headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_overview_returns_engine_values(client, auth_headers, analyzed):
    data = get(client, auth_headers, analyzed, "overview")
    metrics = data["metrics"]
    assert data["repository"]["full_name"] == "octo/shop"
    assert data["repository"]["url"] == "https://github.com/octo/shop"
    assert metrics["health_score"]["value"] == 61.4
    assert metrics["code_quality"]["value"] == 58.0
    assert metrics["technical_debt"]["value"] == pytest.approx(41.8, abs=0.1)
    assert metrics["duplicate_groups"]["value"] == 1
    assert metrics["dependencies"]["value"] == 3
    assert metrics["contributors"]["value"] == 5
    # Average of the model's probabilities, expressed as 0-100.
    assert metrics["historical_risk_signal"]["value"] == pytest.approx(44.0, abs=0.1)
    assert data["languages"] == {"Python": 3, "JavaScript": 1}
    assert data["warnings"]


def test_no_internal_paths_leak(client, auth_headers, analyzed):
    for section in ("overview", "health", "risk", "debt", "duplicates", "architecture", "review",
                    "issues", "opportunities", "files"):
        text = client.get(f"/api/repositories/{analyzed}/{section}", headers=auth_headers).text
        assert "/srv/codepulse" not in text, section
    text = client.get(
        f"/api/repositories/{analyzed}/files/intelligence", params={"path": "src/core/payment.py"}, headers=auth_headers
    ).text
    assert "/srv/codepulse" not in text


def test_health_and_risk(client, auth_headers, analyzed):
    health = get(client, auth_headers, analyzed, "health")
    assert health["overall_score"] == 61.4
    keys = {component["key"]: component for component in health["components"]}
    assert keys["defect_risk"]["label"] == "Historical Risk"
    assert keys["maintainability"]["value"] == 67.5
    assert health["evidence"]["code_quality"]["most_complex_files"][0]["file"] == "src/core/payment.py"

    risk = get(client, auth_headers, analyzed, "risk")
    assert risk["available"] is True
    assert risk["selected_model"] == "Random Forest"
    assert "not a confirmed probability" in risk["label_definition"]
    top = risk["files"][0]
    assert top["file"] == "src/core/payment.py"
    assert top["risk_level"] == "Critical"
    assert top["maintainability"] == 60.0
    assert top["debt_score"] == 72.0


def test_debt_duplicates_review_issues(client, auth_headers, analyzed):
    debt = get(client, auth_headers, analyzed, "debt")
    assert debt["distribution"] == {"LOW": 2, "MEDIUM": 1, "HIGH": 1, "CRITICAL": 0}
    assert debt["files"][0]["debt_reasons"] == ["High relative complexity"]

    duplicates = get(client, auth_headers, analyzed, "duplicates")
    assert duplicates["groups"][0]["files"] == ["src/core/payment.py", "src/core/user.py"]
    assert duplicates["groups"][0]["severity"] == "HIGH"
    assert "line" in duplicates["limitations"]

    review = get(client, auth_headers, analyzed, "review")
    assert review["counts"]["HIGH"] == 1
    assert review["findings"][0]["rule_id"] == "COMPLEXITY_HIGH"

    issues = get(client, auth_headers, analyzed, "issues")
    assert issues["counts"] == {"OPEN": 1, "CLOSED": 1, "UNKNOWN": 0}
    open_issue = next(issue for issue in issues["issues"] if issue["number"] == 7)
    assert open_issue["related_files"] == ["src/core/payment.py"]
    assert open_issue["labels"] == ["bug"]


def test_opportunities_reach_frontend(client, auth_headers, analyzed):
    data = get(client, auth_headers, analyzed, "opportunities")
    assert data["available"] is True
    assert [item["file"] for item in data["items"]] == ["src/core/payment.py", "src/core/user.py"]
    assert data["items"][0]["difficulty"] == "ADVANCED"
    assert data["items"][0]["review_finding_count"] == 1
    assert "guidance" in data["disclaimer"]


def test_architecture_graph_and_filters(client, auth_headers, analyzed):
    data = get(client, auth_headers, analyzed, "architecture")
    assert data["available"] is True
    ids = {node["id"] for node in data["nodes"]}
    assert "src/core/payment.py" in ids
    assert {"source": "src/core/user.py", "target": "src/core/payment.py"} in data["edges"]
    payment = next(node for node in data["nodes"] if node["id"] == "src/core/payment.py")
    assert payment["incoming"] == 2 and payment["outgoing"] == 0
    assert payment["risk_level"] == "Critical"
    assert data["unresolved"] == [{"file": "src/api/routes.py", "imports": ["flask"]}]

    limited = get(client, auth_headers, analyzed, "architecture", limit=5, directory="src/core")
    assert {node["id"] for node in limited["nodes"]} == {"src/core/payment.py", "src/core/user.py"}

    focused = get(client, auth_headers, analyzed, "architecture", focus="src/api/routes.py", depth=1)
    assert focused["nodes"][0]["id"] == "src/api/routes.py"
    assert {node["id"] for node in focused["nodes"]} == {"src/api/routes.py", "src/core/payment.py", "src/core/user.py"}

    missing = client.get(
        f"/api/repositories/{analyzed}/architecture", params={"focus": "nope.py"}, headers=auth_headers
    )
    assert missing.status_code == 404


def test_file_intelligence(client, auth_headers, analyzed):
    data = get(client, auth_headers, analyzed, "files/intelligence", path="src/core/payment.py")
    assert data["file"] == "src/core/payment.py"
    assert data["plan"]["steps"]
    assert data["summary"]["risk_level"] == "Critical"
    assert data["debt"]["technical_debt_level"] == "HIGH"
    assert data["review_findings"][0]["rule_id"] == "COMPLEXITY_HIGH"
    assert data["duplicates"][0]["similarity_score"] == 91.2
    assert data["opportunity"]["difficulty"] == "ADVANCED"
    assert data["issues"][0]["number"] == 7

    files = get(client, auth_headers, analyzed, "files")
    assert len(files["files"]) == 4


@pytest.mark.parametrize("path", ["../../etc/passwd", "src/../../secret", "/etc/passwd", "unknown.py"])
def test_file_intelligence_rejects_unknown_or_unsafe_paths(client, auth_headers, analyzed, path):
    response = client.get(
        f"/api/repositories/{analyzed}/files/intelligence", params={"path": path}, headers=auth_headers
    )
    assert response.status_code in (404, 422)


def test_report_download(client, auth_headers, analyzed):
    response = client.get(f"/api/repositories/{analyzed}/report", headers=auth_headers)
    assert response.status_code == 200
    assert "CodePulse AI Analysis Report" in response.text
    assert "attachment" in response.headers["content-disposition"]


@pytest.mark.parametrize("code", ["repository_not_found", "private_repository", "network_error", "no_source_files"])
def test_failed_analysis_reports_error(client, auth_headers, monkeypatch, code):
    def failing(repo_url, *, progress, **_):
        progress("repository_access", "running", None)
        raise AnalysisError(code, f"Readable message for {code}")

    monkeypatch.setattr(engine_runner, "run_engine", failing)
    body = client.post("/api/repositories", json={"url": "octo/missing"}, headers=auth_headers).json()
    job = client.get(f"/api/analysis/{body['job']['id']}", headers=auth_headers).json()
    assert job["status"] == "failed"
    assert job["error_code"] == code
    assert job["error_message"] == f"Readable message for {code}"
    stage = next(s for s in job["stages"] if s["key"] == "repository_access")
    assert stage["status"] == "failed"
    repo = client.get(f"/api/repositories/{body['repository']['id']}", headers=auth_headers).json()
    assert repo["status"] == "failed"
    assert repo["has_results"] is False


def test_unexpected_crash_is_contained(client, auth_headers, monkeypatch):
    def crashing(repo_url, **_):
        raise RuntimeError("boom")

    monkeypatch.setattr(engine_runner, "run_engine", crashing)
    body = client.post("/api/repositories", json={"url": "octo/crash"}, headers=auth_headers).json()
    job = client.get(f"/api/analysis/{body['job']['id']}", headers=auth_headers).json()
    assert job["status"] == "failed"
    assert job["error_code"] == "analysis_failed"


def test_health_endpoint(client):
    assert client.get("/api/health").json()["database"] == "ok"
