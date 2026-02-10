from fastapi import FastAPI
from app.api.endpoints import build, repo, sync 

app = FastAPI(
    title="Data Platform Copilot API",
    version="0.1.0",
)

app.include_router(build.router)
app.include_router(repo.router)
app.include_router(sync.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
