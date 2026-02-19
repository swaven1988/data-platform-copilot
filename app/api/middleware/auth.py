from __future__ import annotations

import os
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.auth.provider import AuthError, get_auth_provider
from app.core.auth.models import Principal


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Pluggable auth boundary.
    Default: COPILOT_AUTH_MODE=none -> allow.
    """

    def __init__(self, app, *, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        self.provider = None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled:
            request.state.principal = Principal(subject="anonymous", roles=["admin"])
            return await call_next(request)

        if self.provider is None:
            self.provider = get_auth_provider()

        try:
            principal = self.provider.authenticate(request)
            request.state.principal = principal or Principal(subject="anonymous", roles=["user"])
        except AuthError as e:
            # Only enforce auth for /v1 routes (enterprise surface)
            # Keep legacy routes backward compatible.
            if request.url.path.startswith("/v1/"):
                return Response(content=f'{{"detail":"{str(e)}"}}', status_code=401, media_type="application/json")
            request.state.principal = Principal(subject="anonymous", roles=["admin"])

        return await call_next(request)


def should_enable_auth_middleware() -> bool:
    # Allow turning off in dev/test explicitly
    v = (os.getenv("COPILOT_AUTH_ENABLED", "true") or "true").strip().lower()
    return v not in ("0", "false", "no")
