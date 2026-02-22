from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "packaging_manifest.json"

def git_ls_files() -> list[str]:
    out = subprocess.check_output(["git", "ls-files"], cwd=str(ROOT), text=True)
    return [line.strip() for line in out.splitlines() if line.strip()]

def main() -> int:
    if not MANIFEST.exists():
        print("ERROR: packaging_manifest.json missing")
        return 2

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = data.get("files") or data.get("file_paths") or data.get("paths")

    if not isinstance(expected, list):
        print("ERROR: packaging_manifest.json must contain a list field: files (or file_paths/paths)")
        return 2

    expected_set = set(str(x).strip() for x in expected if str(x).strip())
    actual_set = set(git_ls_files())

    missing = sorted(expected_set - actual_set)
    extra = sorted(actual_set - expected_set)

    if missing or extra:
        print("ERROR: packaging_manifest drift detected")
        if missing:
            print("MISSING (in manifest but not in git ls-files):")
            for p in missing[:200]:
                print("  -", p)
        if extra:
            print("EXTRA (in repo but not in manifest):")
            for p in extra[:200]:
                print("  -", p)
        return 1

    print("OK: packaging_manifest matches git ls-files")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())