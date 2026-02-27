from pathlib import Path
from fastapi.testclient import TestClient
from app.api.main import app
from app.core.billing.tenant_budget import set_tenant_limit_usd
from app.core.billing.ledger import LedgerStore, utc_month_key

AUTH_HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


def test_terminal_status_writes_actuals_to_ledger(tmp_path, monkeypatch):
    ws_root = tmp_path / "workspace"
    ws_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COPILOT_WORKSPACE_ROOT", str(ws_root))

    import app.api.endpoints.execution as _ex_mod
    import importlib
    importlib.reload(_ex_mod)

    job = "job_a1"
    ws = ws_root / job
    ws.mkdir(parents=True, exist_ok=True)

    set_tenant_limit_usd(workspace_dir=ws, tenant="default", limit_usd=999.0)

    client = TestClient(app)

    r1 = client.post(
        "/api/v2/build/apply",
        json={"job_name": job, "cost_estimate": {"estimated_total_cost_usd": 3.0}},
        params={"contract_hash": "a1"},
        headers=AUTH_HEADERS,
    )
    assert r1.status_code == 200, r1.text

    r2 = client.post(
        "/api/v2/build/run",
        json={"job_name": job, "backend": "local"},
        params={"contract_hash": "a1"},
        headers=AUTH_HEADERS,
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["execution"]["state"] == "RUNNING"

    r3 = client.get(f"/api/v2/build/status/{job}", headers=AUTH_HEADERS)
    assert r3.status_code == 200, r3.text
    assert r3.json()["state"] == "SUCCEEDED"

    m = utc_month_key()
    ledger = LedgerStore(workspace_dir=ws)
    obj = ledger._load()
    entries = obj.get("entries", [])
    assert isinstance(entries, list) and len(entries) >= 1
    e = entries[0]
    assert e["tenant"] == "default"
    assert e["month"] == m
    assert e.get("estimated_cost_usd") == 3.0
