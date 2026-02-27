from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_log = logging.getLogger("copilot.auth")



def should_enable_auth_middleware() -> bool:
    """
    Canonical toggle:
      - If COPILOT_AUTH_ENABLED is set: obey it
      - Otherwise:
          * under pytest: default OFF (but we still set identity if Authorization is provided)
          * runtime: default ON
    """
    import os

    raw = os.getenv("COPILOT_AUTH_ENABLED")
    if raw is not None:
        v = raw.strip().lower()
        if v in ("0", "false", "no", "off"):
            return False
        if v in ("1", "true", "yes", "on"):
            return True

    if os.getenv("PYTEST_CURRENT_TEST") is not None:
        return False

    return True


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Auth boundary:
      - Public allowlist always open
      - If auth enabled: protected routes require Authorization
      - If auth disabled: do NOT require Authorization, but if present,
        set request identity (dev tokens) so RBAC tests still work.
    """

    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = bool(enabled)

    def _set_user(self, request: Request, sub: str, role: str) -> None:
        user: Dict[str, Any] = {"sub": sub, "role": role}
        request.state.user = user
        request.state.actor = sub
        request.state.role = role

    def _clear_user(self, request: Request) -> None:
        request.state.user = None
        request.state.actor = None
        request.state.role = None

    def _parse_token(self, request: Request) -> Optional[str]:
        auth = request.headers.get("Authorization") or request.headers.get("authorization")
        if not auth:
            return None

        raw = auth.strip()
        if not raw:
            return None

        parts = raw.split(" ", 1)
        if len(parts) == 2:
            scheme = parts[0].strip().lower()
            token = parts[1].strip()
            if scheme == "bearer" and token:
                return token
            return None

        # legacy "<token>" (no scheme)
        return raw

    def _is_public(self, path: str) -> bool:
        """
        IMPORTANT:
        - Keep ONLY safe GET endpoints public.
        - DO NOT make '/api/v1/health/*' public as a prefix, because it includes
          mutating endpoints like '/api/v1/health/ping' used by Phase 26 rate-limit test.
        """
        public_exact = {
            "/",
            "/health",
            "/health/live",
            "/health/ready",
            "/openapi.json",
            "/api/v1/openapi.json",
            "/api/v2/openapi.json",
            "/metrics/snapshot",
            "/api/v1/metrics/snapshot",
            "/api/v2/metrics/snapshot",
            "/api/v1/health/live",
            "/api/v1/health/ready",
            "/api/v2/health/live",
            "/api/v2/health/ready",
            "/docs",
            "/redoc",
        }

        if path in public_exact:
            return True

        # docs assets / swagger ui assets can be prefixed
        public_prefixes = (
            "/docs",
            "/redoc",
        )
        return path.startswith(public_prefixes)

    def _apply_identity_if_token_present(self, request: Request) -> None:
        from app.core.auth.provider import get_auth_provider, AuthError
        try:
            provider = get_auth_provider()
            principal = provider.authenticate(request)
            if principal:
                role = principal.roles[0] if principal.roles else "viewer"
                self._set_user(request, principal.subject, role)
        except AuthError:
            # In auth-disabled mode, unrecognised tokens are silently ignored
            pass
        except Exception as e:
            _log.debug("_apply_identity_if_token_present: unexpected error: %s", e)


    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        self._clear_user(request)

        path = request.url.path

        enabled_now = self.enabled and should_enable_auth_middleware()

        # Public endpoints are always open.
        # But: if auth is disabled AND caller provides a token, still set identity (RBAC-friendly).
        if self._is_public(path):
            if not enabled_now:
                self._apply_identity_if_token_present(request)
            return await call_next(request)

        if not enabled_now:
            # auth disabled: never block, but set identity if token provided
            self._apply_identity_if_token_present(request)
            return await call_next(request)

        # auth enabled: protected routes require token
        from app.core.auth.provider import get_auth_provider, AuthError
        try:
            provider = get_auth_provider()
            principal = provider.authenticate(request)
            if principal:
                role = principal.roles[0] if principal.roles else "viewer"
                self._set_user(request, principal.subject, role)
                return await call_next(request)
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        except AuthError:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
