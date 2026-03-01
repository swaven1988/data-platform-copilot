"""V1 readiness gate script for platform hardening release checks."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REQUIRED_FILES = [
    "VERSION",
    "packaging_manifest.json",
    "tests/snapshots/openapi_snapshot.json",
    "release_metadata.json",
    "frontend/package.json",
]


def _run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return p.returncode, p.stdout


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    failures: list[str] = []

    # Required artifacts
    for rel in REQUIRED_FILES:
        p = repo / rel
        if not p.exists():
            failures.append(f"missing_required_file:{rel}")

    # Version file shape
    v = (repo / "VERSION").read_text(encoding="utf-8").strip() if (repo / "VERSION").exists() else ""
    if not v.startswith("v"):
        failures.append("invalid_version_format:VERSION must start with 'v'")

    # Frontend build artifact
    dist = repo / "frontend" / "dist"
    if not dist.is_dir() or not any(dist.iterdir()):
        failures.append("frontend_dist_missing_or_empty:run 'cd frontend && npm run build'")

    # OpenAPI snapshot parity
    rc, out = _run([sys.executable, "-m", "pytest", "-q", "tests/test_openapi_snapshot.py"],)
    if rc != 0:
        failures.append("openapi_snapshot_mismatch")

    # Packaging manifest parity
    rc2, out2 = _run([sys.executable, "-m", "pytest", "-q", "tests/test_packaging_manifest_check.py"],)
    if rc2 != 0:
        failures.append("packaging_manifest_mismatch")

    # Smoke check key endpoints tests
    rc3, out3 = _run([sys.executable, "-m", "pytest", "-q", "tests/test_phase40_api_contract_parity.py"],)
    if rc3 != 0:
        failures.append("phase40_contract_parity_failed")

    report = {
        "kind": "v1_readiness_report",
        "ready": not failures,
        "failures": failures,
    }
    print(json.dumps(report, indent=2, sort_keys=True))

    if failures:
        if rc != 0:
            print("\n--- test_openapi_snapshot.py output ---")
            print(out)
        if rc2 != 0:
            print("\n--- test_packaging_manifest_check.py output ---")
            print(out2)
        if rc3 != 0:
            print("\n--- test_phase40_api_contract_parity.py output ---")
            print(out3)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

