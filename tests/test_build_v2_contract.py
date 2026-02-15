from fastapi.testclient import TestClient

from app.api.main import app


def test_build_v2_contract_minimal_response_shape():
    client = TestClient(app)

    payload = {
        "spec": {
            "job_name": "contract_job_v2",
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

    r = client.post("/build/v2?include_intelligence=false", json=payload)
    assert r.status_code == 200

    body = r.json()
    assert isinstance(body, dict)

    # Required keys (contract)
    assert "message" in body
    assert "job_name" in body
    assert "spec_hash" in body
    assert "plan_id" in body
    assert "events" in body
    assert "advisor_findings" in body
    assert "policy_results" in body

    assert isinstance(body["message"], str)
    assert body["job_name"] == "contract_job_v2"
    assert isinstance(body["spec_hash"], str)
    assert len(body["spec_hash"]) == 64

    assert isinstance(body["plan_id"], str)
    assert isinstance(body["events"], list)
    assert isinstance(body["advisor_findings"], list)
    assert isinstance(body["policy_results"], list)

    # Optional behavior key (present only on skip path today)
    if "skipped" in body:
        assert isinstance(body["skipped"], bool)

    # Build-path keys (present when not skipped)
    if body.get("skipped") is False or "skipped" not in body:
        assert "workspace_dir" in body
        assert "files" in body
        assert "baseline_commit" in body

        assert isinstance(body["workspace_dir"], str)
        assert isinstance(body["files"], list)
        assert isinstance(body["baseline_commit"], str)
