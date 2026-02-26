from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)

def test_execution_graph_endpoint():
    r = client.get("/execution/graph?intent=build")
    assert r.status_code == 200
    data = r.json()
    assert "order" in data
    assert isinstance(data["order"], list)
