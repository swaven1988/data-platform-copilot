"""Tests for build approvals API and persistence."""

from __future__ import annotations

import time

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


def test_approval_revoke_removes_record(monkeypatch, tmp_path):
    from app.api.endpoints import build_approvals as mod

    monkeypatch.setattr(mod, "WORKSPACE_ROOT", tmp_path)
    c = TestClient(app)
    # create
    c.post(
        "/api/v2/build/approvals",
        json={"job_name": "rev_job", "plan_hash": "rev_hash", "approver": "alice"},
        headers=HEADERS,
    )
    # revoke
    r = c.delete("/api/v2/build/approvals/rev_job/rev_hash", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["revoked"] is True
    # now get should 404
    r2 = c.get("/api/v2/build/approvals/rev_job/rev_hash", headers=HEADERS)
    assert r2.status_code == 404


def test_approval_ttl_expiry(monkeypatch, tmp_path):
    """Approvals past TTL must not be returned by get_approval()."""
    from app.core.build_approval import BuildApprovalStore

    store = BuildApprovalStore(workspace_root=tmp_path)
    store.save_approval(job_name="j", plan_hash="h2", approver="bob")
    # Force TTL to 0 seconds
    monkeypatch.setenv("COPILOT_APPROVAL_TTL_SECONDS", "0")
    time.sleep(0.05)
    result = store.get_approval(job_name="j", plan_hash="h2")
    assert result is None, "Expired approval must not be returned"


def test_approval_list_returns_all_hashes(monkeypatch, tmp_path):
    from app.api.endpoints import build_approvals as mod

    monkeypatch.setattr(mod, "WORKSPACE_ROOT", tmp_path)
    c = TestClient(app)
    for i in range(3):
        c.post(
            "/api/v2/build/approvals",
            json={
                "job_name": "list_job",
                "plan_hash": f"hash_{i}",
                "approver": "carol",
            },
            headers=HEADERS,
        )
    r = c.get("/api/v2/build/approvals/list_job", headers=HEADERS)
    assert r.status_code == 200
    assert len(r.json()["approvals"]) == 3

