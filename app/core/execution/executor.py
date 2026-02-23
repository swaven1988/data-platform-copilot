# app/core/execution/executor.py
from __future__ import annotations

from typing import Any, Dict, Optional

from .models import ExecutionState
from .registry import ExecutionRegistry


class Executor:
    """
    Phase 8A: Stub executor.
    - apply(): moves PRECHECK_PASSED -> APPLIED (idempotent)
    - run(): moves APPLIED -> RUNNING -> SUCCEEDED (immediate, deterministic)
    """

    def __init__(self, registry: ExecutionRegistry):
        self.registry = registry

    def apply(self, job_name: str) -> Dict[str, Any]:
        rec = self.registry.get(job_name)
        if rec is None:
            raise FileNotFoundError(f"execution not found for job_name={job_name}")

        if rec.state == ExecutionState.APPLIED:
            return rec.to_dict()

        rec = self.registry.transition(job_name=job_name, dst=ExecutionState.APPLIED, message="applied")
        return rec.to_dict()

    def run(self, job_name: str) -> Dict[str, Any]:
        rec = self.registry.get(job_name)
        if rec is None:
            raise FileNotFoundError(f"execution not found for job_name={job_name}")

        if rec.state == ExecutionState.SUCCEEDED:
            return rec.to_dict()

        if rec.state != ExecutionState.APPLIED:
            raise ValueError(f"run requires state=APPLIED; current={rec.state.value}")

        rec = self.registry.transition(job_name=job_name, dst=ExecutionState.RUNNING, message="running")
        # Phase 8A: deterministic completion
        rec = self.registry.transition(job_name=job_name, dst=ExecutionState.SUCCEEDED, message="succeeded")
        return rec.to_dict()