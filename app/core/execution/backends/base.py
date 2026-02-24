from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ExecutionBackend(ABC):
    name: str

    @abstractmethod
    def submit(self, job_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a job.

        Returns backend metadata, typically including a stable reference to poll/cancel.
        Example: {"backend_ref": "<container_id>", "meta": {...}}
        """

    @abstractmethod
    def status(self, job_name: str, *, backend_ref: Optional[str] = None) -> Dict[str, Any]:
        """Return a dict: {"state": "RUNNING|SUCCEEDED|FAILED", ...}"""

    @abstractmethod
    def cancel(self, job_name: str, *, backend_ref: Optional[str] = None) -> None:
        """Best-effort cancel/terminate."""