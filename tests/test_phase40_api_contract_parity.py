from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app


AUTH_HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


def test_audit_log_endpoint_contract(tmp_path, monkeypatch):
    audit_path = tmp_path / "audit.log"
    monkeypatch.setenv("COPILOT_AUDIT_PATH", str(audit_path))

    c = TestClient(app)
    r_seed = c.get("/api/v1/health/live", headers=AUTH_HEADERS)
    assert r_seed.status_code == 200, r_seed.text

    r = c.get("/api/v1/audit/log", headers=AUTH_HEADERS)
    assert r.status_code == 200, r.text

    body = r.json()
    assert isinstance(body, dict)
    assert "entries" in body
    assert isinstance(body["entries"], list)

    if body["entries"]:
        last = body["entries"][-1]
        assert isinstance(last, dict)
        assert "type" in last
        assert "http" in last


def test_core_endpoint_parity_smoke(tmp_path, monkeypatch):
    ws_root = tmp_path / "workspace"
    ws_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COPILOT_WORKSPACE_ROOT", str(ws_root))

    c = TestClient(app)

    # Build lifecycle endpoints used by frontend pages
    run_res = c.post(
        "/api/v2/build/run",
        params={"contract_hash": "phase40_hash"},
        json={"job_name": "phase40_job", "backend": "local"},
        headers=AUTH_HEADERS,
    )
    assert run_res.status_code == 200, run_res.text
    run_json = run_res.json()
    assert run_json.get("ok") is True
    assert isinstance(run_json.get("execution"), dict)

    status_res = c.get(
        "/api/v2/build/status/phase40_job",
        headers=AUTH_HEADERS,
    )
    assert status_res.status_code == 200, status_res.text
    status_json = status_res.json()
    assert "state" in status_json
    assert isinstance(status_json.get("execution"), dict)

    # Billing summary endpoint used by Billing page
    billing_res = c.get(
        "/api/v2/billing/summary",
        params={"month": "2026-02"},
        headers=AUTH_HEADERS,
    )
    assert billing_res.status_code == 200, billing_res.text
    billing_json = billing_res.json()
    for key in (
        "tenant",
        "month",
        "limit_usd",
        "spent_estimated_usd",
        "spent_actual_usd",
        "remaining_estimated_usd",
        "utilization_estimated",
        "entries_count",
    ):
        assert key in billing_json

    # Health/system status endpoints used by Health page
    health_res = c.get("/api/v1/health/live")
    assert health_res.status_code in (200, 204), health_res.text

    sys_res = c.get("/api/v1/system/status", headers=AUTH_HEADERS)
    assert sys_res.status_code == 200, sys_res.text
    sys_json = sys_res.json()
    assert "metrics" in sys_json
    assert "artifact" in sys_json

    # Modeling preview endpoint used by Modeling page
    modeling_res = c.get("/modeling/preview-scd2")
    assert modeling_res.status_code == 200, modeling_res.text

