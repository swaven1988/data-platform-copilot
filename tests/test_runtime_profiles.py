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
        "source": {"type": "table", "location": "db.src", "format": "iceberg"},
        "transformations": [{"name": "t1", "type": "select", "config": {"cols": ["*"]}}],
        "sink": {"type": "table", "location": "db.dst", "format": "iceberg"},
        "policy_profile": "default",
    }

    r = client.post("/api/v2/contracts/create", json=contract, headers=HEADERS)
    assert r.status_code == 200, r.text
    return r.json()["contract_hash"]


def test_runtime_profiles_list_get_resolve():
    r = client.get("/api/v2/runtime-profiles/", headers=HEADERS)
    assert r.status_code == 200, r.text
    names = r.json().get("profiles")
    assert isinstance(names, list)
    assert "aws_emr_yarn_default" in names

    r2 = client.get("/api/v2/runtime-profiles/aws_emr_yarn_default", headers=HEADERS)
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["name"] == "aws_emr_yarn_default"
    assert body["cloud"] == "aws"

    job_name = "rp_job"
    contract_hash = _create_contract_hash(job_name)

    r3 = client.post(
        "/api/v2/runtime-profiles/resolve",
        json={
            "job_name": job_name,
            "contract_hash": contract_hash,
            "profile_name": "aws_emr_yarn_default",
            "pricing_overrides": {"instance_hourly_rate": 0.5},
        },
        headers=HEADERS,
    )
    assert r3.status_code == 200, r3.text
    out = r3.json()
    assert out["runtime_profile"] == "aws_emr_yarn_default"
    assert out["cluster_profile"]["instance_hourly_rate"] == 0.5
    assert "conf" in out["spark_conf"]