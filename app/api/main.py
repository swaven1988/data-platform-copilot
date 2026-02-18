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

app = FastAPI(
    title="Data Platform Copilot API",
    version="0.1.0",
)

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


@app.get("/health")
def health_check():
    return {"status": "ok"}
