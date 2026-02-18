from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)

def test_architecture_audit_endpoint():
    r = client.get("/audit/architecture")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kind"] == "architecture_audit"
    assert "status" in data
    assert "findings" in data
