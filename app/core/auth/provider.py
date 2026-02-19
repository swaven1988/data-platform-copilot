from __future__ import annotations

import os
from typing import Optional

from fastapi import Request

from .models import Principal


class AuthError(RuntimeError):
    pass


class AuthProvider:
    def authenticate(self, request: Request) -> Optional[Principal]:
        raise NotImplementedError


class NoAuthProvider(AuthProvider):
    def authenticate(self, request: Request) -> Optional[Principal]:
        return Principal(subject="anonymous", roles=["admin"])


class StaticTokenProvider(AuthProvider):
    """
    Simple enterprise simulation:
    - Requires Authorization: Bearer <token>
    - Token must match COPILOT_ADMIN_TOKEN
    - Principal role = admin
    """

    def __init__(self, token: str):
        self._token = token.strip()

    def authenticate(self, request: Request) -> Optional[Principal]:
        auth = (request.headers.get("authorization") or "").strip()
        if not auth.lower().startswith("bearer "):
            raise AuthError("Missing bearer token")
        token = auth.split(" ", 1)[1].strip()
        if not token or token != self._token:
            raise AuthError("Invalid bearer token")
        return Principal(subject="admin_token", roles=["admin"])


class HeaderProvider(AuthProvider):
    """
    Trust boundary for reverse proxy:
    - Reads X-Forwarded-User and X-Forwarded-Roles
    - Example:
      X-Forwarded-User: user@company.com
      X-Forwarded-Roles: admin,user
    """

    def authenticate(self, request: Request) -> Optional[Principal]:
        user = (request.headers.get("x-forwarded-user") or "").strip()
        roles = (request.headers.get("x-forwarded-roles") or "").strip()
        if not user:
            raise AuthError("Missing x-forwarded-user")
        role_list = [r.strip() for r in roles.split(",") if r.strip()] or ["user"]
        return Principal(subject=user, roles=role_list)


def get_auth_provider() -> AuthProvider:
    mode = (os.getenv("COPILOT_AUTH_MODE", "none") or "none").strip().lower()

    if mode == "none":
        return NoAuthProvider()

    if mode == "static_token":
        token = (os.getenv("COPILOT_ADMIN_TOKEN", "") or "").strip()
        if not token:
            raise AuthError("COPILOT_ADMIN_TOKEN is not set for static_token auth mode")
        return StaticTokenProvider(token=token)

    if mode == "header":
        return HeaderProvider()

    raise AuthError(f"Unknown COPILOT_AUTH_MODE: {mode}")
