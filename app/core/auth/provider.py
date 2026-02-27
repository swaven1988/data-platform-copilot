# app/core/auth/provider.py
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

from fastapi import Request

from app.core.auth.models import Principal

_log = logging.getLogger("copilot.auth")


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
    with open(path, "r", encoding="utf-8") as f:
        v = f.read().strip()
    if not v:
        raise AuthError(f"Secret file empty: {path}")
    return v


def _is_truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in ("1", "true", "yes", "y", "on")


def get_auth_provider() -> AuthProvider:
    """
    Prod:
      - COPILOT_ENV=prod
      - COPILOT_AUTH_MODE=static_token
      - COPILOT_ALLOW_STATIC_TOKEN_IN_PROD=true
      - tokens via /run/secrets/*
    Dev/Test:
      - allow env tokens OR fall back to default dev_* tokens (for tests)
    """
    env = (os.getenv("COPILOT_ENV", "dev") or "dev").strip().lower()
    mode = (os.getenv("COPILOT_AUTH_MODE", "static_token") or "static_token").strip().lower()

    if mode != "static_token":
        raise AuthError(f"Unsupported COPILOT_AUTH_MODE={mode} (supported: static_token)")

    allow_in_prod = _is_truthy(os.getenv("COPILOT_ALLOW_STATIC_TOKEN_IN_PROD", "false"))

    # Prefer explicit env tokens (works for tests/CI/dev)
    admin_env = (os.getenv("COPILOT_ADMIN_TOKEN") or "").strip()
    viewer_env = (os.getenv("COPILOT_VIEWER_TOKEN") or "").strip()
    if admin_env and viewer_env:
        return StaticTokenAuthProvider(
            StaticTokenConfig(allow_in_prod=allow_in_prod, admin_token=admin_env, viewer_token=viewer_env)
        )

    # Prod: must read secrets; never default
    if env == "prod":
        if not allow_in_prod:
            raise AuthError(
                "static_token auth is disabled in prod (set COPILOT_ALLOW_STATIC_TOKEN_IN_PROD=true to override)"
            )

        admin_path = os.getenv("COPILOT_ADMIN_TOKEN_FILE", "/run/secrets/admin_token")
        viewer_path = os.getenv("COPILOT_VIEWER_TOKEN_FILE", "/run/secrets/viewer_token")

        try:
            admin_token = _read_secret_file(admin_path)
            viewer_token = _read_secret_file(viewer_path)
        except FileNotFoundError:
            raise AuthError(f"Secret file missing: {admin_path} or {viewer_path}")

        return StaticTokenAuthProvider(
            StaticTokenConfig(allow_in_prod=allow_in_prod, admin_token=admin_token, viewer_token=viewer_token)
        )

    # Dev/Test: try secret files if present, else fall back to defaults used in your curl/tests
    admin_path = os.getenv("COPILOT_ADMIN_TOKEN_FILE", "/run/secrets/admin_token")
    viewer_path = os.getenv("COPILOT_VIEWER_TOKEN_FILE", "/run/secrets/viewer_token")

    try:
        admin_token = _read_secret_file(admin_path)
        viewer_token = _read_secret_file(viewer_path)
        return StaticTokenAuthProvider(
            StaticTokenConfig(allow_in_prod=allow_in_prod, admin_token=admin_token, viewer_token=viewer_token)
        )
    except FileNotFoundError:
        # Guard: never fall back to default dev tokens in prod
        _env = (os.getenv("COPILOT_ENV", "dev") or "dev").strip().lower()
        if _env == "prod":
            raise AuthError(
                "FATAL: Running in prod with no token configuration. "
                "Set COPILOT_ADMIN_TOKEN + COPILOT_VIEWER_TOKEN or configure secret files."
            )
        _log.warning(
            "AUTH: Using default dev tokens (dev_admin_token / dev_viewer_token). "
            "This is insecure. Set COPILOT_ADMIN_TOKEN and COPILOT_VIEWER_TOKEN env vars."
        )
        # Default dev tokens (matches existing curl/test usage)
        return StaticTokenAuthProvider(
            StaticTokenConfig(allow_in_prod=allow_in_prod, admin_token="dev_admin_token", viewer_token="dev_viewer_token")
        )