import json
from pathlib import Path
from fastapi.testclient import TestClient
from app.api.main import app


SNAPSHOT = Path("tests/snapshots/openapi_snapshot.json")


def test_openapi_snapshot_matches_expected():
    client = TestClient(app)
    r = client.get("/openapi.json")
    assert r.status_code == 200

    current_schema = r.json()

    # First run: generate snapshot file
    if not SNAPSHOT.exists():
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(
            json.dumps(current_schema, indent=2),
            encoding="utf-8",
        )
        assert True
        return

    expected_schema = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert current_schema == expected_schema
