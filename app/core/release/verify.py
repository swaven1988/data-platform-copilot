from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any, Dict, List, Optional


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_release_tarball(
    tarball_path: str,
    expected_sha256: Optional[str] = None,
    *,
    strict_no_extras: bool = False,
    require_packaging_manifest: bool = True,
) -> Dict[str, Any]:
    p = Path(tarball_path)
    if not p.exists():
        return {"ok": False, "error": f"artifact not found: {p}"}
    if not p.is_file():
        return {"ok": False, "error": f"artifact is not a file: {p}"}

    actual_artifact_sha = _sha256_file(p)
    sha256_match = True if expected_sha256 is None else (actual_artifact_sha == expected_sha256)

    # sha-only mode (tests write dummy bytes; must not open tar)
    if not require_packaging_manifest:
        return {
            "ok": sha256_match,
            "artifact": p.name,
            "artifact_path": str(p),
            "artifact_sha256": actual_artifact_sha,
            "sha256_match": sha256_match,
            "manifest_ok": True,
            "missing": [],
            "mismatched": [],              # list[str]
            "extras": [],
            "file_checks": [],             # optional detail list[dict]
            "mismatched_details": [],      # optional detail list[dict]
            "metadata_in_tar": None,
        }

    try:
        with tarfile.open(p, mode="r:gz") as tf:
            members = [m for m in tf.getmembers() if m.isfile()]
            tar_paths = {m.name for m in members}

            if "packaging_manifest.json" not in tar_paths:
                return {"ok": False, "error": "packaging_manifest.json missing from tarball"}

            manifest_bytes = tf.extractfile("packaging_manifest.json").read()  # type: ignore[union-attr]
            manifest = json.loads(manifest_bytes.decode("utf-8"))

            files: List[Dict[str, Any]] = list(manifest.get("files", []))
            expected_paths = {f["path"] for f in files if "path" in f}

            missing = sorted([x for x in expected_paths if x not in tar_paths])
            extras = sorted([x for x in tar_paths if x not in expected_paths])

            mismatched: List[str] = []
            mismatched_details: List[Dict[str, Any]] = []
            file_checks: List[Dict[str, Any]] = []

            for f in files:
                path = f.get("path")
                exp_sha = f.get("sha256")
                if not path or not exp_sha:
                    continue
                if path not in tar_paths:
                    continue

                data = tf.extractfile(path).read()  # type: ignore[union-attr]
                got_sha = hashlib.sha256(data).hexdigest()
                ok = got_sha == exp_sha

                file_checks.append(
                    {
                        "path": path,
                        "sha256_ok": ok,
                        "expected_sha256": exp_sha,
                        "actual_sha256": got_sha,
                    }
                )
                if not ok:
                    mismatched.append(path)
                    mismatched_details.append(
                        {
                            "path": path,
                            "expected_sha256": exp_sha,
                            "actual_sha256": got_sha,
                        }
                    )

            manifest_ok = (len(missing) == 0) and (len(mismatched) == 0) and (not strict_no_extras or len(extras) == 0)
            ok_all = bool(sha256_match and manifest_ok)

            metadata_in_tar = None
            if "release_metadata.json" in tar_paths:
                try:
                    metadata_in_tar = json.loads(
                        tf.extractfile("release_metadata.json").read().decode("utf-8")  # type: ignore[union-attr]
                    )
                except Exception:
                    metadata_in_tar = None

            return {
                "ok": ok_all,
                "artifact": p.name,
                "artifact_path": str(p),
                "artifact_sha256": actual_artifact_sha,
                "sha256_match": sha256_match,
                "manifest_ok": manifest_ok,
                "missing": missing,
                "mismatched": mismatched,                  # list[str] (what tests expect)
                "extras": extras,
                "file_checks": file_checks,
                "mismatched_details": mismatched_details,  # richer details for UI/debug
                "metadata_in_tar": metadata_in_tar,
            }
    except tarfile.ReadError:
        return {"ok": False, "error": "not a gzipped tarball"}
