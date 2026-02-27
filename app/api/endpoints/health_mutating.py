from fastapi import APIRouter, Depends, Request

from app.core.auth.rbac import require_role

router = APIRouter()


@router.post("/health/ping")
def health_ping_mutating(
    request: Request,
    _auth=Depends(require_role("viewer")),
):
    tenant = getattr(request.state, "tenant", None) or getattr(request.state, "tenant_id", None)
    return {"ok": True, "tenant": tenant, "kind": "mutating_ping"}