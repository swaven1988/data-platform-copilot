from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _git_head(project_root: Path) -> str:
    return (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project_root)
        .decode("utf-8")
        .strip()
    )


def _git_describe(project_root: Path) -> str:
    try:
        return (
            subprocess.check_output(["git", "describe", "--tags", "--abbrev=0"], cwd=project_root)
            .decode("utf-8")
            .strip()
        )
    except Exception:
        return "unknown"


def write_release_metadata(project_root: Path) -> Dict[str, Any]:
    project_root = project_root.resolve()

    packaging_manifest = project_root / "packaging_manifest.json"
    openapi_snapshot = project_root / "openapi_snapshot.json"

    commit = _git_head(project_root)
    version = _git_describe(project_root)

    pm_hash = _sha256_file(packaging_manifest) if packaging_manifest.exists() else None
    oa_hash = _sha256_file(openapi_snapshot) if openapi_snapshot.exists() else None

    built_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Backward compatible + canonical keys
    data: Dict[str, Any] = {
        "version": version,
        "commit": commit,
        "built_at_utc": built_at,
        "packaging_manifest_hash": pm_hash,
        "openapi_hash": oa_hash,
        # legacy aliases (keep if consumers rely on them)
        "packaging_manifest_sha256": pm_hash,
        "openapi_snapshot_sha256": oa_hash,
    }

    (project_root / "release_metadata.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data