import json
from pathlib import Path


def test_release_metadata_present():
    path = Path("release_metadata.json")
    assert path.exists()

    data = json.loads(path.read_text())

    assert "commit" in data
    assert "packaging_manifest_hash" in data
    assert "openapi_hash" in data