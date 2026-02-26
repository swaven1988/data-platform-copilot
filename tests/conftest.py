# tests/conftest.py

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import app


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    subprocess.check_call(["git", "init"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "test@example.com"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "Test User"], cwd=repo)

    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.check_call(["git", "add", "."], cwd=repo)
    subprocess.check_call(["git", "commit", "-m", "init"], cwd=repo)

    return repo