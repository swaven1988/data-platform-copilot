"""Phase 31 tests: shared lifecycle persistence, reconcile, and retry endpoint."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient


def _store_path(ws_root: Path) -> Path:
    return ws_root / ".copilot" / "execution" / "lifecycle_store.json"


def test_execution_retry_endpoint_happy_path(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_WORKSPACE_ROOT", str(tmp_path))

    from app.api.main import app

    c = TestClient(app)
    h = {"Authorization": "Bearer dev_admin_token"}

    run_id = "retry_run_1"
    r_create = c.post("/api/v1/executions/create", json={"run_id": run_id}, headers=h)
    assert r_create.status_code == 200, r_create.text

    r_reconcile = c.post("/api/v1/executions/reconcile?stale_after_seconds=0", headers=h)
    assert r_reconcile.status_code == 200, r_reconcile.text

    r_retry = c.post(f"/api/v1/executions/{run_id}/retry", headers=h)
    assert r_retry.status_code == 200, r_retry.text
    body = r_retry.json()
    assert body["run_id"] == run_id
    assert body["status"] == "PENDING"
    assert body["retry_count"] == 1


def test_execution_retry_endpoint_rejects_active_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_WORKSPACE_ROOT", str(tmp_path))

    from app.api.main import app

    c = TestClient(app)
    h = {"Authorization": "Bearer dev_admin_token"}

    run_id = "retry_run_2"
    r_create = c.post("/api/v1/executions/create", json={"run_id": run_id}, headers=h)
    assert r_create.status_code == 200, r_create.text

    # RUNNING is active and retry should be idempotent/no-op with 200
    r_retry = c.post(f"/api/v1/executions/{run_id}/retry", headers=h)
    assert r_retry.status_code == 200, r_retry.text
    assert r_retry.json()["status"] == "RUNNING"


def test_execution_lifecycle_store_persisted_to_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_WORKSPACE_ROOT", str(tmp_path))

    from app.api.main import app

    c = TestClient(app)
    h = {"Authorization": "Bearer dev_admin_token"}

    run_id = "persist_run_1"
    r_create = c.post("/api/v1/executions/create", json={"run_id": run_id}, headers=h)
    assert r_create.status_code == 200, r_create.text

    p = _store_path(tmp_path)
    assert p.exists()

    obj = json.loads(p.read_text(encoding="utf-8"))
    assert obj["kind"] == "execution_lifecycle_store"
    assert run_id in obj["runs"]


def test_periodic_reconcile_is_wired():
    """Lifespan and periodic reconcile task must be defined in main."""
    import app.api.main as m

    assert callable(getattr(m, "_periodic_reconcile", None)), \
        "_periodic_reconcile must be defined in app/api/main.py"
    assert callable(getattr(m, "_lifespan", None)), \
        "_lifespan must be defined in app/api/main.py"

