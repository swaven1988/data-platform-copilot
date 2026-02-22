from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from fastapi import Request

from app.core.auth.models import Principal


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class StaticTokenConfig:
    allow_in_prod: bool
    admin_token: str
    viewer_token: str


class AuthProvider:
    def authenticate(self, request: Request) -> Optional[Principal]:
        raise NotImplementedError


class StaticTokenAuthProvider(AuthProvider):
    def __init__(self, cfg: StaticTokenConfig):
        self.cfg = cfg

    def authenticate(self, request: Request) -> Optional[Principal]:
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if not auth:
            raise AuthError("Missing Authorization header")

        parts = auth.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise AuthError("Invalid Authorization header (expected: Bearer <token>)")

        token = parts[1].strip()
        if not token:
            raise AuthError("Empty bearer token")

        if token == self.cfg.admin_token:
            return Principal(subject="static_token_admin", roles=["admin", "viewer"])

        if token == self.cfg.viewer_token:
            return Principal(subject="static_token_viewer", roles=["viewer"])

        raise AuthError("Invalid token")


def _read_secret_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            v = f.read().strip()
        if not v:
            raise AuthError(f"Secret file empty: {path}")
        return v
    except FileNotFoundError:
        raise AuthError(f"Secret file missing: {path}")


def get_auth_provider() -> AuthProvider:
    """
    Current prod baseline:
      COPILOT_AUTH_MODE=static_token
      COPILOT_ALLOW_STATIC_TOKEN_IN_PROD=true (explicit)
      tokens via /run/secrets/admin_token and /run/secrets/viewer_token
    """
    env = (os.getenv("COPILOT_ENV", "dev") or "dev").strip().lower()
    mode = (os.getenv("COPILOT_AUTH_MODE", "static_token") or "static_token").strip().lower()

    if mode != "static_token":
        raise AuthError(f"Unsupported COPILOT_AUTH_MODE={mode} (supported: static_token)")

    allow_in_prod = (os.getenv("COPILOT_ALLOW_STATIC_TOKEN_IN_PROD", "false") or "false").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if env == "prod" and not allow_in_prod:
        raise AuthError("static_token auth is disabled in prod (set COPILOT_ALLOW_STATIC_TOKEN_IN_PROD=true to override)")

    admin_path = os.getenv("COPILOT_ADMIN_TOKEN_FILE", "/run/secrets/admin_token")
    viewer_path = os.getenv("COPILOT_VIEWER_TOKEN_FILE", "/run/secrets/viewer_token")

    cfg = StaticTokenConfig(
        allow_in_prod=allow_in_prod,
        admin_token=_read_secret_file(admin_path),
        viewer_token=_read_secret_file(viewer_path),
    )
    return StaticTokenAuthProvider(cfg)
