from __future__ import annotations

from collections import Counter
from typing import Dict, Optional

from prometheus_client import Counter as PromCounter

# Requests counters (HTTP-level)
_REQUESTS = Counter()

# Named counters (custom)
_NAMED = Counter()

_PROM_REQUESTS = PromCounter(
    "copilot_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)


def reset_metrics() -> None:
    """
    Test helper: clears all counters to avoid cross-test leakage.
    Safe to call multiple times.
    """
    _REQUESTS.clear()
    _NAMED.clear()


def inc_http(method: str, path: str, status: Optional[int] = None) -> None:
    """
    Canonical HTTP metric increment used by middleware.
    """
    m = (method or "UNKNOWN").upper()
    p = path or "/"
    s = status if status is not None else "unknown"

    _REQUESTS["requests_total"] += 1
    _REQUESTS[f"requests_{m}"] += 1
    _REQUESTS[f"path_{p}"] += 1
    _REQUESTS[f"path_{p}|{s}"] += 1
    _PROM_REQUESTS.labels(method=m, path=p, status=str(s)).inc()


def inc_request(path: str, status: Optional[int]) -> None:
    """
    Backwards-compatible helper (older code may call this).
    Must also contribute to requests_total for contract consistency.
    """
    p = path or "/"
    s = status if status is not None else "unknown"

    _REQUESTS["requests_total"] += 1
    _REQUESTS[f"path_{p}|{s}"] += 1


def inc_named(name: str, value: int = 1) -> None:
    """
    Increment a named counter (used by health endpoints, etc.).
    """
    if not name:
        return
    _NAMED[name] += int(value)


def snapshot_requests() -> Dict[str, int]:
    return dict(_REQUESTS)


def snapshot_named() -> Dict[str, int]:
    return dict(_NAMED)


def snapshot() -> Dict[str, int]:
    """
    Backwards-compatible snapshot (older code may expect this).
    """
    return dict(_REQUESTS)
