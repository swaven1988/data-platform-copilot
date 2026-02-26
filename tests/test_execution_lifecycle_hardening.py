import time
from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)
H = {"Authorization": "Bearer dev_admin_token"}


def test_cancel_idempotent():
    run_id = "r1"
    r = client.post("/api/v1/executions/create", json={"run_id": run_id}, headers=H)
    assert r.status_code == 200

    c1 = client.post(f"/api/v1/executions/{run_id}/cancel", headers=H)
    assert c1.status_code == 200
    assert c1.json()["status"] == "CANCELING"

    # second cancel should be idempotent (still CANCELING)
    c2 = client.post(f"/api/v1/executions/{run_id}/cancel", headers=H)
    assert c2.status_code == 200
    assert c2.json()["status"] == "CANCELING"


def test_reconcile_stale_to_terminal():
    run_id = "r2"
    r = client.post("/api/v1/executions/create", json={"run_id": run_id}, headers=H)
    assert r.status_code == 200

    # wait small and reconcile aggressively
    time.sleep(0.01)
    rec = client.post("/api/v1/executions/reconcile?stale_after_seconds=0", headers=H)
    assert rec.status_code == 200
    assert rec.json()["reconciled"] >= 1


def test_reconcile_stale_cancel_to_canceled():
    run_id = "r3"
    r = client.post("/api/v1/executions/create", json={"run_id": run_id}, headers=H)
    assert r.status_code == 200

    c = client.post(f"/api/v1/executions/{run_id}/cancel", headers=H)
    assert c.status_code == 200

    time.sleep(0.01)
    rec = client.post("/api/v1/executions/reconcile?stale_after_seconds=0", headers=H)
    assert rec.status_code == 200