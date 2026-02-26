from __future__ import annotations

from typing import Iterable


VERSIONED_PREFIXES: tuple[str, ...] = ("/api/v1/", "/api/v2/")


def is_versioned_path(path: str) -> bool:
    return any(path.startswith(p) for p in VERSIONED_PREFIXES)


def is_unversioned_api_path(path: str, *, allow: Iterable[str] = ()) -> bool:
    if is_versioned_path(path):
        return False
    if path.startswith("/docs") or path.startswith("/openapi.json") or path.startswith("/redoc"):
        return False
    for p in allow:
        if path.startswith(p):
            return False
    return True
