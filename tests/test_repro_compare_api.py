from pathlib import Path
from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)

def test_repro_compare_smoke():
    repo_root = Path(__file__).resolve().parents[1]
    ws = repo_root / "workspace"
    if not ws.exists():
        return
    jobs = [p.name for p in ws.iterdir() if p.is_dir() and not p.name.startswith(".")]
    if len(jobs) < 1:
        return
    # compare same job to itself should be no diffs
    r = client.get("/workspace/repro/compare", params={"job_a": jobs[0], "job_b": jobs[0]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["summary"]["added"] == 0
    assert d["summary"]["removed"] == 0
    assert d["summary"]["changed"] == 0
