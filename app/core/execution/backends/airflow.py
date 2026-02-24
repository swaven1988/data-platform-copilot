from __future__ import annotations

from typing import Any, Dict, Optional

from .base import ExecutionBackend


class AirflowBackend(ExecutionBackend):
    name = "airflow"

    def submit(self, job_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        # placeholder — REST trigger later
        return {"backend_ref": job_name, "meta": {"dag_run": job_name}}

    def status(self, job_name: str, *, backend_ref: Optional[str] = None) -> Dict[str, Any]:
        return {"state": "RUNNING"}

    def cancel(self, job_name: str, *, backend_ref: Optional[str] = None) -> None:
        return None