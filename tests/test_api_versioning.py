from fastapi.testclient import TestClient
from app.api.main import app


def test_v2_routes_exist_and_work():
    client = TestClient(app)

    r = client.get("/api/v2/plugins/resolve?intent=build&disabled=always_warn")
    assert r.status_code == 200

    data = r.json()
    assert "selected" in data
    assert "skipped" in data


def test_unversioned_routes_still_work_but_are_deprecated():
    client = TestClient(app)

    r = client.get("/plugins/resolve?intent=build&disabled=always_warn")
    assert r.status_code == 200

    # Deprecation headers present on unversioned endpoints
    assert r.headers.get("Deprecation") == "true"
    assert "Sunset" in r.headers
    assert "Link" in r.headers
