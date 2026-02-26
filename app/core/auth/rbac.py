from __future__ import annotations

from typing import Callable, Iterable, List, Optional

from fastapi import HTTPException, Request


# Role hierarchy (simple, extensible)
ROLE_ORDER = {
    "viewer": 1,
    "admin": 2,
}


def _get_user_role(request: Request) -> Optional[str]:
    user = getattr(request.state, "user", None)
    if not user:
        return None
    return user.get("role")


def _enforce_any_role(request: Request, allowed_roles: Iterable[str]):
    allowed = list(allowed_roles)
    for r in allowed:
        if r not in ROLE_ORDER:
            raise ValueError(f"Unknown role: {r}")

    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_role = user.get("role")
    if user_role not in ROLE_ORDER:
        raise HTTPException(status_code=403, detail="Invalid role")

    # allow if user's role is >= min required among allowed_roles
    # e.g. allowed ["viewer"] => viewer/admin ok, allowed ["admin"] => admin only
    min_required = min(allowed, key=lambda x: ROLE_ORDER[x])
    if ROLE_ORDER[user_role] < ROLE_ORDER[min_required]:
        raise HTTPException(status_code=403, detail="Insufficient role")

    return user


def require_role(required_role: str) -> Callable:
    """
    FastAPI dependency-style role enforcement.
    """
    if required_role not in ROLE_ORDER:
        raise ValueError(f"Unknown role: {required_role}")

    def dependency(request: Request):
        return _enforce_any_role(request, [required_role])

    return dependency


def require_any_role(roles: List[str]) -> Callable:
    """
    Dependency: allow any of the roles (by hierarchy).
    Example:
      Depends(require_any_role(["viewer", "admin"]))
    """
    def dependency(request: Request):
        return _enforce_any_role(request, roles)

    return dependency


def enforce_required_role(*, user_role: Optional[str], required_role: str) -> bool:
    """
    Used by middleware policy enforcement.
    Returns True if allowed else False.
    """
    if required_role not in ROLE_ORDER:
        raise ValueError(f"Unknown role: {required_role}")
    if not user_role or user_role not in ROLE_ORDER:
        return False
    return ROLE_ORDER[user_role] >= ROLE_ORDER[required_role]
