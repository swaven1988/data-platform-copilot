from fastapi import APIRouter
from app.core.observability.metrics import snapshot_named, snapshot_requests

router = APIRouter()


def _render():
    req = snapshot_requests()
    body = {"requests": req}
    body.update(snapshot_named())

    # Compatibility: expose common totals at top-level (tests expect this)
    for k in ("requests_total", "requests_GET", "requests_POST", "requests_PUT", "requests_DELETE", "requests_PATCH"):
        if k in req:
            body[k] = req[k]

    return body


@router.get("/metrics/snapshot")
def metrics_snapshot():
    return _render()


@router.get("/api/v1/metrics/snapshot")
def metrics_snapshot_v1():
    return _render()


@router.get("/api/v2/metrics/snapshot")
def metrics_snapshot_v2():
    return _render()