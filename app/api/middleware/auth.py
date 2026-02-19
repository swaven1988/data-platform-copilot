from __future__ import annotations

import logging
import os
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.auth.models import Principal
from app.core.auth.policy import required_role_for
from app.core.auth.provider import AuthError, get_auth_provider
from app.core.auth.rbac import enforce_required_role

log = logging.getLogger("copilot.auth")


def _principal_to_user(principal: Principal) -> dict:
    roles = set(principal.roles or [])
    if "admin" in roles:
        role = "admin"
    elif "viewer" in roles:
        role = "viewer"
    else:
        role = "viewer"

    return {"sub": principal.subject, "role": role, "roles": sorted(list(roles))}


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Stage 14: Auth boundary
    Stage 15: Central RBAC policy + audit logs for /api/v*
    """

    def __init__(self, app, *, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        self.provider = None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        method = request.method.upper()

        # If auth disabled: allow everything as admin (dev-only)
        if not self.enabled:
            p = Principal(subject="anonymous", roles=["admin"])
            request.state.principal = p
            request.state.user = _principal_to_user(p)
            return await call_next(request)

        if self.provider is None:
            self.provider = get_auth_provider()

        # -------------------------
        # Authenticate (strict only for /api/v*)
        # -------------------------
        try:
            principal = self.provider.authenticate(request)
            if principal is None:
                principal = Principal(subject="anonymous", roles=["viewer"])
            request.state.principal = principal
            request.state.user = _principal_to_user(principal)

        except AuthError as e:
            # Strict enforcement only for versioned enterprise surfaces
            if path.startswith("/api/v1") or path.startswith("/api/v2"):
                log.info(
                    "authz deny (unauthenticated) method=%s path=%s reason=%s",
                    method,
                    path,
                    str(e),
                )
                return JSONResponse(status_code=401, content={"detail": str(e)})

            # Legacy (unversioned) stays backward compatible
            p = Principal(subject="anonymous", roles=["admin"])
            request.state.principal = p
            request.state.user = _principal_to_user(p)

        # -------------------------
        # Stage 15: Central policy enforcement for /api/v*
        # -------------------------
        required = required_role_for(method, path)
        if required is not None:
            user_role = request.state.user.get("role") if getattr(request.state, "user", None) else None
            allowed = enforce_required_role(user_role=user_role, required_role=required)

            if not allowed:
                log.info(
                    "authz deny subject=%s role=%s required=%s method=%s path=%s",
                    request.state.user.get("sub"),
                    user_role,
                    required,
                    method,
                    path,
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Insufficient role",
                        "required_role": required,
                        "actual_role": user_role,
                    },
                )

            # Audit allow
            log.info(
                "authz allow subject=%s role=%s method=%s path=%s",
                request.state.user.get("sub"),
                user_role,
                method,
                path,
            )

        return await call_next(request)


def should_enable_auth_middleware() -> bool:
    v = (os.getenv("COPILOT_AUTH_ENABLED", "true") or "true").strip().lower()
    return v not in ("0", "false", "no")
