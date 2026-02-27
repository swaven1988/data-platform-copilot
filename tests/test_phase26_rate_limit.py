from fastapi.testclient import TestClient
from app.api.main import app


def test_rate_limit_hits_on_mutating_endpoint(monkeypatch):
    monkeypatch.setenv("COPILOT_RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("COPILOT_RATE_LIMIT_RPM", "2")

    c = TestClient(app)

    headers = {
        "Authorization": "Bearer dev_viewer_token",
        "X-Tenant": "default",
        "X-Forwarded-For": "1.2.3.4",
    }

    r1 = c.post("/api/v1/health/ping", headers=headers)
    r2 = c.post("/api/v1/health/ping", headers=headers)
    r3 = c.post("/api/v1/health/ping", headers=headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429