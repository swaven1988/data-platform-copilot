# tests/test_execution_policy_enforcement.py
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)

AUTH_HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


def test_apply_blocks_when_cost_too_high(tmp_path: Path):
    # workspace under tmp
    ws = tmp_path / "workspace" / "job_block"
    ws.mkdir(parents=True, exist_ok=True)

    body = {
        "job_name": "job_block",
        "workspace_dir": str(ws),
        "cost_estimate": {
            "estimated_total_cost_usd": 9999.0,
            "confidence": 0.9,
            "assumptions": {"test": True},
        },
    }

    r = client.post("/api/v2/build/apply", json=body, params={"contract_hash": "h1"}, headers=AUTH_HEADERS)
    assert r.status_code == 409, r.text
    j = r.json()
    assert j["detail"]["blocked"] is True
    assert j["detail"]["decision"] == "BLOCK"


def test_apply_warn_allows_continue(tmp_path: Path):
    ws = tmp_path / "workspace" / "job_warn"
    ws.mkdir(parents=True, exist_ok=True)

    # cost under threshold -> allow
    body = {
        "job_name": "job_warn",
        "workspace_dir": str(ws),
        "cost_estimate": {
            "estimated_total_cost_usd": 10.0,
            "confidence": 0.9,
            "assumptions": {"test": True},
        },
    }

    r = client.post("/api/v2/build/apply", json=body, params={"contract_hash": "h2"}, headers=AUTH_HEADERS)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"] is True
    assert out["execution"]["state"] == "APPLIED"