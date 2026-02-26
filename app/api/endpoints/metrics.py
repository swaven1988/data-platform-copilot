from __future__ import annotations

from fastapi import APIRouter
from starlette.responses import Response

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


router = APIRouter(tags=["observability"])


@router.get("/metrics")
def metrics() -> Response:
    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)