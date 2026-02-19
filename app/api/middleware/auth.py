from __future__ import annotations

import os
from typing import Callable, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.auth.provider import AuthError, get_auth_provider
from app.core.auth.models import Principal


def _principal_to_user(principal: Principal) -> dict:
    # Backward-compat bridge for existing RBAC dependency (require_role expects request.state.user)
    role = "viewer"
    roles = set(principal.roles or [])
    if "admin" in roles:
        role = "admin"
    elif "viewer" in roles:
        role = "viewer"

    return {
        "sub": principal.subject,
        "role": role,
        "roles": sorted(list(roles)),
    }


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Stage 14 Auth Boundary.

    IMPORTANT:
      - New: request.state.principal (Principal)
      - Backward-compat: request.state.user (dict) for app.core.auth.rbac.require_role()
    """

    def __init__(self, app, *, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        self.provider = None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled:
            p = Principal(subject="anonymous", roles=["admin"])
            request.state.principal = p
            request.state.user = _principal_to_user(p)
            return await call_next(request)

        if self.provider is None:
            self.provider = get_auth_provider()

        try:
            principal = self.provider.authenticate(request)
            if principal is None:
                principal = Principal(subject="anonymous", roles=["viewer"])

            request.state.principal = principal
            request.state.user = _principal_to_user(principal)

        except AuthError as e:
            # Enforce only for versioned enterprise surface
            if request.url.path.startswith("/api/v1") or request.url.path.startswith("/api/v2"):
                return JSONResponse(status_code=401, content={"detail": str(e)})

            # Legacy routes stay backward compatible
            p = Principal(subject="anonymous", roles=["admin"])
            request.state.principal = p
            request.state.user = _principal_to_user(p)

        return await call_next(request)


def should_enable_auth_middleware() -> bool:
    v = (os.getenv("COPILOT_AUTH_ENABLED", "true") or "true").strip().lower()
    return v not in ("0", "false", "no")
