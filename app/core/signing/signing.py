# PATCH 2 — app/core/signing/signing.py
# Fix: canonical_json_bytes must accept dataclasses (ReproManifest) and dicts.

# REPLACE entire file with this:

from __future__ import annotations

import base64
import dataclasses
import hashlib
import hmac
import json
import os
from typing import Any, Dict


class SigningError(RuntimeError):
    pass


def _get_key() -> bytes:
    key = os.getenv("COPILOT_SIGNING_KEY", "").strip()
    if not key:
        raise SigningError("COPILOT_SIGNING_KEY is not set")
    return key.encode("utf-8")


def ensure_signing_key_present() -> None:
    _get_key()


def sign_bytes(payload: bytes) -> str:
    key = _get_key()
    sig = hmac.new(key, payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")


def verify_bytes(payload: bytes, signature: str) -> bool:
    key = _get_key()
    padded = signature + "=" * (-len(signature) % 4)
    try:
        sig = base64.urlsafe_b64decode(padded.encode("utf-8"))
    except Exception:
        return False
    expected = hmac.new(key, payload, hashlib.sha256).digest()
    return hmac.compare_digest(sig, expected)


def _to_jsonable(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x) for x in obj]
    if dataclasses.is_dataclass(obj):
        return _to_jsonable(dataclasses.asdict(obj))
    # pydantic v2
    if hasattr(obj, "model_dump"):
        return _to_jsonable(obj.model_dump())
    # pydantic v1
    if hasattr(obj, "dict"):
        return _to_jsonable(obj.dict())
    return str(obj)


def canonical_json_bytes(obj: Any) -> bytes:
    jsonable = _to_jsonable(obj)
    return json.dumps(jsonable, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
