from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Callable, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

log = logging.getLogger("copilot.request")


def _json_log(event: str, **fields):
    # Structured log in a single line; tokens are never logged.
    msg = {"event": event, **fields}
    log.info("%s", msg)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Stage 19: Request ID + basic structured audit fields (no secrets).

    Adds:
      request.state.request_id
      response header: X-Request-Id
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = rid

        start = time.time()
        resp = await call_next(request)
        dur_ms = int((time.time() - start) * 1000)

        resp.headers["X-Request-Id"] = rid

        if request.url.path.startswith("/api/"):
            _json_log(
                "request",
                request_id=rid,
                method=request.method,
                path=request.url.path,
                status_code=resp.status_code,
                duration_ms=dur_ms,
            )
        return resp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Stage 20: Security headers (enabled in prod by default).
    """

    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        resp = await call_next(request)
        if not self.enabled:
            return resp

        # Safe defaults; UI is proxied; keep CSP minimal.
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        resp.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        return resp


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Stage 20: Very small in-memory rate limit (best-effort).
    Controlled by:
      COPILOT_RATE_LIMIT_ENABLED=true/false
      COPILOT_RATE_LIMIT_RPM=120  (requests per minute)
    """

    def __init__(self, app, enabled: bool = False, rpm: int = 120):
        super().__init__(app)
        self.enabled = enabled
        self.rpm = max(10, int(rpm))
        self._bucket = {}  # key -> (window_start_epoch_minute, count)

    def _key(self, request: Request) -> str:
        # Prefer real client ip if behind proxy.
        xf = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        ip = (xf.split(",")[0].strip() if xf else request.client.host) if request.client else "unknown"
        return ip

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled:
            return await call_next(request)

        # Only rate limit API surface
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        key = self._key(request)
        minute = int(time.time() // 60)

        win, cnt = self._bucket.get(key, (minute, 0))
        if win != minute:
            win, cnt = minute, 0

        cnt += 1
        self._bucket[key] = (win, cnt)

        if cnt > self.rpm:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

        return await call_next(request)


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Stage 18: Tenant isolation.
    Enforces that X-Tenant (or tenant in path) matches allowed tenant.
    Defaults:
      - Dev: relaxed
      - Prod: strict for /api/v1/tenants/{tenant}/...
    Env:
      COPILOT_TENANT_STRICT=true/false
      COPILOT_DEFAULT_TENANT=default
    """

    def __init__(self, app, strict: bool = False, default_tenant: str = "default"):
        super().__init__(app)
        self.strict = strict
        self.default_tenant = default_tenant

    def _extract_path_tenant(self, path: str) -> Optional[str]:
        # /api/v1/tenants/<tenant>/...
        parts = path.split("/")
        try:
            i = parts.index("tenants")
            return parts[i + 1] if len(parts) > i + 1 else None
        except ValueError:
            return None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)

        header_tenant = request.headers.get("x-tenant") or request.headers.get("X-Tenant")
        path_tenant = self._extract_path_tenant(path)

        # choose effective tenant
        effective = header_tenant or path_tenant or self.default_tenant
        request.state.tenant = effective

        if self.strict and path_tenant and header_tenant and (path_tenant != header_tenant):
            return JSONResponse(
                status_code=403,
                content={"detail": "Tenant mismatch", "path_tenant": path_tenant, "header_tenant": header_tenant},
            )

        return await call_next(request)
