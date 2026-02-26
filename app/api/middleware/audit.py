from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.observability.audit import audit_event
from app.core.observability.metrics import inc_request


def _extract_actor(request: Request) -> str | None:
    # prefer auth middleware population if exists
    actor = getattr(request.state, "actor", None)
    if actor:
        return str(actor)

    # fallback to Authorization presence only (do not log token)
    auth = request.headers.get("Authorization")
    if auth:
        return "bearer"
    return None


def _extract_tenant(request: Request) -> str | None:
    tenant = getattr(request.state, "tenant_id", None)
    if tenant:
        return str(tenant)

    # common path format: /api/v1/tenants/{tenant}/...
    parts = request.url.path.split("/")
    try:
        idx = parts.index("tenants")
        return parts[idx + 1]
    except Exception:
        return None


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response | None = None
        status: int | None = None
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            rid = getattr(request.state, "request_id", None)
            audit_event(
                event_type="http_request",
                request_id=rid,
                actor=_extract_actor(request),
                tenant=_extract_tenant(request),
                method=request.method,
                path=request.url.path,
                status_code=status,
            )