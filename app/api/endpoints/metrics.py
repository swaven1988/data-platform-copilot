from fastapi import APIRouter
from app.core.observability.metrics import snapshot

router = APIRouter()


@router.get("/metrics/snapshot")
def metrics_snapshot():
    return {"requests": snapshot()}