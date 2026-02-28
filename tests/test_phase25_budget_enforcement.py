"""Phase 25 tests: monthly budget hard enforcement and billing AI breakdown."""

from __future__ import annotations

import importlib

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.billing.ledger import LedgerStore, utc_month_key
from app.core.billing.tenant_budget import set_tenant_limit_usd


AUTH_HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


def test_apply_blocks_when_budget_already_exhausted(tmp_path, monkeypatch):
    ws_root = tmp_path / "workspace"
    ws_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COPILOT_WORKSPACE_ROOT", str(ws_root))

    import app.api.endpoints.execution as _ex_mod

    importlib.reload(_ex_mod)

    ws1 = ws_root / "job_budget_exhausted"
    ws1.mkdir(parents=True, exist_ok=True)

    month = utc_month_key()
    set_tenant_limit_usd(workspace_dir=ws1, tenant="default", limit_usd=10.0)

    ledger = LedgerStore(workspace_dir=ws1)
    ledger.upsert_estimate(
        tenant="default",
        month=month,
        job_name="seed_job",
        build_id="seed_build",
        estimated_cost_usd=10.0,
    )

    client = TestClient(app)
    r = client.post(
        "/api/v2/build/apply",
        json={"job_name": "job_budget_exhausted", "cost_estimate": {"estimated_total_cost_usd": 1.0}},
        params={"contract_hash": "h_exhausted"},
        headers=AUTH_HEADERS,
    )

    assert r.status_code == 409, r.text
    body = r.json()["detail"]
    assert body["decision"] == "BLOCK"
    assert "billing" in body["details"]


def test_apply_warns_when_budget_near_limit(tmp_path, monkeypatch):
    ws_root = tmp_path / "workspace"
    ws_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COPILOT_WORKSPACE_ROOT", str(ws_root))

    import app.api.endpoints.execution as _ex_mod

    importlib.reload(_ex_mod)

    ws1 = ws_root / "job_budget_warn"
    ws1.mkdir(parents=True, exist_ok=True)

    month = utc_month_key()
    set_tenant_limit_usd(workspace_dir=ws1, tenant="default", limit_usd=100.0)

    ledger = LedgerStore(workspace_dir=ws1)
    ledger.upsert_estimate(
        tenant="default",
        month=month,
        job_name="seed_job",
        build_id="seed_warn",
        estimated_cost_usd=79.0,
    )

    client = TestClient(app)
    r = client.post(
        "/api/v2/build/apply",
        json={"job_name": "job_budget_warn", "cost_estimate": {"estimated_total_cost_usd": 1.0}},
        params={"contract_hash": "h_warn"},
        headers=AUTH_HEADERS,
    )

    assert r.status_code == 200, r.text
    out = r.json()
    assert out["decision"] == "WARN"


def test_billing_summary_includes_ai_breakdown_fields(tmp_path, monkeypatch):
    ws_root = tmp_path / "workspace"
    ws_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COPILOT_WORKSPACE_ROOT", str(ws_root))

    import app.api.endpoints.execution as _ex_mod

    importlib.reload(_ex_mod)

    ws1 = ws_root / "job_billing_breakdown"
    ws1.mkdir(parents=True, exist_ok=True)

    month = utc_month_key()
    set_tenant_limit_usd(workspace_dir=ws1, tenant="default", limit_usd=100.0)

    ledger = LedgerStore(workspace_dir=ws1)
    ledger.upsert_estimate(
        tenant="default",
        month=month,
        job_name="job_billing_breakdown",
        build_id="b1",
        estimated_cost_usd=20.0,
    )
    ledger.upsert_actual(
        tenant="default",
        month=month,
        job_name="job_billing_breakdown",
        build_id="b1",
        actual_cost_usd=5.0,
        actual_runtime_seconds=12.0,
        finished_ts="2026-01-01T00:00:00Z",
    )
    ledger.upsert_actual(
        tenant="default",
        month=month,
        job_name="ai_intent_gapfill",
        build_id="b2",
        actual_cost_usd=2.0,
        actual_runtime_seconds=2.0,
        finished_ts="2026-01-01T00:00:10Z",
    )

    client = TestClient(app)
    r = client.get(
        "/api/v2/billing/summary",
        params={"workspace_dir": str(ws1), "month": month},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["spent_actual_usd"] == 7.0
    assert body["ai_spent_actual_usd"] == 2.0
    assert body["non_ai_spent_actual_usd"] == 5.0
    assert body["budget_status"] in {"ok", "warning", "exceeded"}

