from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)

HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


def test_contract_plan_intelligence_policy_build_flow_allow_and_block():
    job_name = "it_job_compiler_flow"

    # 1) CONTRACT
    contract = {
        "job_name": job_name,
        "compute_profile": {
            "engine": "spark",
            "spark_version": "3.5.0",
            "cluster_mode": "yarn",
            "cloud": "aws",
        },
        "source": {"type": "table", "location": "db.src", "format": "iceberg"},
        "transformations": [
            {"name": "t1", "type": "select", "config": {"cols": ["a", "b"]}},
            {"name": "t2", "type": "join", "config": {"on": ["id"], "how": "left"}},
            {"name": "t3", "type": "aggregate", "config": {"group_by": ["a"]}},
        ],
        "sink": {"type": "table", "location": "db.dst", "format": "iceberg"},
        "sla": {"max_runtime_minutes": 60, "freshness_minutes": 1440},
        "policy_profile": "default",
    }

    r = client.post("/api/v2/contracts/create", json=contract, headers=HEADERS)
    assert r.status_code == 200, r.text
    contract_hash = r.json()["contract_hash"]

    # Determinism: same content -> same hash
    r2 = client.post("/api/v2/contracts/create", json=contract, headers=HEADERS)
    assert r2.status_code == 200, r2.text
    assert r2.json()["contract_hash"] == contract_hash

    r = client.get(f"/api/v2/contracts/{job_name}/{contract_hash}", headers=HEADERS)
    assert r.status_code == 200, r.text
    assert r.json()["job_name"] == job_name

    # 2) PLAN
    params = {
        "job_name": job_name,
        "contract_hash": contract_hash,
        "plugin_fingerprint": "core",
        "policy_profile": "default",
    }
    r = client.post("/api/v2/plans/create", params=params, headers=HEADERS)
    assert r.status_code == 200, r.text
    plan_hash = r.json()["plan_hash"]

    r = client.get(f"/api/v2/plans/{job_name}/{plan_hash}", headers=HEADERS)
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan["job_name"] == job_name
    assert plan["metadata"]["contract_hash"] == contract_hash
    assert plan["metadata"]["plugin_fingerprint"] == "core"
    assert plan["metadata"]["policy_profile"] == "default"
    assert len(plan["physical_stages"]) == len(contract["transformations"])

    # 3) INTELLIGENCE
    cluster_profile = {
        "executor_instances": 10,
        "executor_cores": 4,
        "executor_memory_gb": 8,
        "instance_hourly_rate": 0.25,  # injected pricing
    }

    r = client.post(
        "/api/v2/intelligence/analyze",
        params={"job_name": job_name, "plan_hash": plan_hash},
        json=cluster_profile,
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text
    intelligence_hash = r.json()["intelligence_hash"]

    r = client.get(f"/api/v2/intelligence/{job_name}/{intelligence_hash}", headers=HEADERS)
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["plan_hash"] == plan_hash
    assert isinstance(report["runtime_estimate_minutes"], (int, float))
    assert isinstance(report["cost_estimate_usd"], (int, float))
    assert 0.0 <= report["failure_probability"] <= 1.0
    assert 0 <= report["risk_score"] <= 100
    assert report["risk_level"] in ("LOW", "MEDIUM", "HIGH")

    # 4) POLICY EVAL (ALLOW/WARN)
    thresholds_allow = {
        "max_cost_usd": 999999.0,
        "max_risk_score": 100,
        "max_failure_probability": 1.0,
        "min_confidence_score": 0.0,
        "mode": "balanced",
    }

    r = client.post(
        "/api/v2/policy/evaluate",
        params={
            "job_name": job_name,
            "contract_hash": contract_hash,
            "plan_hash": plan_hash,
            "intelligence_hash": intelligence_hash,
        },
        json=thresholds_allow,
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text
    allow_eval = r.json()
    assert allow_eval["decision"] in ("ALLOW", "WARN")
    policy_eval_hash_allow = allow_eval["policy_eval_hash"]

    # 5) BUILD (ALLOW/WARN should pass)
    r = client.post(
        "/api/v3/build/run",
        params={
            "job_name": job_name,
            "contract_hash": contract_hash,
            "plan_hash": plan_hash,
            "intelligence_hash": intelligence_hash,
            "policy_eval_hash": policy_eval_hash_allow,
        },
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["build_id"]
    assert out["decision"] in ("ALLOW", "WARN")
    assert "lineage" in out

    # 4b) POLICY EVAL (BLOCK)
    thresholds_block = {
        "max_cost_usd": 0.01,
        "max_risk_score": 0,
        "max_failure_probability": 0.0,
        "min_confidence_score": 0.99,
        "mode": "strict",
    }

    r = client.post(
        "/api/v2/policy/evaluate",
        params={
            "job_name": job_name,
            "contract_hash": contract_hash,
            "plan_hash": plan_hash,
            "intelligence_hash": intelligence_hash,
        },
        json=thresholds_block,
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text
    block_eval = r.json()
    assert block_eval["decision"] == "BLOCK"
    policy_eval_hash_block = block_eval["policy_eval_hash"]

    # 5b) BUILD (BLOCK should 403)
    r = client.post(
        "/api/v3/build/run",
        params={
            "job_name": job_name,
            "contract_hash": contract_hash,
            "plan_hash": plan_hash,
            "intelligence_hash": intelligence_hash,
            "policy_eval_hash": policy_eval_hash_block,
        },
        headers=HEADERS,
    )
    assert r.status_code == 403, r.text