"""Fix 2 test — verifies path traversal protection in execution endpoint."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)

HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


def test_job_name_with_path_traversal_returns_400():
    r = client.post(
        "/api/v2/build/apply?contract_hash=abc123",
        json={"job_name": "../../etc/passwd"},
        headers=HEADERS,
    )
    assert r.status_code == 400, r.text
    assert "job_name" in r.text.lower() or "invalid" in r.text.lower()


def test_job_name_with_slash_returns_400():
    r = client.post(
        "/api/v2/build/apply?contract_hash=abc123",
        json={"job_name": "foo/bar"},
        headers=HEADERS,
    )
    assert r.status_code == 400, r.text


def test_valid_job_name_accepted():
    """Valid job names should not be rejected by the regex guard (may fail later for other reasons)."""
    r = client.post(
        "/api/v2/build/apply?contract_hash=abc123",
        json={"job_name": "valid-job_name-123"},
        headers=HEADERS,
    )
    # 400 is ok if it fails for business reasons (workspace missing etc.) — not for job_name validation
    if r.status_code == 400:
        body = r.json()
        detail = str(body.get("detail", ""))
        assert "job_name" not in detail.lower(), f"Valid job_name was incorrectly rejected: {detail}"


def test_workspace_dir_outside_root_returns_400(tmp_path):
    """workspace_dir pointing outside the workspace root must be rejected."""
    r = client.post(
        "/api/v2/build/apply?contract_hash=abc123",
        json={"job_name": "testjob", "workspace_dir": str(tmp_path / "evil")},
        headers=HEADERS,
    )
    assert r.status_code == 400, r.text
    assert "workspace_dir" in r.text.lower() or "workspace" in r.text.lower()
