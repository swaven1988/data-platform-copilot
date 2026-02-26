from fastapi.testclient import TestClient
from app.api.main import app


def test_metrics_snapshot_increments_after_traffic():
    c = TestClient(app)

    # generate traffic
    c.get("/api/v1/health/live", headers={"Authorization": "Bearer dev_admin_token", "X-Tenant": "default"})
    c.get("/api/v1/health/live", headers={"Authorization": "Bearer dev_admin_token", "X-Tenant": "default"})

    r = c.get("/api/v1/metrics/snapshot", headers={"Authorization": "Bearer dev_admin_token"})
    assert r.status_code == 200
    body = r.json()
    assert "requests" in body
    assert isinstance(body["requests"], dict)

    # at least one key should exist now
    assert len(body["requests"]) >= 1