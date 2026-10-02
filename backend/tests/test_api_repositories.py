import pytest

from app.services.github_url import InvalidRepositoryUrl, parse_github_url
from conftest import signup


@pytest.mark.parametrize("value,owner,name", [
    ("https://github.com/psf/requests", "psf", "requests"),
    ("https://github.com/psf/requests.git", "psf", "requests"),
    ("http://www.github.com/psf/requests/", "psf", "requests"),
    ("github.com/psf/requests", "psf", "requests"),
    ("git@github.com:psf/requests.git", "psf", "requests"),
    ("psf/requests", "psf", "requests"),
    ("https://github.com/psf/requests/tree/main/src", "psf", "requests"),
])
def test_parse_valid_urls(value, owner, name):
    parsed = parse_github_url(value)
    assert (parsed.owner, parsed.name) == (owner, name)
    assert parsed.canonical_url == f"https://github.com/{owner}/{name}".lower()


@pytest.mark.parametrize("value", [
    "", "https://gitlab.com/a/b", "https://github.com/psf", "file:///etc/passwd",
    "../../etc/passwd", "https://github.com/../x", "https://github.com/a/b; rm -rf /",
    "/home/user/repo", "https://evil.com/github.com/a/b",
])
def test_parse_rejects_invalid_urls(value):
    with pytest.raises(InvalidRepositoryUrl):
        parse_github_url(value)


def test_add_repository_rejects_invalid_url(client, auth_headers, fake_engine):
    response = client.post("/api/repositories", json={"url": "https://gitlab.com/a/b"}, headers=auth_headers)
    assert response.status_code == 422
    assert fake_engine == []


def test_add_repository_starts_and_completes_analysis(client, auth_headers, fake_engine):
    response = client.post(
        "/api/repositories", json={"url": "https://github.com/psf/requests"}, headers=auth_headers
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["created"] is True
    assert body["repository"]["full_name"] == "psf/requests"
    job = body["job"]
    assert job is not None

    status = client.get(f"/api/analysis/{job['id']}/status", headers=auth_headers).json()
    assert status["status"] == "completed"
    assert status["progress"] == 100
    assert all(stage["status"] == "done" for stage in status["stages"])
    assert fake_engine == ["https://github.com/psf/requests"]

    repository = client.get(f"/api/repositories/{body['repository']['id']}", headers=auth_headers).json()
    assert repository["status"] == "completed"
    assert repository["has_results"] is True
    assert repository["health_score"] == 61.4
    assert repository["debt_score"] == 41.8 or repository["debt_score"] == 41.75


def test_adding_same_repository_reuses_it(client, auth_headers, fake_engine):
    first = client.post("/api/repositories", json={"url": "psf/requests"}, headers=auth_headers).json()
    again = client.post(
        "/api/repositories", json={"url": "https://github.com/PSF/Requests.git"}, headers=auth_headers
    )
    assert again.status_code == 200
    assert again.json()["created"] is False
    assert again.json()["repository"]["id"] == first["repository"]["id"]
    assert len(client.get("/api/repositories", headers=auth_headers).json()) == 1


def test_list_reanalyze_and_delete(client, auth_headers, fake_engine):
    repo_id = client.post("/api/repositories", json={"url": "psf/requests"}, headers=auth_headers).json()["repository"]["id"]
    listing = client.get("/api/repositories", headers=auth_headers).json()
    assert [item["id"] for item in listing] == [repo_id]

    job = client.post(f"/api/repositories/{repo_id}/analyze", headers=auth_headers)
    assert job.status_code == 202
    jobs = client.get(f"/api/repositories/{repo_id}/jobs", headers=auth_headers).json()
    assert len(jobs) == 2

    assert client.delete(f"/api/repositories/{repo_id}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/repositories/{repo_id}", headers=auth_headers).status_code == 404
    assert client.get(f"/api/analysis/{job.json()['id']}", headers=auth_headers).status_code == 404


def test_users_cannot_access_each_others_repositories(client, auth_headers, fake_engine):
    repo_id = client.post("/api/repositories", json={"url": "psf/requests"}, headers=auth_headers).json()["repository"]["id"]
    other = {"Authorization": f"Bearer {signup(client, email='eve@example.com')['access_token']}"}
    assert client.get(f"/api/repositories/{repo_id}", headers=other).status_code == 404
    assert client.get(f"/api/repositories/{repo_id}/overview", headers=other).status_code == 404
    assert client.delete(f"/api/repositories/{repo_id}", headers=other).status_code == 404
    assert client.get("/api/repositories", headers=other).json() == []


def test_add_without_analysis(client, auth_headers, fake_engine):
    body = client.post(
        "/api/repositories", json={"url": "psf/requests", "analyze": False}, headers=auth_headers
    ).json()
    assert body["job"] is None
    assert body["repository"]["status"] == "never_analyzed"
    overview = client.get(f"/api/repositories/{body['repository']['id']}/overview", headers=auth_headers)
    assert overview.status_code == 404
    assert fake_engine == []
