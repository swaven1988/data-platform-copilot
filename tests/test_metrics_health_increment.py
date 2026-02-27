def test_health_metrics_increment(client):
    r1 = client.get("/api/v1/health/live")
    assert r1.status_code == 200

    r2 = client.get("/api/v1/metrics/snapshot")
    data = r2.json()

    assert data.get("health_live", 0) >= 1
    assert data.get("requests_total", 0) >= 1