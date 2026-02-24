from pathlib import Path
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)

AUTH = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


def test_cancel_lifecycle(tmp_path: Path):
    ws = tmp_path / "workspace" / "job_cancel"
    ws.mkdir(parents=True, exist_ok=True)

    # apply
    r1 = client.post(
        "/api/v2/build/apply",
        json={"job_name": "job_cancel", "workspace_dir": str(ws)},
        params={"contract_hash": "c1"},
        headers=AUTH,
    )
    assert r1.status_code == 200

    # run
    r2 = client.post(
        "/api/v2/build/run",
        json={"job_name": "job_cancel", "workspace_dir": str(ws), "backend": "local"},
        params={"contract_hash": "c1"},
        headers=AUTH,
    )
    assert r2.status_code == 200
    assert r2.json()["execution"]["state"] == "RUNNING"

    # cancel
    r3 = client.post(
        "/api/v2/build/cancel",
        json={"job_name": "job_cancel", "workspace_dir": str(ws)},
        headers=AUTH,
    )
    assert r3.status_code == 200
    assert r3.json()["execution"]["state"] == "CANCELED"

    # idempotent cancel
    r4 = client.post(
        "/api/v2/build/cancel",
        json={"job_name": "job_cancel", "workspace_dir": str(ws)},
        headers=AUTH,
    )
    assert r4.status_code == 200
    assert r4.json()["execution"]["state"] == "CANCELED"