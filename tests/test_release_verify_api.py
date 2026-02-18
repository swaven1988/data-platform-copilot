import hashlib
from pathlib import Path
from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)

def test_release_verify_missing_tarball():
    r = client.post("/release/verify/tarball", json={"tarball_path":"does_not_exist.tar.gz","expected_sha256":"00"})
    assert r.status_code == 404

def test_release_verify_smoke(tmp_path: Path):
    f = tmp_path / "x.tar.gz"
    f.write_bytes(b"dummy")
    h = hashlib.sha256(b"dummy").hexdigest()
    r = client.post("/release/verify/tarball", json={"tarball_path": str(f), "expected_sha256": h, "require_packaging_manifest": False})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["sha256_match"] is True
