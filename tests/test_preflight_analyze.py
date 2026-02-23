from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)

AUTH_HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


def test_preflight_deterministic():
    payload = {
        "job_name": "test_job",
        "runtime_profile": "aws_emr_yarn_default",
        "dataset": {"estimated_input_gb": 50, "shuffle_multiplier": 2.0},
        "pricing": {"cost_per_executor_hour": 1.0, "executors": 4},
        "sla": {"max_runtime_minutes": 120},
    }

    r1 = client.post("/api/v2/preflight/analyze", json=payload, headers=AUTH_HEADERS)
    r2 = client.post("/api/v2/preflight/analyze", json=payload, headers=AUTH_HEADERS)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["preflight_hash"] == r2.json()["preflight_hash"]


def test_preflight_block():
    payload = {
        "job_name": "risk_job",
        "runtime_profile": "aws_emr_yarn_default",
        "dataset": {"estimated_input_gb": 500, "shuffle_multiplier": 5.0},
        "pricing": {"cost_per_executor_hour": 5.0, "executors": 2},
        "sla": {"max_runtime_minutes": 10},
    }

    r = client.post("/api/v2/preflight/analyze", json=payload, headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert r.json()["policy_decision"] in ["WARN", "BLOCK"]