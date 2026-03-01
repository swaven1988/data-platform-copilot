from pathlib import Path
from fastapi.testclient import TestClient
from app.api.main import app
from app.core.billing.tenant_budget import set_tenant_limit_usd
from app.core.billing.ledger import utc_month_key

AUTH_HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


def test_billing_summary_endpoint(tmp_path, monkeypatch):
    ws_root = tmp_path / "workspace"
    ws_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COPILOT_WORKSPACE_ROOT", str(ws_root))

    import app.api.endpoints.execution as _ex_mod
    import importlib
    importlib.reload(_ex_mod)

    ws1 = ws_root / "job_s1"
    ws1.mkdir(parents=True, exist_ok=True)
    set_tenant_limit_usd(workspace_dir=ws1, tenant="default", limit_usd=25.0)

    client = TestClient(app)

    r1 = client.post(
        "/api/v2/build/apply",
        json={"job_name": "job_s1", "cost_estimate": {"estimated_total_cost_usd": 10.0}},
        params={"contract_hash": "s1"},
        headers=AUTH_HEADERS,
    )
    assert r1.status_code == 200, r1.text

    r2 = client.post(
        "/api/v2/build/apply",
        json={"job_name": "job_s2", "cost_estimate": {"estimated_total_cost_usd": 5.0}},
        params={"contract_hash": "s2"},
        headers=AUTH_HEADERS,
    )
    assert r2.status_code == 200, r2.text

    m = utc_month_key()
    rs = client.get(
        "/api/v2/billing/summary",
        params={"workspace_dir": str(ws1), "month": m},
        headers=AUTH_HEADERS,
    )
    assert rs.status_code == 200, rs.text
    j = rs.json()
    assert j["tenant"] == "default"
    assert j["month"] == m
    assert j["limit_usd"] == 25.0
    assert j["entries_count"] >= 1


def test_billing_summary_includes_ai_by_task(tmp_path, monkeypatch):
    import importlib

    monkeypatch.setenv("COPILOT_WORKSPACE_ROOT", str(tmp_path))
    import app.api.endpoints.billing as billing_mod

    monkeypatch.setattr(billing_mod, "DEFAULT_WORKSPACE_ROOT", tmp_path)

    from app.core.billing.ledger import LedgerStore, utc_month_key
    from app.core.billing.tenant_budget import set_tenant_limit_usd

    ws = tmp_path / "__billing__"
    set_tenant_limit_usd(workspace_dir=ws, tenant="default", limit_usd=100.0)
    ledger = LedgerStore(workspace_dir=ws)
    month = utc_month_key()
    for job, cost in [("ai_intent_gapfill", 0.05), ("ai_failure_triage", 0.02)]:
        ledger.upsert_actual(
            tenant="default",
            month=month,
            job_name=job,
            build_id=job,
            actual_cost_usd=cost,
            actual_runtime_seconds=None,
            finished_ts="2026-01-01T00:00:00Z",
        )

    from fastapi.testclient import TestClient
    from app.api.main import app

    c = TestClient(app)
    r = c.get(
        "/api/v2/billing/summary",
        headers={"Authorization": "Bearer dev_admin_token", "X-Tenant": "default"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "ai_by_task" in body
    assert "ai_intent_gapfill" in body["ai_by_task"]
    assert "ai_failure_triage" in body["ai_by_task"]
