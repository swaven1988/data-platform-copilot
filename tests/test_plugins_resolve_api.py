from fastapi.testclient import TestClient

from app.api.main import app


def test_plugins_resolve_endpoint_returns_selected_and_skipped():
    client = TestClient(app)

    r = client.get("/plugins/resolve?intent=build&disabled=always_warn")
    assert r.status_code == 200

    data = r.json()
    assert "selected" in data
    assert "skipped" in data
    assert "order" in data

    assert "always_warn" not in data["selected"]
    assert any(x["name"] == "always_warn" and x["reason"] == "disabled" for x in data["skipped"])
