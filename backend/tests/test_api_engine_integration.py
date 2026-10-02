"""End-to-end check with the real CodePulse engine on a small local Git repository."""

import os
import shutil
import tempfile

import pytest

git = pytest.importorskip("git")
pytest.importorskip("radon")
pytest.importorskip("lizard")

from app.services import engine_runner  # noqa: E402
from app.services.result_builder import build_sections  # noqa: E402

FILES = {
    "shop/payment_service.py": (
        "class PaymentService:\n"
        "    def process(self, amount):\n"
        "        if amount > 0:\n"
        "            if amount > 100:\n"
        "                return 'large'\n"
        "            return True\n"
        "        return False\n"
    ),
    "shop/user_service.py": (
        "from shop.payment_service import PaymentService\n"
        "class UserService:\n"
        "    def pay(self):\n"
        "        return PaymentService().process(100)\n"
    ),
    "shop/__init__.py": "",
    "web/app.js": "import { start } from './util.js';\nfunction main() { start(); }\n",
    "web/util.js": "export function start() { console.log('started'); }\n",
}


@pytest.fixture(scope="module")
def local_repo():
    directory = tempfile.mkdtemp(prefix="codepulse_engine_it_")
    repo = git.Repo.init(directory)
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
    for path, content in FILES.items():
        full = os.path.join(directory, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(content)
    repo.git.add(all=True)
    repo.index.commit("Initial commit")
    with open(os.path.join(directory, "shop/payment_service.py"), "a", encoding="utf-8") as handle:
        handle.write("\n# handle negative amounts\n")
    repo.git.add(all=True)
    repo.index.commit("Fix bug in payment processing")
    yield directory
    shutil.rmtree(directory, ignore_errors=True)


def _run(local_repo, progress):
    return engine_runner.run_engine(
        local_repo, owner=None, name="sample", progress=progress, check_github=False
    )


def test_real_engine_produces_real_sections(local_repo):
    events = []
    run = _run(local_repo, lambda key, status, message: events.append((key, status)))
    try:
        sections = build_sections(run)
    finally:
        shutil.rmtree(run.repo_path, ignore_errors=True)

    keys = [key for key, _ in engine_runner.STAGES]
    assert [key for key, status in events if status == "running"] == keys
    assert ("repository_access", "done") in events
    # Too few files for ML on this tiny repository: skipped, not faked.
    assert ("ml_risk", "skipped") in events
    assert sections["risk"]["available"] is False
    assert sections["overview"]["metrics"]["historical_risk_signal"]["value"] is None
    assert sections["overview"]["metrics"]["historical_risk_signal"]["reason"]

    files = {row["file"] for row in sections["risk"]["files"]}
    assert "shop/payment_service.py" in files
    assert sections["health"]["available"] is True
    edges = sections["architecture"]["edges"]
    assert {"source": "shop/user_service.py", "target": "shop/payment_service.py"} in edges
    assert {"source": "web/app.js", "target": "web/util.js"} in edges
    document = sections["files"]["documents"]["shop/payment_service.py"]
    assert document["plan"]["steps"]
    assert document["history"]["commit_count"] == 2
    assert sections["report_html"] and "CodePulse AI Analysis Report" in sections["report_html"]
    assert local_repo not in str(sections)
    assert run.repo_path not in str(sections)


def test_api_flow_with_real_engine(client, auth_headers, monkeypatch, local_repo):
    real = engine_runner.run_engine
    clones = []

    def local_runner(repo_url, **kwargs):
        kwargs["check_github"] = False
        kwargs["owner"] = None
        run = real(local_repo, **kwargs)
        clones.append(run.repo_path)
        return run

    monkeypatch.setattr(engine_runner, "run_engine", local_runner)
    try:
        body = client.post("/api/repositories", json={"url": "octo/sample"}, headers=auth_headers).json()
        job = client.get(f"/api/analysis/{body['job']['id']}", headers=auth_headers).json()
        assert job["status"] == "completed", job
        repo_id = body["repository"]["id"]
        architecture = client.get(f"/api/repositories/{repo_id}/architecture", headers=auth_headers).json()
        assert architecture["edges"]
        intelligence = client.get(
            f"/api/repositories/{repo_id}/files/intelligence",
            params={"path": "shop/user_service.py"},
            headers=auth_headers,
        ).json()
        assert intelligence["related_files"][0]["file"] == "shop/payment_service.py"
        opportunities = client.get(f"/api/repositories/{repo_id}/opportunities", headers=auth_headers).json()
        assert opportunities["available"] is True
    finally:
        for path in clones:
            shutil.rmtree(path, ignore_errors=True)
