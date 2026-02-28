"""
Phase 22 — Workspace Repro & Verify endpoint smoke tests.

Tests:
  - GET /workspace/repro/manifest → 404 on missing workspace
  - GET /workspace/repro/manifest → 200 with {kind, job_name, files} on existing workspace

Route is registered at /workspace/repro/manifest (no /api/v1 prefix).
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)
HEADERS = {"Authorization": "Bearer dev_admin_token", "X-Tenant-ID": "default"}

_REPRO_PATCH  = "app.api.endpoints.workspace_repro.build_repro_manifest"
_DICT_PATCH   = "app.api.endpoints.workspace_repro.manifest_to_json_dict"
MANIFEST_URL  = "/workspace/repro/manifest"


def _fake_manifest(job_name: str) -> MagicMock:
    m = MagicMock()
    m.kind = "repro"
    m.job_name = job_name
    m.workspace_root = "/tmp/ws"
    m.includes = []
    m.files = []
    return m


def _fake_dict(job_name: str) -> dict:
    return {
        "kind": "repro",
        "job_name": job_name,
        "workspace_root": "/tmp/ws",
        "includes": [],
        "files": [],
    }


def test_workspace_repro_manifest_404_missing_job():
    """Returns 404 when build_repro_manifest raises FileNotFoundError."""
    with patch(_REPRO_PATCH, side_effect=FileNotFoundError("workspace not found")):
        r = client.get(
            MANIFEST_URL,
            params={"job_name": "totally_missing_job_xyz"},
            headers=HEADERS,
        )
    assert r.status_code == 404


def test_workspace_repro_manifest_200_with_fixture():
    """Happy path: build_repro_manifest succeeds → 200 with expected keys."""
    job_name = "repro_test_job"
    with (
        patch(_REPRO_PATCH, return_value=_fake_manifest(job_name)),
        patch(_DICT_PATCH, return_value=_fake_dict(job_name)),
    ):
        r = client.get(
            MANIFEST_URL,
            params={"job_name": job_name},
            headers=HEADERS,
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["job_name"] == job_name
    assert "files" in body
    assert isinstance(body["files"], list)


def test_workspace_repro_manifest_includes_param():
    """The includes query param is forwarded correctly to build_repro_manifest."""
    job_name = "repro_includes_job"
    captured = []

    def _capture(workspace_root, job_name, includes=None):
        captured.append(includes)
        return _fake_manifest(job_name)

    with (
        patch(_REPRO_PATCH, side_effect=_capture),
        patch(_DICT_PATCH, return_value=_fake_dict(job_name)),
    ):
        r = client.get(
            MANIFEST_URL,
            params={"job_name": job_name, "includes": "jobs,configs"},
            headers=HEADERS,
        )
    assert r.status_code == 200, r.text
    assert captured[0] == ["jobs", "configs"]
