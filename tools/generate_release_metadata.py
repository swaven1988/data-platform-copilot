import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main():
    root = Path(".").resolve()

    version_file = (root / "VERSION").read_text(encoding="utf-8").strip()

    commit = (
        subprocess.check_output(["git", "rev-parse", "HEAD"])
        .decode()
        .strip()
    )

    packaging_hash = sha256_file(root / "packaging_manifest.json")
    openapi_hash = sha256_file(root / "openapi_snapshot.json")

    metadata = {
        "version": version_file,
        "commit": commit,
        "packaging_manifest_hash": packaging_hash,
        "openapi_hash": openapi_hash,
        "built_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "packaging_manifest_sha256": packaging_hash,
        "openapi_snapshot_sha256": openapi_hash,
    }

    (root / "release_metadata.json").write_text(
        json.dumps(metadata, indent=2)
    )


if __name__ == "__main__":
    main()
