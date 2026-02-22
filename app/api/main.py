import os

from fastapi import FastAPI, Request
from fastapi.responses import Response

from app.api.versioning import is_unversioned_api_path

from app.api.endpoints import build, repo, sync, intelligence
from app.api.endpoints import semantic_diff, conflicts, remotes, impact_graph
from app.api.plan_api import router as plan_router
from app.api.routes import plugins as plugins_routes
from app.api.routes import advisors as advisors_routes
from app.api import execution

from app.api.endpoints.advisor_explain import router as advisor_explain_router
from app.api.endpoints.workspace_repro import router as workspace_repro_router
from app.api.endpoints.audit import router as audit_router

from app.api.endpoints.repro_compare import router as repro_compare_router
from app.api.endpoints.release_verify import router as release_verify_router

from app.api.endpoints.federation import router as federation_router
from app.api.endpoints.workspace_verify import router as workspace_verify_router

from app.api.endpoints.v1_tenanted import router as v1_router

from app.api.middleware.auth import AuthMiddleware, should_enable_auth_middleware
from app.api.middleware.request_context import (
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    TenantIsolationMiddleware,
)

# Modeling endpoints
from app.api.endpoints.modeling_preview import router as modeling_router
from app.api.endpoints.modeling_registry import router as modeling_registry_router
from app.api.endpoints.modeling_advanced import router as modeling_advanced_router
from app.api.endpoints.modeling_get import router as modeling_get_router

# Health endpoints
from app.api.endpoints import health
from app.api.endpoints import metrics as metrics_ep


app = FastAPI(
    title="Data Platform Copilot API",
    version="0.1.0",
)

# include health routes AFTER app is defined
# app.include_router(health.router)

# ------------------------------------------------------------
# Middleware stack (ORDER MATTERS)
# ------------------------------------------------------------

# Request id + structured API request logs (no secrets)
app.add_middleware(RequestContextMiddleware)

# Tenant isolation (strict in prod by default)
env = (os.getenv("COPILOT_ENV") or "dev").strip().lower()
tenant_strict = (os.getenv("COPILOT_TENANT_STRICT") or ("true" if env == "prod" else "false")).strip().lower() in (
    "1",
    "true",
    "yes",
)
default_tenant = (os.getenv("COPILOT_DEFAULT_TENANT") or "default").strip()
app.add_middleware(TenantIsolationMiddleware, strict=tenant_strict, default_tenant=default_tenant)

# Auth boundary
app.add_middleware(AuthMiddleware, enabled=should_enable_auth_middleware())

# Rate limiting (off by default)
rl_enabled = (os.getenv("COPILOT_RATE_LIMIT_ENABLED") or "false").strip().lower() in ("1", "true", "yes")
rl_rpm = int((os.getenv("COPILOT_RATE_LIMIT_RPM") or "120").strip())
app.add_middleware(RateLimitMiddleware, enabled=rl_enabled, rpm=rl_rpm)

# Security headers (on in prod by default)
sec_enabled = (os.getenv("COPILOT_SECURITY_HEADERS_ENABLED") or ("true" if env == "prod" else "false")).strip().lower() in (
    "1",
    "true",
    "yes",
)
app.add_middleware(SecurityHeadersMiddleware, enabled=sec_enabled)

# ------------------------------------------------------------
# Deprecation headers for unversioned endpoints
# ------------------------------------------------------------
@app.middleware("http")
async def add_deprecation_headers_for_unversioned(request: Request, call_next):
    resp: Response = await call_next(request)

    path = request.url.path
    if is_unversioned_api_path(path):
        resp.headers.setdefault("Deprecation", "true")
        resp.headers.setdefault("Sunset", "Sat, 31 May 2026 00:00:00 GMT")
        resp.headers.setdefault("Link", '</api/v2>; rel="latest-version"')

    return resp


# ------------------------------------------------------------
# Unversioned (backward-compat) — deprecated aliases
# ------------------------------------------------------------
app.include_router(build.router)
app.include_router(repo.router)
app.include_router(semantic_diff.router)
app.include_router(conflicts.router)
app.include_router(remotes.router)
app.include_router(impact_graph.router)
app.include_router(sync.router)
app.include_router(plan_router)
app.include_router(plugins_routes.router)
app.include_router(advisors_routes.router)
app.include_router(execution.router)
app.include_router(intelligence.router)
app.include_router(advisor_explain_router)
app.include_router(workspace_repro_router)
app.include_router(audit_router)
app.include_router(repro_compare_router)
app.include_router(release_verify_router)
app.include_router(health.router)
app.include_router(metrics_ep.router)
app.include_router(federation_router)
app.include_router(workspace_verify_router)
app.include_router(modeling_registry_router)
app.include_router(modeling_advanced_router)
app.include_router(modeling_router)
app.include_router(modeling_get_router)

# IMPORTANT: do NOT include v1_router unversioned anymore

# ------------------------------------------------------------
# Versioned (authoritative)
#   - /api/v1 frozen
#   - /api/v2 evolving
# ------------------------------------------------------------
for prefix in ("/api/v1", "/api/v2"):
    app.include_router(build.router, prefix=prefix)
    app.include_router(repo.router, prefix=prefix)
    app.include_router(semantic_diff.router, prefix=prefix)
    app.include_router(conflicts.router, prefix=prefix)
    app.include_router(remotes.router, prefix=prefix)
    app.include_router(impact_graph.router, prefix=prefix)
    app.include_router(sync.router, prefix=prefix)
    app.include_router(plan_router, prefix=prefix)
    app.include_router(plugins_routes.router, prefix=prefix)
    app.include_router(advisors_routes.router, prefix=prefix)
    app.include_router(execution.router, prefix=prefix)
    app.include_router(intelligence.router, prefix=prefix)
    app.include_router(metrics_ep.router, prefix=prefix)

    # Modeling (IMPORTANT ORDER)
    app.include_router(modeling_registry_router, prefix=prefix)
    app.include_router(modeling_advanced_router, prefix=prefix)
    app.include_router(modeling_router, prefix=prefix)
    app.include_router(modeling_get_router, prefix=prefix)

# Tenanted router: v1 only
app.include_router(v1_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "healthy"}