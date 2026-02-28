"""Prometheus metrics scrape endpoint.

This module exposes a read-only scrape endpoint for Prometheus-compatible
collectors. It does not implement custom metric aggregation logic and does not
modify request handling behavior.
"""

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
