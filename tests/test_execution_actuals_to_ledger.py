from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.billing.tenant_budget import set_tenant_limit_usd
from app.core.billing.ledger import LedgerStore, utc_month_key

client = TestClient(app)

AUTH_HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


def test_terminal_status_writes_actuals_to_ledger(tmp_path: Path):
    ws = tmp_path / "workspace" / "job_a1"
    ws.mkdir(parents=True, exist_ok=True)

    set_tenant_limit_usd(workspace_dir=ws, tenant="default", limit_usd=999.0)

    # apply with estimate
    r1 = client.post(
        "/api/v2/build/apply",
        json={"job_name": "job_a1", "workspace_dir": str(ws), "cost_estimate": {"estimated_total_cost_usd": 3.0}},
        params={"contract_hash": "a1"},
        headers=AUTH_HEADERS,
    )
    assert r1.status_code == 200, r1.text

    # run -> RUNNING
    r2 = client.post(
        "/api/v2/build/run",
        json={"job_name": "job_a1", "workspace_dir": str(ws), "backend": "local"},
        params={"contract_hash": "a1"},
        headers=AUTH_HEADERS,
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["execution"]["state"] == "RUNNING"

    # poll status -> SUCCEEDED (local backend returns SUCCEEDED)
    r3 = client.get(
        "/api/v2/build/status/job_a1",
        params={"workspace_dir": str(ws)},
        headers=AUTH_HEADERS,
    )
    assert r3.status_code == 200, r3.text
    assert r3.json()["state"] == "SUCCEEDED"

    # ledger should now include actual fields on the estimate entry
    m = utc_month_key()
    ledger = LedgerStore(workspace_dir=ws)
    obj = ledger._load()  # test-only usage
    entries = obj.get("entries", [])
    assert isinstance(entries, list) and len(entries) == 1
    e = entries[0]
    assert e["tenant"] == "default"
    assert e["month"] == m
    assert e["estimated_cost_usd"] == 3.0
    assert e.get("actual_cost_usd") == 3.0
    assert isinstance(e.get("actual_runtime_seconds"), (int, float))
    assert isinstance(e.get("finished_ts"), str)
