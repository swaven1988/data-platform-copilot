from fastapi import APIRouter, Depends, Request

from app.core.auth.rbac import require_role
from app.core.auth.tenant_guard import enforce_tenant

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/{tenant}/health")
def tenant_health(
    tenant: str,
    request: Request,
    _auth=Depends(require_role("viewer")),
):
    enforce_tenant(request, tenant)
    return {"tenant": tenant, "status": "ok", "kind": "tenant_health"}