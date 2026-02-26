from fastapi.testclient import TestClient
from app.api.main import app


def test_cross_tenant_denied_for_tenant_path_endpoints():
    c = TestClient(app)

    # request is in tenant=default via header, but tries /tenants/other/...
    r = c.get(
        "/api/v1/tenants/other/health",
        headers={"Authorization": "Bearer dev_viewer_token", "X-Tenant": "default"},
    )
    assert r.status_code == 403


def test_tenant_path_allows_matching_tenant():
    c = TestClient(app)

    r = c.get(
        "/api/v1/tenants/default/health",
        headers={"Authorization": "Bearer dev_viewer_token", "X-Tenant": "default"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tenant"] == "default"