"""Fix 1 test — verify hmac.HMAC-based sign/verify are inverse operations."""
from __future__ import annotations

import os
import pytest


@pytest.fixture(autouse=True)
def _set_signing_key(monkeypatch):
    monkeypatch.setenv("COPILOT_SIGNING_KEY", "test-secret-key-for-signing")


def test_sign_verify_roundtrip():
    from app.core.signing.signing import sign_bytes, verify_bytes

    payload = b"hello world"
    sig = sign_bytes(payload)
    assert isinstance(sig, str)
    assert len(sig) > 0
    assert verify_bytes(payload, sig) is True


def test_verify_wrong_payload_fails():
    from app.core.signing.signing import sign_bytes, verify_bytes

    sig = sign_bytes(b"correct payload")
    assert verify_bytes(b"wrong payload", sig) is False


def test_verify_corrupted_sig_fails():
    from app.core.signing.signing import sign_bytes, verify_bytes

    sig = sign_bytes(b"payload")
    corrupted = sig[:-4] + "XXXX"
    assert verify_bytes(b"payload", corrupted) is False


def test_verify_invalid_base64_fails():
    from app.core.signing.signing import verify_bytes

    assert verify_bytes(b"payload", "!!!not-base64!!!") is False
