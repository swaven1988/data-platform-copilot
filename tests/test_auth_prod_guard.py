"""Fix 3 test — prod guard and dev warning log in auth provider."""
from __future__ import annotations

import pytest


def test_prod_env_without_tokens_raises_auth_error(monkeypatch):
    """With COPILOT_ENV=prod and no token env vars configured, get_auth_provider() must raise AuthError."""
    monkeypatch.setenv("COPILOT_ENV", "prod")
    monkeypatch.delenv("COPILOT_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("COPILOT_VIEWER_TOKEN", raising=False)
    # Use a path that definitely doesn't exist to exercise the FileNotFoundError fallback
    monkeypatch.setenv("COPILOT_ADMIN_TOKEN_FILE", "/nonexistent/path/admin_token")
    monkeypatch.setenv("COPILOT_VIEWER_TOKEN_FILE", "/nonexistent/path/viewer_token")
    # Allow static tokens in prod so we reach the fallback path
    monkeypatch.setenv("COPILOT_ALLOW_STATIC_TOKEN_IN_PROD", "true")

    from importlib import reload
    import app.core.auth.provider as _mod
    reload(_mod)
    from app.core.auth.provider import AuthError, get_auth_provider
    with pytest.raises(AuthError):
        get_auth_provider()



def test_dev_env_falls_back_to_dev_tokens(monkeypatch, caplog):
    """With COPILOT_ENV=dev and no tokens/files configured, falls back to dev tokens with a warning."""
    monkeypatch.setenv("COPILOT_ENV", "dev")
    monkeypatch.delenv("COPILOT_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("COPILOT_VIEWER_TOKEN", raising=False)
    monkeypatch.setenv("COPILOT_ADMIN_TOKEN_FILE", "/nonexistent/path/admin_token")
    monkeypatch.setenv("COPILOT_VIEWER_TOKEN_FILE", "/nonexistent/path/viewer_token")

    import logging
    from importlib import reload
    import app.core.auth.provider as _mod
    reload(_mod)
    from app.core.auth.provider import get_auth_provider, StaticTokenAuthProvider
    import app.core.auth.provider as provider_module

    with caplog.at_level(logging.WARNING, logger="copilot.auth"):
        provider = get_auth_provider()

    assert isinstance(provider, StaticTokenAuthProvider)
    assert provider.cfg.admin_token == "dev_admin_token"
    # Warning log should have been emitted
    assert any("insecure" in r.message.lower() or "dev tokens" in r.message.lower() for r in caplog.records)
