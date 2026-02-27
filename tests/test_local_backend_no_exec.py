"""Fix 7 test — LocalBackend.submit() must not execute caller-supplied commands."""
from __future__ import annotations

from app.core.execution.backends.local import LocalBackend


def test_local_backend_ignores_command_in_config():
    """submit() must not execute commands from the config dict."""
    backend = LocalBackend()
    # Even with a dangerous command in config, submit() must not execute it
    result = backend.submit("test_job", config={"command": ["rm", "-rf", "/"]})
    assert isinstance(result, dict)
    assert "backend_ref" in result
    # Must be a PID-based reference (numeric string), not a subprocess output
    assert result["backend_ref"].isdigit()
    assert result.get("meta", {}).get("simulated") is True


def test_local_backend_status_returns_succeeded():
    backend = LocalBackend()
    status = backend.status("test_job")
    assert status["state"] == "SUCCEEDED"


def test_local_backend_cancel_is_noop():
    backend = LocalBackend()
    result = backend.cancel("test_job", backend_ref="12345")
    assert result is None
