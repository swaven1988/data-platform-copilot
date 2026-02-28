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


def test_request_id_present_in_state(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_ENABLED", "0")
    c = TestClient(app)
    r = c.get("/api/v1/health/live")
    assert "x-request-id" in {k.lower() for k in r.headers.keys()}
