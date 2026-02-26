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

from app.api.observability.metrics import (
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    normalize_path,
)

from app.core.observability.metrics import inc_request as inc_request_core


def _json_log(event: str, **fields):
    msg = {"event": event, **fields}
    log.info("%s", msg)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Request ID + structured request logs + metrics.
    Keeps request_id coherent if another middleware already set it.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # respect existing request_id if already set by RequestIdMiddleware
        rid = getattr(request.state, "request_id", None) or request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = rid

        start = time.time()
        resp = await call_next(request)
        dur_ms = int((time.time() - start) * 1000)

        resp.headers.setdefault("X-Request-Id", rid)

        # Metrics (Prometheus)
        p = normalize_path(request.url.path)
        m = request.method.upper()
        s = str(getattr(resp, "status_code", 0))
        HTTP_REQUESTS_TOTAL.labels(method=m, path=p, status=s).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=m, path=p).observe(dur_ms / 1000.0)

        # Metrics (snapshot backing store)
        inc_request_core(p, getattr(resp, "status_code", None))

        if request.url.path.startswith("/api/"):
            tenant: Optional[str] = getattr(request.state, "tenant", None) or getattr(request.state, "tenant_id", None)
            user = getattr(request.state, "user", None) or {}
            _json_log(
                "request",
                request_id=rid,
                method=request.method,
                path=request.url.path,
                status_code=resp.status_code,
                duration_ms=dur_ms,
                tenant=tenant,
                sub=user.get("sub"),
                role=user.get("role"),
            )
        return resp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        resp = await call_next(request)
        if not self.enabled:
            return resp

        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        resp.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        return resp


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, enabled: bool = False, rpm: int = 120):
        super().__init__(app)
        self.enabled = enabled
        self.rpm = max(10, int(rpm))
        self._bucket = {}  # key -> (window_start_epoch_minute, count)

    def _key(self, request: Request) -> str:
        xf = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        ip = (xf.split(",")[0].strip() if xf else request.client.host) if request.client else "unknown"
        return ip

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled:
            return await call_next(request)

        now_min = int(time.time() // 60)
        key = self._key(request)
        win, cnt = self._bucket.get(key, (now_min, 0))

        if win != now_min:
            win, cnt = now_min, 0

        cnt += 1
        self._bucket[key] = (win, cnt)

        if cnt > self.rpm:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

        return await call_next(request)


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Tenant isolation:
      - reads X-Tenant or tenant in path (/api/v1/tenants/{tenant}/...)
      - sets request.state.tenant AND request.state.tenant_id (alias)
      - strict mode enforces explicit tenant for versioned APIs
    """

    def __init__(self, app, strict: bool = False, default_tenant: str = "default"):
        super().__init__(app)
        self.strict = strict
        self.default_tenant = default_tenant

    def _extract_path_tenant(self, path: str) -> Optional[str]:
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

        # only versioned surfaces
        if not (path.startswith("/api/v1") or path.startswith("/api/v2")):
            request.state.tenant = self.default_tenant
            request.state.tenant_id = self.default_tenant
            return await call_next(request)

        # allow no-tenant probes
        if path.startswith("/api/v1/health/") or path.startswith("/api/v2/health/"):
            request.state.tenant = self.default_tenant
            request.state.tenant_id = self.default_tenant
            return await call_next(request)

        if path.startswith("/api/v1/metrics") or path.startswith("/api/v2/metrics"):
            request.state.tenant = self.default_tenant
            request.state.tenant_id = self.default_tenant
            return await call_next(request)

        header_tenant = request.headers.get("x-tenant") or request.headers.get("X-Tenant")
        path_tenant = self._extract_path_tenant(path)

        if self.strict and not header_tenant and not path_tenant:
            return JSONResponse(status_code=400, content={"detail": "Missing X-Tenant header"})

        effective = header_tenant or path_tenant or self.default_tenant

        request.state.tenant = effective
        request.state.tenant_id = effective  # alias for older codepaths

        if self.strict and path_tenant and header_tenant and (path_tenant != header_tenant):
            return JSONResponse(
                status_code=403,
                content={"detail": "Tenant mismatch", "path_tenant": path_tenant, "header_tenant": header_tenant},
            )

        return await call_next(request)