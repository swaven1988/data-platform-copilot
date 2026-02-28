"""
Phase 27 — Semantic Diff API integration tests.

Tests GET /repo/semantic-diff:
  - 404 when workspace job dir does not exist
  - 200 with correct response shape when called with a real git repo fixture
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)
HEADERS = {"Authorization": "Bearer dev_admin_token", "X-Tenant-ID": "default"}


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True
    )


def _init_git_repo(repo: Path) -> bool:
    """Create a 2-commit git repo. Returns False if git is unavailable."""
    try:
        result = subprocess.run(["git", "--version"], capture_output=True)
        if result.returncode != 0:
            return False
    except FileNotFoundError:
        return False

    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")

    # Commit 1
    (repo / "schema.json").write_text('{"version": 1}', encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")

    # Commit 2 (modified)
    (repo / "schema.json").write_text('{"version": 2}', encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "bump version")
    return True


def test_semantic_diff_404_missing_workspace(monkeypatch):
    """Returns 404 when the workspace dir for the job does not exist."""
    import app.api.endpoints.semantic_diff as sd_mod
    monkeypatch.setattr(sd_mod, "WORKSPACE_ROOT", Path("/nonexistent_root_xyz"))

    r = client.get(
        "/api/v1/repo/semantic-diff",
        params={"job_name": "no_such_job", "ref_a": "HEAD~1", "ref_b": "HEAD"},
        headers=HEADERS,
    )
    assert r.status_code == 404


def test_semantic_diff_valid_response_shape(tmp_path, monkeypatch):
    """Happy path: git repo with 2 commits → valid response shape."""
    import app.api.endpoints.semantic_diff as sd_mod
    monkeypatch.setattr(sd_mod, "WORKSPACE_ROOT", tmp_path)

    job_name = "semantic_test_job"
    repo_path = tmp_path / job_name

    if not _init_git_repo(repo_path):
        pytest.skip("git not available in this environment")

    r = client.get(
        "/api/v1/repo/semantic-diff",
        params={"job_name": job_name, "ref_a": "HEAD~1", "ref_b": "HEAD"},
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "ref_a" in body
    assert "ref_b" in body
    assert "files" in body
    assert "file_count" in body
    assert isinstance(body["files"], list)
    assert body["file_count"] >= 1


def test_semantic_diff_with_path_filter(tmp_path, monkeypatch):
    """Path filter parameter is accepted without error."""
    import app.api.endpoints.semantic_diff as sd_mod
    monkeypatch.setattr(sd_mod, "WORKSPACE_ROOT", tmp_path)

    job_name = "semantic_filter_job"
    repo_path = tmp_path / job_name

    if not _init_git_repo(repo_path):
        pytest.skip("git not available in this environment")

    r = client.get(
        "/api/v1/repo/semantic-diff",
        params={
            "job_name": job_name,
            "ref_a": "HEAD~1",
            "ref_b": "HEAD",
            "paths": "schema.json",
        },
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["scoped_paths"] == ["schema.json"]
