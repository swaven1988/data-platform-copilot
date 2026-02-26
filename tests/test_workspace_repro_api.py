from pathlib import Path
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_workspace_repro_manifest_missing_job():
    r = client.get("/workspace/repro/manifest", params={"job_name": "does_not_exist"})
    assert r.status_code == 404, r.text


def test_workspace_repro_manifest_smoke():
    repo_root = Path(__file__).resolve().parents[1]
    ws = repo_root / "workspace"
    if not ws.exists():
        return

    jobs = [p.name for p in ws.iterdir() if p.is_dir() and not p.name.startswith(".")]
    if not jobs:
        return

    r = client.get("/workspace/repro/manifest", params={"job_name": jobs[0]})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kind"] == "workspace_repro_manifest"
    assert "files" in data
