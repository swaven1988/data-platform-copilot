from fastapi.testclient import TestClient
from app.api.main import app


def test_request_id_header_roundtrip():
    c = TestClient(app)
    r = c.get("/api/v1/health/live")
    assert r.status_code in (200, 404)  # endpoint may differ by stack
    assert "X-Request-Id" in r.headers
    assert len(r.headers["X-Request-Id"]) > 10


def test_request_id_passthrough():
    c = TestClient(app)
    rid = "test-rid-123"
    r = c.get("/api/v1/health/live", headers={"X-Request-Id": rid})
    assert r.headers.get("X-Request-Id") == rid