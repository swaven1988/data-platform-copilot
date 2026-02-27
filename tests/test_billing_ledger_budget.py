from pathlib import Path
from fastapi.testclient import TestClient
from app.api.main import app
from app.core.billing.tenant_budget import set_tenant_limit_usd

AUTH_HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


def test_budget_blocks_when_monthly_limit_exceeded(tmp_path, monkeypatch):
    # Redirect DEFAULT_WORKSPACE to tmp_path for this test
    ws_root = tmp_path / "workspace"
    ws_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COPILOT_WORKSPACE_ROOT", str(ws_root))

    # Force execution.py to reload DEFAULT_WORKSPACE from env
    import app.api.endpoints.execution as _ex_mod
    import importlib
    importlib.reload(_ex_mod)

    ws1 = ws_root / "job_budget_1"
    ws1.mkdir(parents=True, exist_ok=True)

    # Set tiny monthly budget
    set_tenant_limit_usd(workspace_dir=ws1, tenant="default", limit_usd=15.0)

    client = TestClient(app)

    r1 = client.post(
        "/api/v2/build/apply",
        json={"job_name": "job_budget_1", "cost_estimate": {"estimated_total_cost_usd": 10.0}},
        params={"contract_hash": "h1"},
        headers=AUTH_HEADERS,
    )
    assert r1.status_code == 200, r1.text

    r2 = client.post(
        "/api/v2/build/apply",
        json={"job_name": "job_budget_2", "cost_estimate": {"estimated_total_cost_usd": 10.0}},
        params={"contract_hash": "h2"},
        headers=AUTH_HEADERS,
    )
    assert r2.status_code == 409, r2.text
    j = r2.json()
    assert j["detail"]["blocked"] is True
    assert j["detail"]["decision"] == "BLOCK"
    assert "billing" in j["detail"]["details"]
