import json
from pathlib import Path

from app.core.packaging.package_manifest import generate_packaging_manifest


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    out_path = project_root / "packaging_manifest.json"

    manifest = generate_packaging_manifest(project_root=project_root)

    out_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote packaging manifest: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())