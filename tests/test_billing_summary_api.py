from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.billing.tenant_budget import set_tenant_limit_usd
from app.core.billing.ledger import utc_month_key

client = TestClient(app)

AUTH_HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


def test_billing_summary_endpoint(tmp_path: Path):
    ws1 = tmp_path / "workspace" / "job_s1"
    ws1.mkdir(parents=True, exist_ok=True)
    set_tenant_limit_usd(workspace_dir=ws1, tenant="default", limit_usd=25.0)

    r1 = client.post(
        "/api/v2/build/apply",
        json={"job_name": "job_s1", "workspace_dir": str(ws1), "cost_estimate": {"estimated_total_cost_usd": 10.0}},
        params={"contract_hash": "s1"},
        headers=AUTH_HEADERS,
    )
    assert r1.status_code == 200, r1.text

    ws2 = tmp_path / "workspace" / "job_s2"
    ws2.mkdir(parents=True, exist_ok=True)

    r2 = client.post(
        "/api/v2/build/apply",
        json={"job_name": "job_s2", "workspace_dir": str(ws2), "cost_estimate": {"estimated_total_cost_usd": 5.0}},
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
    assert j["spent_estimated_usd"] == 15.0
    assert j["entries_count"] == 2
