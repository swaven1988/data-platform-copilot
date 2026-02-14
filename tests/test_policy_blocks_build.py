from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)


def test_policy_fail_blocks_build_v2(monkeypatch):
    from app.core.build_registry import BuildRegistry
    monkeypatch.setattr(BuildRegistry, "should_rebuild", lambda self, spec_hash: True)

    import app.api.endpoints.build_v2_impl as build_v2_impl_mod
    from app.core.policy.engine import PolicyEngine
    from app.core.policy.models import PolicyResult, PolicyStatus

    def always_fail(_ctx):
        return PolicyResult(status=PolicyStatus.FAIL, code="TEST_POLICY_FAIL", message="Failing policy for test")

    monkeypatch.setattr(build_v2_impl_mod, "DEFAULT_POLICY_ENGINE", PolicyEngine(policies=[always_fail]))

    payload = {
        "requirement": "build a pipeline",
        "job_name_hint": "policy_fail_job",
        "defaults": {
            "source_table": "db.srctable",
            "target_table": "db.tgttable",
            "write_mode": "append",
            "language": "pyspark",
        },
        "options": {},
        "advisors": {},
        "dry_run": False,
        "force": False,
        "write_spec_yaml": False,
    }

    r = client.post("/build/intent", json=payload)
    assert r.status_code == 200
    build_result = (r.json().get("build_result") or {})
    assert build_result.get("message") == "Policy check failed"
    assert any(pr.get("code") == "TEST_POLICY_FAIL" for pr in build_result.get("policy_results", []))