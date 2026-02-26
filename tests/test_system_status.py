from fastapi.testclient import TestClient
from app.api.main import app


def test_system_status_endpoint():
    c = TestClient(app)
    r = c.get(
        "/api/v1/system/status",
        headers={"Authorization": "Bearer dev_admin_token"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "metrics" in body
    assert "artifact" in body