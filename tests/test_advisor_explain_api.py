from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)

def test_advisor_explain_default():
    payload = {
        "advisor_name": "basic_checks",
        "code": "plan.no_baseline",
        "finding": {"severity": "warn", "message": "Baseline missing", "applies_to": "workspace/x"},
    }
    r = client.post("/advisors/explain", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["advisor_name"] == "basic_checks"
    assert data["code"] == "plan.no_baseline"
    assert "Guidance" in data["explanation"]
