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
        "source": {"type": "table", "location": "db.srctable", "format": "iceberg"},
        "transformations": [{"name": "t1", "type": "select", "config": {"cols": ["*"]}}],
        "sink": {"type": "table", "location": "db.tgttable", "format": "iceberg"},
        "policy_profile": "default",
    }
    r = client.post("/api/v2/contracts/create", json=contract, headers=HEADERS)
    assert r.status_code == 200, r.text
    return r.json()["contract_hash"]


def test_policy_fail_blocks_build_v2(monkeypatch):
    from app.core.build_registry import BuildRegistry
    monkeypatch.setattr(BuildRegistry, "should_rebuild", lambda self, spec_hash: True)

    import app.api.endpoints.build_v2_impl as build_v2_impl_mod
    from app.core.policy.engine import PolicyEngine
    from app.core.policy.models import PolicyResult, PolicyStatus

    def always_fail(_ctx):
        return PolicyResult(
            status=PolicyStatus.FAIL,
            code="TEST_POLICY_FAIL",
            message="Failing policy for test",
        )

    monkeypatch.setattr(
        build_v2_impl_mod,
        "DEFAULT_POLICY_ENGINE",
        PolicyEngine(policies=[always_fail]),
    )

    job_name = "policy_fail_job"
    contract_hash = _create_contract_hash(job_name)

    payload = {
        "requirement": "build a pipeline",
        "job_name_hint": job_name,
        "defaults": {
            "source_table": "db.srctable",
            "target_table": "db.tgttable",
            "write_mode": "append",
            "language": "pyspark",
        },
        "options": {"contract_hash": contract_hash},
        "advisors": {},
        "dry_run": False,
        "force": False,
        "write_spec_yaml": False,
    }

    r = client.post("/build/intent", json=payload, headers=HEADERS)
    assert r.status_code == 200, r.text
    body = r.json()

    # /build/intent returns nested build_result
    assert "build_result" in body, body
    br = body["build_result"]
    policy = br.get("policy_results", [])
    assert any(p.get("code") == "TEST_POLICY_FAIL" for p in policy), br
    assert any(p.get("status") in ("FAIL", "BLOCK") for p in policy), br

    # If blocked, your build_v2_impl returns message "Policy check failed" (nested)
    assert br.get("message") == "Policy check failed"