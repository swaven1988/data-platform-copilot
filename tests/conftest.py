import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import app


@pytest.fixture(scope="session", autouse=True)
def _force_test_env():
    # Make runtime behave deterministically in tests
    os.environ.setdefault("COPILOT_ENV", "dev")
    # Ensure auth is OFF for test clients unless a test explicitly enables it
    os.environ.setdefault("COPILOT_AUTH_ENABLED", "0")


@pytest.fixture(scope="session")
def auth_headers():
    return {
        "Authorization": "Bearer dev_admin_token",
        "X-Tenant": "default",
        "X-Forwarded-For": "1.2.3.4",
    }


@pytest.fixture(scope="session")
def viewer_headers():
    return {
        "Authorization": "Bearer dev_viewer_token",
        "X-Tenant": "default",
        "X-Forwarded-For": "1.2.3.4",
    }


@pytest.fixture()
def client(auth_headers):
    return TestClient(app, headers=auth_headers)


@pytest.fixture()
def viewer_client(viewer_headers):
    return TestClient(app, headers=viewer_headers)


@pytest.fixture()
def tmp_repo(tmp_path: Path):
    """
    Provides a temporary git repo for tests/test_head_drift.py
    """
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo), check=True)
    (repo / "README.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), check=True)
    return repo