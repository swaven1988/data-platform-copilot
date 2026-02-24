from __future__ import annotations

import subprocess
from typing import Any, Dict, Optional

from .base import ExecutionBackend


class LocalBackend(ExecutionBackend):
    name = "local"

    def submit(self, job_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        cmd = config.get("command", ["echo", f"Running {job_name}"])
        proc = subprocess.Popen(cmd)
        return {"backend_ref": str(proc.pid), "meta": {"pid": proc.pid}}

    def status(self, job_name: str, *, backend_ref: Optional[str] = None) -> Dict[str, Any]:
        # Phase 10.1: keep local backend deterministic (immediate success)
        return {"state": "SUCCEEDED"}

    def cancel(self, job_name: str, *, backend_ref: Optional[str] = None) -> None:
        # No-op for now (best-effort)
        return None