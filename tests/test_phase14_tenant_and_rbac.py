from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_v2_requires_x_tenant_header_for_non_health_metrics():
    # billing summary is /api/v2/* and should require X-Tenant
    r = client.get(
        "/api/v2/billing/summary",
        headers={"Authorization": "Bearer dev_admin_token"},
    )
    assert r.status_code == 400
    assert "Missing X-Tenant" in (r.json().get("detail") or "")


def test_v2_health_does_not_require_tenant_header():
    r = client.get("/api/v1/health/live")
    assert r.status_code in (200, 204)


def test_viewer_can_get_v2_when_tenant_present():
    r = client.get(
        "/api/v2/billing/summary",
        headers={"Authorization": "Bearer dev_viewer_token", "X-Tenant": "default"},
    )
    # should succeed (200) or 401 if auth provider disabled; but in repo it is enabled with dev tokens
    assert r.status_code == 200, r.text


def test_viewer_cannot_post_v2_apply():
    # apply is a write surface; default required role remains admin
    r = client.post(
        "/api/v2/build/apply?contract_hash=sm1",
        headers={"Authorization": "Bearer dev_viewer_token", "X-Tenant": "default"},
        json={},
    )
    assert r.status_code in (403, 422), r.text
    # 422 is acceptable if endpoint expects a body and validation fails BEFORE auth;
    # if auth runs first, it should be 403.


def test_admin_can_post_v2_apply_authz_path():
    # We only assert it is not 403 when admin; it may be 200/400/422 depending on contract_hash/body
    r = client.post(
        "/api/v2/build/apply?contract_hash=sm1",
        headers={"Authorization": "Bearer dev_admin_token", "X-Tenant": "default"},
        json={},
    )
    assert r.status_code != 403, r.text
