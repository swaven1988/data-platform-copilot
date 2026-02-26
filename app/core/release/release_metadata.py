import json
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def get_git_commit() -> str:
    return (
        subprocess.check_output(["git", "rev-parse", "HEAD"])
        .decode()
        .strip()
    )


def generate_release_metadata(project_root: Path) -> dict:
    manifest = project_root / "packaging_manifest.json"
    openapi = project_root / "tests" / "snapshots" / "openapi_snapshot.json"

    return {
        "version": (project_root / "VERSION").read_text().strip()
        if (project_root / "VERSION").exists()
        else "dev",
        "commit_sha": get_git_commit(),
        "manifest_sha256": sha256_file(manifest),
        "openapi_sha256": sha256_file(openapi),
        "build_timestamp_utc": datetime.utcnow().isoformat(),
    }


def write_release_metadata(project_root: Path):
    metadata = generate_release_metadata(project_root)
    output = project_root / "release_metadata.json"
    output.write_text(json.dumps(metadata, indent=2))