from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.observability.metrics import inc_http


# ------------------------------------------------------------
# RequestContextMiddleware
# - assigns request_id
# - attaches to request.state
# - echoes X-Request-Id in response
# - increments HTTP metrics (single source of truth)
# ------------------------------------------------------------
class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        rid = (request.headers.get("X-Request-Id") or "").strip()
        if not rid:
            rid = str(uuid.uuid4())

        request.state.request_id = rid

        resp: Response = await call_next(request)
        resp.headers.setdefault("X-Request-Id", rid)

        # single metrics system
        inc_http(request.method, request.url.path, getattr(resp, "status_code", None))

        return resp


# ------------------------------------------------------------
# SecurityHeadersMiddleware
# ------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = bool(enabled)

    def _env_enabled(self) -> bool:
        env = (os.getenv("COPILOT_ENV") or "dev").strip().lower()
        raw = os.getenv("COPILOT_SECURITY_HEADERS_ENABLED")
        if raw is None:
            # default: ON in prod, OFF elsewhere
            return env == "prod"
        return raw.strip().lower() in ("1", "true", "yes", "on")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        resp: Response = await call_next(request)

        enabled = self.enabled and self._env_enabled()
        if not enabled:
            return resp

        # minimal, safe defaults
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("X-XSS-Protection", "0")
        return resp


# ------------------------------------------------------------
# RateLimitMiddleware
# - env-toggle must work after app import (pytest monkeypatch)
# - apply to mutating methods (POST/PUT/PATCH/DELETE)
# ------------------------------------------------------------
@dataclass
class _Bucket:
    window_start: float
    count: int


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, enabled: bool = False, rpm: int = 120):
        super().__init__(app)
        self.enabled = bool(enabled)
        self.rpm = int(rpm)
        self._buckets: Dict[str, _Bucket] = {}

    def _env_enabled(self) -> bool:
        raw = os.getenv("COPILOT_RATE_LIMIT_ENABLED")
        if raw is None:
            return self.enabled
        return raw.strip().lower() in ("1", "true", "yes", "on")

    def _env_rpm(self) -> int:
        raw = os.getenv("COPILOT_RATE_LIMIT_RPM")
        if raw is None:
            return max(1, int(self.rpm))
        try:
            return max(1, int(raw.strip()))
        except Exception:
            return max(1, int(self.rpm))

    def _client_key(self, request: Request) -> str:
        # prefer forwarded-for for tests / gateways
        xff = (request.headers.get("X-Forwarded-For") or "").strip()
        ip = xff.split(",")[0].strip() if xff else None
        if not ip:
            ip = getattr(getattr(request, "client", None), "host", None) or "unknown"

        tenant = getattr(request.state, "tenant", None) or (request.headers.get("X-Tenant") or "").strip() or "default"
        return f"{ip}|{tenant}"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method.upper() not in ("POST", "PUT", "PATCH", "DELETE"):
            return await call_next(request)

        if not self._env_enabled():
            return await call_next(request)

        rpm = self._env_rpm()
        now = time.time()
        key = self._client_key(request)

        bucket = self._buckets.get(key)
        if bucket is None or (now - bucket.window_start) >= 60.0:
            bucket = _Bucket(window_start=now, count=0)
            self._buckets[key] = bucket

        bucket.count += 1
        if bucket.count > rpm:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

        return await call_next(request)


# ------------------------------------------------------------
# TenantIsolationMiddleware
# - default tenant if missing except billing + /tenants/*
# - enforce /tenants/{t} matches header tenant (when header present)
# ------------------------------------------------------------
class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Tenant behavior:
      - If X-Tenant is missing:
          * for billing endpoints and /tenants/* endpoints -> 400
          * otherwise -> default_tenant is applied
      - If path includes /tenants/{t}/... then header tenant must match => 403
    """

    def __init__(self, app, strict: bool = False, default_tenant: str = "default"):
        super().__init__(app)
        self.strict = bool(strict)
        self.default_tenant = (default_tenant or "default").strip() or "default"

    def _is_public(self, path: str) -> bool:
        public_prefixes = (
            "/health",
            "/api/v1/health",
            "/api/v2/health",
            "/metrics",
            "/api/v1/metrics",
            "/api/v2/metrics",
            "/openapi.json",
            "/api/v1/openapi.json",
            "/api/v2/openapi.json",
            "/docs",
            "/redoc",
        )
        return path == "/" or path.startswith(public_prefixes)

    def _requires_explicit_tenant(self, path: str) -> bool:
        if path.startswith("/api/v1/billing") or path.startswith("/api/v2/billing"):
            return True
        if path.startswith("/api/v1/tenants/") or path.startswith("/api/v2/tenants/"):
            return True
        return False

    def _extract_tenant_from_path(self, path: str) -> Optional[str]:
        # /api/v1/tenants/{tenant}/...
        parts = [p for p in path.split("/") if p]
        # ["api","v1","tenants","{tenant}",...]
        if len(parts) >= 4 and parts[0] == "api" and parts[2] == "tenants":
            return parts[3]
        return None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        header_tenant = (request.headers.get("X-Tenant") or "").strip()
        tenant = header_tenant or self.default_tenant

        if not self._is_public(path):
            if not header_tenant and self._requires_explicit_tenant(path):
                return JSONResponse(status_code=400, content={"detail": "Missing X-Tenant header"})

            path_tenant = self._extract_tenant_from_path(path)
            if path_tenant and header_tenant and path_tenant != header_tenant:
                return JSONResponse(status_code=403, content={"detail": "Cross-tenant request denied"})

            if self.strict and not header_tenant:
                return JSONResponse(status_code=400, content={"detail": "Missing X-Tenant header"})

        request.state.tenant = tenant
        return await call_next(request)