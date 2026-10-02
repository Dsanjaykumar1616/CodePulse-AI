"""Test configuration: a throwaway SQLite database and inline analysis jobs."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

_DB_DIR = tempfile.mkdtemp(prefix="codepulse_api_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_DIR}/test.db"
os.environ["JWT_SECRET"] = "test-secret-not-for-production-0123456789"
os.environ["CODEPULSE_RUN_JOBS_INLINE"] = "1"
os.environ.pop("GITHUB_TOKEN", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import engine_runner  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fake_engine import fake_run_engine  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def fake_engine(monkeypatch):
    calls = []

    def runner(repo_url, **kwargs):
        calls.append(repo_url)
        return fake_run_engine(repo_url, **kwargs)

    monkeypatch.setattr(engine_runner, "run_engine", runner)
    return calls


def signup(client, email="ada@example.com", password="analytical1", name="Ada"):
    response = client.post(
        "/api/auth/signup", json={"name": name, "email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def auth_headers(client):
    token = signup(client)["access_token"]
    return {"Authorization": f"Bearer {token}"}
