from __future__ import annotations

from typing import Any, Dict, Optional

from .base import ExecutionBackend


class K8sBackend(ExecutionBackend):
    name = "k8s"

    def submit(self, job_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        # placeholder — real k8s client later
        return {"backend_ref": job_name, "meta": {"k8s_job": job_name}}

    def status(self, job_name: str, *, backend_ref: Optional[str] = None) -> Dict[str, Any]:
        return {"state": "RUNNING"}

    def cancel(self, job_name: str, *, backend_ref: Optional[str] = None) -> None:
        return None