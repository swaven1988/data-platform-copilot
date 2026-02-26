from fastapi import HTTPException, status
from starlette.requests import Request


def enforce_tenant(request: Request, tenant_id: str):
    ctx_tenant = getattr(request.state, "tenant_id", None)
    if ctx_tenant is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    if ctx_tenant != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
