from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)

HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


def _create_contract_hash(job_name: str) -> str:
    contract = {
        "job_name": job_name,
        "compute_profile": {
            "engine": "spark",
            "spark_version": "3.5.0",
            "cluster_mode": "yarn",
            "cloud": "aws",
        },
        "source": {"type": "table", "location": "raw_db.source_table", "format": "iceberg"},
        "transformations": [{"name": "t1", "type": "select", "config": {"cols": ["*"]}}],
        "sink": {"type": "table", "location": "curated_db.target_table", "format": "iceberg"},
        "sla": {"max_runtime_minutes": 60, "freshness_minutes": 1440},
        "policy_profile": "default",
    }

    r = client.post("/api/v2/contracts/create", json=contract, headers=HEADERS)
    assert r.status_code == 200, r.text
    return r.json()["contract_hash"]


def test_build_v2_contract_minimal_response_shape():
    job_name = "contract_job_v2"
    contract_hash = _create_contract_hash(job_name)

    payload = {
        "spec": {
            "job_name": job_name,
            "preset": "generic",
            "owner": "data-platform",
            "env": "dev",
            "schedule": "0 6 * * *",
            "timezone": "UTC",
            "description": "contract test",
            "tags": ["copilot", "contract"],
            "source_table": "raw_db.source_table",
            "target_table": "curated_db.target_table",
            "partition_column": "data_dt",
            "write_mode": "append",
            "language": "pyspark",
            "spark_dynamic_allocation": True,
            "spark_conf_overrides": {},
            "dq_enabled": False,
            "troubleshoot_enabled": False,
        },
        "write_spec_yaml": False,
        "job_name_override": None,
    }

    r = client.post(
        f"/build/v2?include_intelligence=false&contract_hash={contract_hash}",
        json=payload,
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text

    body = r.json()
    assert body.get("job_name") == job_name
    assert "spec_hash" in body
    assert "policy_results" in body