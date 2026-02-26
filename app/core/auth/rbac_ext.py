from fastapi import HTTPException, status
from starlette.requests import Request

# Reuse the legacy enforcement (keeps existing error shape/handlers)
from app.core.auth.rbac import enforce_required_role


def require_role(role: str):
    async def _dep(request: Request):
        enforce_required_role(required_role=role, request=request)
        return role
    return _dep


def require_roles(*allowed_roles: str):
    async def _dep(request: Request):
        role = getattr(request.state, "role", None) or getattr(request.state, "user_role", None)
        if role is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        if role not in allowed_roles:
            # match existing style as close as possible (legacy layer may wrap)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return role
    return _dep
