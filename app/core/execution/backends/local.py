from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .base import ExecutionBackend


class LocalBackend(ExecutionBackend):
    name = "local"

    def submit(self, job_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        # Fix 7: Do NOT accept or execute caller-supplied commands — prevents command injection.
        # Simulate immediate submission using current process PID as a stable backend_ref.
        pid = os.getpid()
        print(f"Running {job_name}")  # keeps stdout visible in tests for debugging
        return {"backend_ref": str(pid), "meta": {"pid": pid, "simulated": True}}

    def status(self, job_name: str, *, backend_ref: Optional[str] = None) -> Dict[str, Any]:
        # Phase 10.1: keep local backend deterministic (immediate success)
        return {"state": "SUCCEEDED"}

    def cancel(self, job_name: str, *, backend_ref: Optional[str] = None) -> None:
        # No-op for now (best-effort)
        return None