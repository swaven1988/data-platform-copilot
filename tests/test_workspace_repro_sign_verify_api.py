# PATCH 4 — tests/test_workspace_repro_sign_verify_api.py
# Fix: now sign endpoint returns 400 for missing key (even if job doesn't exist),
# and 404 if key exists but job missing. Keep test stable.

# REPLACE entire file with this:

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_workspace_repro_sign_requires_key(monkeypatch):
    monkeypatch.delenv("COPILOT_SIGNING_KEY", raising=False)
    r = client.get("/workspace/repro/sign", params={"job_name": "does_not_matter"})
    assert r.status_code == 400


def test_workspace_repro_sign_verify_roundtrip(monkeypatch):
    monkeypatch.setenv("COPILOT_SIGNING_KEY", "dev_secret_key")

    job_name = "example_pipeline"
    r = client.get("/workspace/repro/sign", params={"job_name": job_name})
    if r.status_code == 404:
        pytest.skip(f"workspace job not present in this test env: {job_name}")
    assert r.status_code == 200, r.text

    sig = r.json()["signature"]
    r2 = client.post("/workspace/repro/verify", json={"job_name": job_name, "signature": sig})
    assert r2.status_code == 200, r2.text
    assert r2.json()["verified"] is True
