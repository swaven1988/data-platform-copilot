from fastapi import APIRouter
from app.core.observability.metrics import snapshot

router = APIRouter()


@router.get(
    "/metrics/snapshot",
    operation_id="metrics_snapshot_v1_get",
)
def metrics_snapshot():
    return {"requests": snapshot()}
