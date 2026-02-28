from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import Response

from app.api.versioning import is_unversioned_api_path

from app.api.endpoints import build, repo, sync
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

# Modeling endpoints
from app.api.endpoints.modeling_preview import router as modeling_router
from app.api.endpoints.modeling_registry import router as modeling_registry_router
from app.api.endpoints.modeling_advanced import router as modeling_advanced_router
from app.api.endpoints.modeling_get import router as modeling_get_router

# Health + metrics endpoints
from app.api.endpoints import health
from app.api.endpoints import metrics as metrics_ep

from app.api.endpoints.contracts import router as contracts_router
from app.api.endpoints.plans import router as plans_router
from app.api.endpoints.intelligence import router as intelligence_router
from app.api.endpoints.policy_eval import router as policy_router
from app.api.endpoints.build_v3 import router as build_v3_router
from app.api.endpoints.runtime_profiles import router as runtime_profiles_router
from app.api.endpoints.spark_optimizer_api import router as spark_optimizer_router
from app.api.endpoints.ai_gateway import router as ai_gateway_router
from app.api.endpoints.intent_parse import router as intent_parse_router

from app.api.endpoints import preflight
from app.api.endpoints.execution import router as execution_router
from app.api.endpoints.billing import router as billing_router

from app.api.endpoints import supply_chain
from app.api.endpoints import system_status
from app.api.endpoints import executions_lifecycle

from app.api.middleware.error_shaping import SafeErrorMiddleware
from app.api.middleware.request_context import (
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    TenantIsolationMiddleware,
)
from app.api.middleware.audit import AuditMiddleware

from app.api.endpoints.health_mutating import router as health_mutating_router


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Data Platform Copilot API",
    version="0.1.0",
)

# ------------------------------------------------------------
# Middleware stack (ORDER MATTERS) — canonical
# Note: Starlette reverses add_middleware order — the LAST call = OUTERMOST wrapper.
# Desired runtime order (outermost → innermost):
#   SafeErrorMiddleware → CORSMiddleware → SecurityHeaders → RateLimit
#   → RequestContext → Audit → Auth → TenantIsolation → handler
# ------------------------------------------------------------

env = (os.getenv("COPILOT_ENV") or "dev").strip().lower()

# Tenant isolation (innermost of the stack — added first)
tenant_strict = (os.getenv("COPILOT_TENANT_STRICT") or "0").strip().lower() in ("1", "true", "yes")
default_tenant = (os.getenv("COPILOT_DEFAULT_TENANT") or "default").strip()
app.add_middleware(TenantIsolationMiddleware, strict=tenant_strict, default_tenant=default_tenant)

# Auth boundary:
# - Enabled by default in runtime
# - Disabled by default under pytest unless explicitly enabled via env
pytest_running = bool(os.getenv("PYTEST_CURRENT_TEST"))
auth_enabled = should_enable_auth_middleware()
if pytest_running and os.getenv("COPILOT_AUTH_ENABLED") is None:
    auth_enabled = False
app.add_middleware(AuthMiddleware, enabled=auth_enabled)

# Audit (needs tenant + actor available)
app.add_middleware(AuditMiddleware)

# Request context (request_id + metrics increment)
app.add_middleware(RequestContextMiddleware)

# Rate limiting (off by default)
rl_enabled = (os.getenv("COPILOT_RATE_LIMIT_ENABLED") or "0").strip().lower() in ("1", "true", "yes")
rl_rpm = int((os.getenv("COPILOT_RATE_LIMIT_RPM") or "120").strip())
app.add_middleware(RateLimitMiddleware, enabled=rl_enabled, rpm=rl_rpm)

# Security headers (on in prod by default if you want)
sec_enabled = (os.getenv("COPILOT_SECURITY_HEADERS_ENABLED") or ("true" if env == "prod" else "false")).strip().lower() in (
    "1",
    "true",
    "yes",
)
app.add_middleware(SecurityHeadersMiddleware, enabled=sec_enabled)

# Fix 5: CORSMiddleware — second-to-last so OPTIONS preflight is handled outside Auth
# (last-added = outermost; second-to-last = second outermost, after SafeErrorMiddleware)
_cors_origins_raw = os.getenv("COPILOT_CORS_ORIGINS", "").strip()
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()] if _cors_origins_raw else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fix 9: SafeErrorMiddleware LAST = outermost (catches all exceptions from inner middleware)
app.add_middleware(SafeErrorMiddleware)



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
app.include_router(contracts_router)
app.include_router(plans_router)
app.include_router(intelligence_router)
app.include_router(runtime_profiles_router)
app.include_router(spark_optimizer_router)
app.include_router(ai_gateway_router)
app.include_router(intent_parse_router)
app.include_router(policy_router)
app.include_router(build_v3_router)
app.include_router(preflight.router)
app.include_router(execution_router)
app.include_router(billing_router)

# IMPORTANT: do NOT include v1_router unversioned


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

    # NOTE: DO NOT include metrics_ep.router here since it already defines /api/v1/* and /api/v2/*
    # app.include_router(metrics_ep.router, prefix=prefix)

    # Modeling (IMPORTANT ORDER)
    app.include_router(modeling_registry_router, prefix=prefix)
    app.include_router(modeling_advanced_router, prefix=prefix)
    app.include_router(modeling_router, prefix=prefix)
    app.include_router(modeling_get_router, prefix=prefix)
    app.include_router(spark_optimizer_router, prefix=prefix)

# Tenanted router: v1 only
app.include_router(v1_router, prefix="/api/v1")

# v1-only extra surfaces
app.include_router(supply_chain.router, prefix="/api/v1")
app.include_router(system_status.router, prefix="/api/v1")
app.include_router(executions_lifecycle.router, prefix="/api/v1")
app.include_router(health_mutating_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "healthy"}
