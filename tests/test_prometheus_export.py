"""Prometheus export endpoint contract tests.

This module validates that the scrape endpoint is reachable and returns
expected metric names. It does not validate absolute counter values across
process restarts.
"""

from fastapi.testclient import TestClient

from app.api.main import app


def test_prometheus_metrics_endpoint_returns_200(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_ENABLED", "0")
    c = TestClient(app)
    r = c.get("/metrics")
    assert r.status_code == 200
    assert "copilot_http_requests_total" in r.text
