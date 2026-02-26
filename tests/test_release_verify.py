from __future__ import annotations

import json
import tarfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.release.verify import verify_release_tarball


def _make_tar(tmp_path: Path) -> Path:
    # Create content files
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("hello", encoding="utf-8")
    b.write_text("world", encoding="utf-8")

    def sha256_bytes(bs: bytes) -> str:
        import hashlib
        h = hashlib.sha256()
        h.update(bs)
        return h.hexdigest()

    # Build packaging_manifest.json consistent with our tar contents
    files = []
    for fp in [Path("a.txt"), Path("b.txt")]:
        data = (tmp_path / fp.name).read_bytes()
        files.append({"path": fp.as_posix(), "sha256": sha256_bytes(data), "size": len(data)})

    manifest = {"kind": "packaging_manifest", "include_paths": [], "excludes": [], "files": files}

    mpath = tmp_path / "packaging_manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    tar_path = tmp_path / "release.tar.gz"
    with tarfile.open(tar_path, mode="w:gz") as tf:
        tf.add(a, arcname="a.txt")
        tf.add(b, arcname="b.txt")
        tf.add(mpath, arcname="packaging_manifest.json")

    return tar_path


def test_verify_release_tarball_ok(tmp_path: Path):
    tar_path = _make_tar(tmp_path)
    out = verify_release_tarball(str(tar_path))
    assert out["ok"] is True
    assert out["manifest_ok"] is True
    assert out["missing"] == []
    assert out["mismatched"] == []


def test_verify_release_tarball_detects_mismatch(tmp_path: Path):
    tar_path = _make_tar(tmp_path)

    # mutate tar by rewriting it with changed a.txt but same manifest
    changed = tmp_path / "a.txt"
    changed.write_text("HELLO_CHANGED", encoding="utf-8")

    tar2 = tmp_path / "release2.tar.gz"
    with tarfile.open(tar_path, mode="r:gz") as src:
        members = src.getmembers()

    # rebuild tar2 with mutated a.txt and original manifest extracted
    mbytes = None
    with tarfile.open(tar_path, mode="r:gz") as tf:
        m = tf.getmember("packaging_manifest.json")
        mbytes = tf.extractfile(m).read()

    mpath = tmp_path / "packaging_manifest.json"
    mpath.write_bytes(mbytes)

    b = tmp_path / "b.txt"  # unchanged

    with tarfile.open(tar2, mode="w:gz") as tf:
        tf.add(changed, arcname="a.txt")
        tf.add(b, arcname="b.txt")
        tf.add(mpath, arcname="packaging_manifest.json")

    out = verify_release_tarball(str(tar2))
    assert out["ok"] is False
    assert out["manifest_ok"] is False
    assert "a.txt" in out["mismatched"]


def test_api_verify_release(tmp_path: Path):
    tar_path = _make_tar(tmp_path)
    c = TestClient(app)

    r = c.post(
        "/api/v2/release/verify",
        headers={"Authorization": "Bearer dev_admin_token", "X-Tenant": "default"},
        json={"artifact_path": str(tar_path)},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["manifest_ok"] is True


def test_api_verify_requires_tenant(tmp_path: Path):
    tar_path = _make_tar(tmp_path)
    c = TestClient(app)

    r = c.post(
        "/api/v2/release/verify",
        headers={"Authorization": "Bearer dev_admin_token"},
        json={"artifact_path": str(tar_path)},
    )
    # middleware OR endpoint should block
    assert r.status_code in (400, 401), r.text
