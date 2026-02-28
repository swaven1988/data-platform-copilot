"""Tests for build approvals API and persistence."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app


HEADERS = {"Authorization": "Bearer dev_admin_token", "X-Tenant": "default"}


def test_build_approval_create_and_get(monkeypatch, tmp_path):
    from app.api.endpoints import build_approvals as approvals_mod

    monkeypatch.setattr(approvals_mod, "WORKSPACE_ROOT", tmp_path)

    c = TestClient(app)
    req = {
        "job_name": "approval_job",
        "plan_hash": "plan_123",
        "approver": "alice",
        "notes": "reviewed and approved",
        "metadata": {"ticket": "PLAT-123"},
    }
    r_create = c.post("/api/v2/build/approvals", json=req, headers=HEADERS)
    assert r_create.status_code == 200, r_create.text
    body = r_create.json()
    assert body["ok"] is True
    assert body["approval"]["job_name"] == "approval_job"
    assert body["approval"]["plan_hash"] == "plan_123"

    r_get = c.get("/api/v2/build/approvals/approval_job/plan_123", headers=HEADERS)
    assert r_get.status_code == 200, r_get.text
    got = r_get.json()
    assert got["ok"] is True
    assert got["approval"]["approver"] == "alice"


def test_build_approval_get_missing_returns_404(monkeypatch, tmp_path):
    from app.api.endpoints import build_approvals as approvals_mod

    monkeypatch.setattr(approvals_mod, "WORKSPACE_ROOT", tmp_path)

    c = TestClient(app)
    r = c.get("/api/v2/build/approvals/missing_job/missing_plan", headers=HEADERS)
    assert r.status_code == 404
    assert r.json()["detail"] == "approval_not_found"

