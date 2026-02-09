from fastapi import FastAPI
from app.api.endpoints import build, repo

app = FastAPI(
    title="Data Platform Copilot API",
    version="0.1.0",
)

app.include_router(build.router)
app.include_router(repo.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
