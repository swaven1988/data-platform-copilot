from fastapi.testclient import TestClient
from app.api.main import app

c = TestClient(app)


def test_admin_can_access_system_status():
    r = c.get(
        "/api/v1/system/status",
        headers={"Authorization": "Bearer dev_admin_token"},
    )
    assert r.status_code == 200


def test_viewer_cannot_access_system_status():
    r = c.get(
        "/api/v1/system/status",
        headers={"Authorization": "Bearer dev_viewer_token"},
    )
    assert r.status_code == 403


def test_no_token_denied():
    r = c.get("/api/v1/system/status")
    assert r.status_code == 401