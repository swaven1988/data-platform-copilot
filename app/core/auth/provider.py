from __future__ import annotations

import os
from typing import Optional

from fastapi import Request

from app.core.auth.models import Principal


class AuthError(Exception):
    pass


class StaticTokenProvider:
    def __init__(self):
        self.admin_token = os.getenv("COPILOT_STATIC_ADMIN_TOKEN")
        self.viewer_token = os.getenv("COPILOT_STATIC_VIEWER_TOKEN")
        self.legacy_token = os.getenv("COPILOT_STATIC_TOKEN")

        if not any([self.admin_token, self.viewer_token, self.legacy_token]):
            raise AuthError(
                "Missing static token config. "
                "Set COPILOT_STATIC_ADMIN_TOKEN "
                "or COPILOT_STATIC_VIEWER_TOKEN "
                "or COPILOT_STATIC_TOKEN."
            )

    def _extract_token(self, request: Request) -> str:
        # Defensive header extraction (case-safe + proxy-safe)
        auth_header = (
            request.headers.get("authorization")
            or request.headers.get("Authorization")
            or request.headers.get("x-forwarded-authorization")
        )

        if not auth_header:
            raise AuthError("Authentication required")

        if not auth_header.startswith("Bearer "):
            raise AuthError("Invalid authorization header")

        return auth_header.replace("Bearer ", "").strip()

    def authenticate(self, request: Request) -> Optional[Principal]:
        token = self._extract_token(request)

        if self.admin_token and token == self.admin_token:
            return Principal(subject="admin", roles=["admin"])

        if self.viewer_token and token == self.viewer_token:
            return Principal(subject="viewer", roles=["viewer"])

        if self.legacy_token and token == self.legacy_token:
            return Principal(subject="legacy", roles=["admin"])

        raise AuthError("Invalid bearer token")


def get_auth_provider():
    mode = (os.getenv("COPILOT_AUTH_MODE") or "none").strip().lower()

    if mode == "none":
        return None

    if mode == "static_token":
        return StaticTokenProvider()

    raise AuthError(f"Unsupported auth mode: {mode}")
