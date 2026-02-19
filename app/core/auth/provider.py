from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any

import jwt
from fastapi import Request

from app.core.auth.models import Principal


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class JwtConfig:
    signing_key: str
    issuer: Optional[str] = None
    audience: Optional[str] = None
    leeway_seconds: int = 30


class StaticTokenProvider:
    def __init__(self):
        self.admin_token = os.getenv("COPILOT_STATIC_ADMIN_TOKEN")
        self.viewer_token = os.getenv("COPILOT_STATIC_VIEWER_TOKEN")
        self.legacy_token = os.getenv("COPILOT_STATIC_TOKEN")

        if not any([self.admin_token, self.viewer_token, self.legacy_token]):
            raise AuthError(
                "Missing static token config. "
                "Set COPILOT_STATIC_ADMIN_TOKEN or COPILOT_STATIC_VIEWER_TOKEN or COPILOT_STATIC_TOKEN."
            )

    def _extract_bearer(self, request: Request) -> str:
        auth_header = (
            request.headers.get("authorization")
            or request.headers.get("Authorization")
            or request.headers.get("x-forwarded-authorization")
            or request.headers.get("X-Forwarded-Authorization")
        )
        if not auth_header:
            raise AuthError("Authentication required")
        if not auth_header.startswith("Bearer "):
            raise AuthError("Invalid authorization header")
        return auth_header.replace("Bearer ", "").strip()

    def authenticate(self, request: Request) -> Optional[Principal]:
        token = self._extract_bearer(request)

        if self.admin_token and token == self.admin_token:
            return Principal(subject="admin", roles=["admin"])
        if self.viewer_token and token == self.viewer_token:
            return Principal(subject="viewer", roles=["viewer"])
        if self.legacy_token and token == self.legacy_token:
            return Principal(subject="legacy", roles=["admin"])

        raise AuthError("Invalid bearer token")


class ApiKeyProvider:
    """
    Stage 17: Service accounts / API keys.

    Keys are loaded from env COPILOT_API_KEYS_JSON in this format:
      {
        "key_abc": {"sub":"svc-foo", "roles":["admin"], "tenant":"default"},
        "key_xyz": {"sub":"svc-bar", "roles":["viewer"]}
      }

    Client supplies:
      X-API-Key: <key>
    """

    def __init__(self):
        raw = os.getenv("COPILOT_API_KEYS_JSON", "").strip()
        if not raw:
            raise AuthError("Missing COPILOT_API_KEYS_JSON for api_key mode")

        try:
            self.keys: Dict[str, Dict[str, Any]] = json.loads(raw)
        except Exception as e:
            raise AuthError(f"Invalid COPILOT_API_KEYS_JSON: {e}") from e

        if not isinstance(self.keys, dict) or not self.keys:
            raise AuthError("COPILOT_API_KEYS_JSON must be a non-empty object")

    def authenticate(self, request: Request) -> Optional[Principal]:
        k = request.headers.get("x-api-key") or request.headers.get("X-API-Key")
        if not k:
            raise AuthError("Authentication required")

        meta = self.keys.get(k)
        if not meta:
            raise AuthError("Invalid api key")

        sub = meta.get("sub") or "service"
        roles = meta.get("roles") or ["viewer"]
        return Principal(subject=sub, roles=roles)


class JwtProvider:
    """
    Stage 16: JWT auth.

    Bearer token is decoded with COPILOT_SIGNING_KEY.
    Optional:
      COPILOT_JWT_ISSUER
      COPILOT_JWT_AUDIENCE
      COPILOT_JWT_LEEWAY_SECONDS
    """

    def __init__(self):
        key = (os.getenv("COPILOT_SIGNING_KEY") or "").strip()
        if not key:
            raise AuthError("Missing COPILOT_SIGNING_KEY for jwt mode")

        issuer = (os.getenv("COPILOT_JWT_ISSUER") or "").strip() or None
        audience = (os.getenv("COPILOT_JWT_AUDIENCE") or "").strip() or None
        leeway = int((os.getenv("COPILOT_JWT_LEEWAY_SECONDS") or "30").strip() or "30")
        self.cfg = JwtConfig(signing_key=key, issuer=issuer, audience=audience, leeway_seconds=leeway)

    def _extract_bearer(self, request: Request) -> str:
        auth_header = (
            request.headers.get("authorization")
            or request.headers.get("Authorization")
            or request.headers.get("x-forwarded-authorization")
            or request.headers.get("X-Forwarded-Authorization")
        )
        if not auth_header:
            raise AuthError("Authentication required")
        if not auth_header.startswith("Bearer "):
            raise AuthError("Invalid authorization header")
        return auth_header.replace("Bearer ", "").strip()

    def authenticate(self, request: Request) -> Optional[Principal]:
        token = self._extract_bearer(request)

        options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_iat": False,
            "verify_nbf": True,
            "verify_iss": self.cfg.issuer is not None,
            "verify_aud": self.cfg.audience is not None,
        }

        try:
            claims = jwt.decode(
                token,
                self.cfg.signing_key,
                algorithms=["HS256"],
                issuer=self.cfg.issuer,
                audience=self.cfg.audience,
                options=options,
                leeway=self.cfg.leeway_seconds,
            )
        except Exception:
            raise AuthError("Invalid bearer token")

        sub = claims.get("sub") or "user"
        roles = claims.get("roles") or claims.get("role") or ["viewer"]
        if isinstance(roles, str):
            roles = [roles]
        return Principal(subject=sub, roles=list(roles))


def get_auth_provider():
    mode = (os.getenv("COPILOT_AUTH_MODE") or "none").strip().lower()
    env = (os.getenv("COPILOT_ENV") or "dev").strip().lower()

    if mode == "none":
        return None

    if mode == "static_token":
        # Stage 21: prod should not allow static tokens unless explicitly allowed
        if env == "prod" and (os.getenv("COPILOT_ALLOW_STATIC_TOKEN_IN_PROD") or "").strip().lower() not in ("1", "true", "yes"):
            raise AuthError("static_token not allowed in prod (set COPILOT_ALLOW_STATIC_TOKEN_IN_PROD=true to override)")
        return StaticTokenProvider()

    if mode == "jwt":
        return JwtProvider()

    if mode == "api_key":
        return ApiKeyProvider()

    raise AuthError(f"Unsupported auth mode: {mode}")
