from __future__ import annotations

import argparse
from pathlib import Path
import sys

# ---- sys.path bootstrap (Windows-friendly) ----
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# ---------------------------------------------

from app.core.packaging.package_manifest import (  # noqa: E402
    generate_packaging_manifest,
    load_manifest,
    manifests_equal,
    write_manifest,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="Fail if packaging_manifest.json differs from regenerated")
    ap.add_argument("--out", default="packaging_manifest.json", help="Output path (default packaging_manifest.json)")
    args = ap.parse_args()

    out_path = PROJECT_ROOT / args.out
    current = generate_packaging_manifest(project_root=PROJECT_ROOT)

    if args.check:
        if not out_path.exists():
            print(f"ERROR: {out_path} missing. Run without --check to generate.", file=sys.stderr)
            return 2
        expected = load_manifest(out_path)
        if not manifests_equal(current, expected):
            print("ERROR: packaging_manifest.json drift detected. Regenerate and commit.", file=sys.stderr)
            return 3
        print("OK: packaging_manifest.json matches.")
        return 0

    write_manifest(out_path, current)
    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
