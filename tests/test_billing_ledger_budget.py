from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.billing.tenant_budget import set_tenant_limit_usd

client = TestClient(app)

AUTH_HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


def test_budget_blocks_when_monthly_limit_exceeded(tmp_path: Path):
    ws = tmp_path / "workspace" / "job_budget_1"
    ws.mkdir(parents=True, exist_ok=True)

    # Set tiny monthly budget
    set_tenant_limit_usd(workspace_dir=ws, tenant="default", limit_usd=15.0)

    # First apply: estimate 10 -> allowed
    r1 = client.post(
        "/api/v2/build/apply",
        json={"job_name": "job_budget_1", "workspace_dir": str(ws), "cost_estimate": {"estimated_total_cost_usd": 10.0}},
        params={"contract_hash": "h1"},
        headers=AUTH_HEADERS,
    )
    assert r1.status_code == 200, r1.text

    # Second apply (different job workspace to ensure spend is shared at workspace root)
    ws2 = tmp_path / "workspace" / "job_budget_2"
    ws2.mkdir(parents=True, exist_ok=True)

    r2 = client.post(
        "/api/v2/build/apply",
        json={"job_name": "job_budget_2", "workspace_dir": str(ws2), "cost_estimate": {"estimated_total_cost_usd": 10.0}},
        params={"contract_hash": "h2"},
        headers=AUTH_HEADERS,
    )
    assert r2.status_code == 409, r2.text
    j = r2.json()
    assert j["detail"]["blocked"] is True
    assert j["detail"]["decision"] == "BLOCK"
    assert "billing" in j["detail"]["details"]
