from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)

AUTH_HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}

def test_build_blocks_on_high_risk(monkeypatch):
    from app.core.build_registry import BuildRegistry
    monkeypatch.setattr(BuildRegistry, "should_rebuild", lambda self, spec_hash: True)

    contract_hash = "dummy_hash"

    body = {
        "spec": {
            "job_name": "block_job",
            "language": "pyspark",
            "source_table": "db.srctable",
            "target_table": "db.tgttable",
            "write_mode": "append",
        },
        "options": {
            "preflight": {
                "enabled": True,
                "job_name": "block_job",
                "runtime_profile": "aws_emr_yarn_default",
                "dataset": {"estimated_input_gb": 800, "shuffle_multiplier": 6.0},
                "pricing": {"cost_per_executor_hour": 5.0, "executors": 1},
                "sla": {"max_runtime_minutes": 5},
            }
        },
    }

    build_path = _pick_build_v2_path()
    r = client.post(build_path, json=body, params={"contract_hash": contract_hash}, headers=AUTH_HEADERS)

    assert "Build V1" not in r.text, r.text
    assert r.status_code == 400, r.text

def test_build_warn_allows_continue(monkeypatch):
    from app.core.build_registry import BuildRegistry
    monkeypatch.setattr(BuildRegistry, "should_rebuild", lambda self, spec_hash: True)

    contract_hash = "dummy_hash"

    body = {
        "spec": {
            "job_name": "warn_job",
            "language": "pyspark",
            "source_table": "db.srctable",
            "target_table": "db.tgttable",
            "write_mode": "append",
        },
        "options": {
            "preflight": {
                "enabled": True,
                "job_name": "warn_job",
                "runtime_profile": "aws_emr_yarn_default",
                "dataset": {"estimated_input_gb": 200, "shuffle_multiplier": 2.0},
                "pricing": {"cost_per_executor_hour": 3.0, "executors": 2},
                "sla": {"max_runtime_minutes": 60},
            }
        },
    }

    build_path = _pick_build_v2_path()
    r = client.post(build_path, json=body, params={"contract_hash": contract_hash}, headers=AUTH_HEADERS)

    assert "Build V1" not in r.text, r.text
    assert r.status_code != 401, r.text
    assert r.status_code != 422, r.text


def _pick_build_v2_path():
    # prefer the v2 build endpoint if exposed
    paths = app.openapi().get("paths", {})
    candidates = [
        "/api/v2/build/v2",
        "/api/v2/build",
        "/build/v2",
        "/api/v2/build/intent",  # unlikely but safe
    ]
    for p in candidates:
        if p in paths and "post" in paths[p]:
            return p
    raise AssertionError(f"No build v2 path found in OpenAPI. Available: {sorted(paths.keys())[:50]}")