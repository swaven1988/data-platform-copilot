from __future__ import annotations

import re
from prometheus_client import Counter, Histogram


def normalize_path(path: str) -> str:
    """Reduce high-cardinality paths for metrics labels."""
    p = path or "/"

    # UUID-ish
    p = re.sub(r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", "/:uuid", p)
    # long hex
    p = re.sub(r"/[0-9a-fA-F]{16,}", "/:hex", p)
    # ints
    p = re.sub(r"/\d+", "/:id", p)

    # Modeling names
    p = re.sub(r"^(/api/v[12]/modeling)/[^/]+$", r"\1/:name", p)
    # Tenants
    p = re.sub(r"^(/api/v1/tenants)/[^/]+/health$", r"\1/:tenant/health", p)

    return p


HTTP_REQUESTS_TOTAL = Counter(
    "copilot_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "copilot_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)

AUTHZ_DECISIONS_TOTAL = Counter(
    "copilot_authz_decisions_total",
    "Authorization decisions",
    ["decision", "required_role", "actual_role", "method", "path"],
)