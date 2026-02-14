from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)


def test_policy_warn_does_not_block_build(monkeypatch):
    # Force rebuild path
    from app.core.build_registry import BuildRegistry
    monkeypatch.setattr(BuildRegistry, "should_rebuild", lambda self, spec_hash: True)

    # Patch policy engine used by build_v2_impl
    import app.api.endpoints.build_v2_impl as build_v2_impl_mod
    from app.core.policy.engine import PolicyEngine
    from app.core.policy.models import PolicyResult, PolicyStatus

    def always_warn(_ctx):
        return PolicyResult(
            status=PolicyStatus.WARN,
            code="TEST_POLICY_WARN",
            message="Warning policy for test",
        )

    monkeypatch.setattr(build_v2_impl_mod, "DEFAULT_POLICY_ENGINE", PolicyEngine(policies=[always_warn]))

    payload = {
        "requirement": "build a pipeline",
        "job_name_hint": "policy_warn_job",
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
    body = r.json()

    build_result = body.get("build_result") or {}
    assert build_result.get("message") == "Build V2 completed"

    prs = build_result.get("policy_results") or []
    assert any(pr.get("code") == "TEST_POLICY_WARN" for pr in prs)
