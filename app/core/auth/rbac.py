from __future__ import annotations

from typing import Callable, List

from fastapi import Depends, HTTPException, Request

from .models import Principal


def _principal_from_request(request: Request) -> Principal:
    p = getattr(request.state, "principal", None)
    if not p:
        # if middleware not installed for some reason, deny
        raise HTTPException(status_code=401, detail="Unauthenticated")
    return p


def require_roles(allowed: List[str]) -> Callable:
    def _dep(principal: Principal = Depends(_principal_from_request)) -> Principal:
        if not principal.has_any_role(allowed):
            raise HTTPException(status_code=403, detail="Forbidden")
        return principal

    return _dep
