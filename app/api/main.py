from fastapi import FastAPI
from app.api.endpoints import build, repo, sync
from app.api.plan_api import router as plan_router
from app.api.plugins_api import router as plugins_router
from app.api.routes import plugins as plugins_routes
from app.api.routes import advisors as advisors_routes
from app.api import execution
from app.api.endpoints import intelligence


app = FastAPI(
    title="Data Platform Copilot API",
    version="0.1.0",
)

app.include_router(build.router)
app.include_router(repo.router)
app.include_router(sync.router)
app.include_router(plan_router)
app.include_router(plugins_routes.router)
app.include_router(advisors_routes.router)
app.include_router(execution.router)
app.include_router(intelligence.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
