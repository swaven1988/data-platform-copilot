from fastapi.testclient import TestClient
from app.api.main import app


def test_cache_stats_endpoint():
    client = TestClient(app)

    r = client.get("/cache/stats")
    assert r.status_code == 200

    data = r.json()
    assert data["kind"] == "advisors_run_cache"
    assert "hits" in data
    assert "misses" in data
    assert "entries" in data
    assert "ttl_seconds" in data
    assert "max_entries" in data
