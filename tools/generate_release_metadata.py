import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path


def sha256_file(path: Path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main():
    root = Path(".").resolve()

    commit = (
        subprocess.check_output(["git", "rev-parse", "HEAD"])
        .decode()
        .strip()
    )

    packaging_hash = sha256_file(root / "packaging_manifest.json")
    openapi_hash = sha256_file(root / "openapi_snapshot.json")

    metadata = {
        "version": subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"]
        )
        .decode()
        .strip(),
        "commit": commit,
        "packaging_manifest_hash": packaging_hash,
        "openapi_hash": openapi_hash,
        "build_timestamp_utc": datetime.utcnow().isoformat(),
    }

    (root / "release_metadata.json").write_text(
        json.dumps(metadata, indent=2)
    )


if __name__ == "__main__":
    main()