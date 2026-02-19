from fastapi import APIRouter, Depends

from app.core.auth.rbac import require_role


router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/{tenant}/health")
def tenant_health(
    tenant: str,
    _auth=Depends(require_role("viewer")),
):
    return {"tenant": tenant, "status": "ok", "kind": "tenant_health"}
