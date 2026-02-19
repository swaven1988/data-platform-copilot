from typing import Callable, List
from fastapi import HTTPException, Request


# Role hierarchy (simple, extensible)
ROLE_ORDER = {
    "viewer": 1,
    "admin": 2,
}


def require_role(required_role: str) -> Callable:
    """
    FastAPI dependency-style role enforcement.

    Usage:
        @router.get(...)
        def endpoint(..., user=Depends(require_role("admin"))):
            ...
    """

    if required_role not in ROLE_ORDER:
        raise ValueError(f"Unknown role: {required_role}")

    def dependency(request: Request):
        user = getattr(request.state, "user", None)

        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        user_role = user.get("role")

        if user_role not in ROLE_ORDER:
            raise HTTPException(status_code=403, detail="Invalid role")

        if ROLE_ORDER[user_role] < ROLE_ORDER[required_role]:
            raise HTTPException(status_code=403, detail="Insufficient role")

        return user

    return dependency
