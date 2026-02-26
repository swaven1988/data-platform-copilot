from fastapi.testclient import TestClient
from app.api.main import app


def test_metrics_snapshot_endpoint_exists():
    c = TestClient(app)
    # generate some traffic
    c.get("/api/v1/health/live", headers={"Authorization": "Bearer dev_admin_token"})
    r = c.get("/api/v1/metrics/snapshot", headers={"Authorization": "Bearer dev_admin_token"})
    assert r.status_code == 200
    body = r.json()
    assert "requests" in body
    assert isinstance(body["requests"], dict)
