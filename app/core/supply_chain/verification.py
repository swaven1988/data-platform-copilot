import hashlib
import json
import os
from pathlib import Path
from typing import Dict


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_expected_sha(sha_file: Path) -> str:
    content = sha_file.read_text().strip()
    return content.split()[0]


def verify_artifact_integrity(artifact_path: Path, sha_path: Path) -> Dict:
    if not artifact_path.exists():
        return {"valid": False, "reason": "artifact_missing"}

    if not sha_path.exists():
        return {"valid": False, "reason": "sha_file_missing"}

    actual_sha = sha256_file(artifact_path)
    expected_sha = load_expected_sha(sha_path)

    return {
        "valid": actual_sha == expected_sha,
        "expected_sha": expected_sha,
        "actual_sha": actual_sha,
    }


_EXCLUDED_DIRS = {
    "workspace", "node_modules", ".venv", "venv", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".git", ".egg-info",
}


def generate_runtime_manifest(project_root: Path) -> Dict:
    manifest = {
        "files": [],
        "total_files": 0,
    }

    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        # Skip excluded directories anywhere in the path
        parts = set(path.relative_to(project_root).parts)
        if parts & _EXCLUDED_DIRS:
            continue
        manifest["files"].append({
            "path": str(path.relative_to(project_root)),
            "sha256": sha256_file(path),
        })

    manifest["total_files"] = len(manifest["files"])
    return manifest



def write_runtime_manifest(project_root: Path, output_path: Path):
    manifest = generate_runtime_manifest(project_root)
    output_path.write_text(json.dumps(manifest, indent=2))