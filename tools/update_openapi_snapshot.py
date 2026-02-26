import json
from pathlib import Path

from app.api.main import app


def main() -> int:
    snap_path = Path("tests/snapshots/openapi_snapshot.json")
    snap_path.parent.mkdir(parents=True, exist_ok=True)

    spec = app.openapi()

    snap_path.write_text(
        json.dumps(spec, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote OpenAPI snapshot: {snap_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())