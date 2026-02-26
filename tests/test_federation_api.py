import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _git_available(), reason="git not available")
def test_federation_connect_and_config(tmp_path, monkeypatch):
    # Point WORKSPACE_ROOT to tmp workspace by monkeypatching env via module reload pattern
    # Minimal approach: create a fake workspace folder at repo workspace path if needed.
    # This test focuses on API contract presence and returns; it does not require network.
    # Create a local git repo to federate.
    repo = tmp_path / "remote_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo), check=True)
    (repo / "hello.txt").write_text("hi", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), check=True)

    # Ensure job workspace exists
    project_root = Path(__file__).resolve().parents[1]
    ws = project_root / "workspace" / "job_fed_test" / ".copilot"
    ws.mkdir(parents=True, exist_ok=True)

    r = client.post(
        "/federation/connect",
        json={
            "job_name": "job_fed_test",
            "name": "templates",
            "url": str(repo),
            "ref": "HEAD",
            "sync": True,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["job_name"] == "job_fed_test"
    assert "config" in data
    assert "sync_result" in data
    assert data["sync_result"]["name"] == "templates"

    r2 = client.get("/federation/config", params={"job_name": "job_fed_test"})
    assert r2.status_code == 200
    cfg = r2.json()
    assert cfg["kind"] == "federation_config"
    assert any(x["name"] == "templates" for x in cfg["repos"])
