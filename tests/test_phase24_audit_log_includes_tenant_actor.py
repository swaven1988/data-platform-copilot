import json
from pathlib import Path

from fastapi.testclient import TestClient
from app.api.main import app


def test_audit_log_includes_tenant_and_actor(tmp_path, monkeypatch):
    audit_path = tmp_path / "audit.log"
    monkeypatch.setenv("COPILOT_AUDIT_PATH", str(audit_path))

    c = TestClient(app)
    r = c.get(
        "/api/v1/health/live",
        headers={"Authorization": "Bearer dev_admin_token", "X-Tenant": "default"},
    )
    assert r.status_code == 200

    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1
    rec = json.loads(lines[-1])

    assert rec["type"] == "http_request"
    assert rec["actor"] in ("dev_admin", "dev_viewer", "bearer", "static_token_admin", "static_token_viewer", None)
    assert rec["tenant"] == "default"
    assert rec["http"]["path"] == "/api/v1/health/live"