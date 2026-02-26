from fastapi.testclient import TestClient

from app.api.main import app


def test_build_intent_dry_run_contract_shape():
    client = TestClient(app)

    payload = {
        "requirement": "job name: contract_intent_job env=dev read from raw_db.t1 write to curated_db.t2 partition by data_dt append schedule: 0 6 * * * timezone: UTC pyspark",
        "job_name_hint": "contract_intent_job",
        "defaults": {
            "source_table": "raw_db.t1",
            "target_table": "curated_db.t2",
            "write_mode": "append",
            "language": "pyspark",
        },
        "write_spec_yaml": False,
        "dry_run": True,
        "explain": False,
        "options": {"include_intelligence": False},
        "advisors": {},
        "force": False,
    }

    r = client.post("/build/intent", json=payload)
    assert r.status_code == 200

    body = r.json()
    assert isinstance(body, dict)

    # Required keys (contract)
    assert "message" in body
    assert "parsed_spec" in body
    assert "warnings" in body
    assert "spec_hash" in body
    assert "plugin_fingerprint" in body
    assert "advisor_findings" in body

    # Type checks
    assert isinstance(body["message"], str)
    assert isinstance(body["parsed_spec"], dict)
    assert isinstance(body["warnings"], list)
    assert isinstance(body["spec_hash"], str)
    assert len(body["spec_hash"]) == 64
    assert isinstance(body["plugin_fingerprint"], str)
    assert isinstance(body["advisor_findings"], list)

    # Parsed spec must include identity + IO + language at minimum
    ps = body["parsed_spec"]
    assert ps.get("job_name") == "contract_intent_job"
    assert isinstance(ps.get("source_table"), str) and "." in ps["source_table"]
    assert isinstance(ps.get("target_table"), str) and "." in ps["target_table"]
    assert ps.get("language") in ("pyspark", "scala")
    assert ps.get("write_mode") in ("merge", "append", "overwrite")
