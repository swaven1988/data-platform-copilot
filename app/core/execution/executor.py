# app/core/execution/executor.py
from __future__ import annotations

from typing import Any, Dict, Optional

from .models import ExecutionState
from .registry import ExecutionRegistry

# Phase 10: pluggable execution backends
from .backends import BACKENDS


class Executor:
    """
    Phase 8A: Stub executor.
    - apply(): moves PRECHECK_PASSED -> APPLIED (idempotent)
    - run(): moves APPLIED -> RUNNING -> SUCCEEDED (immediate, deterministic)

    Phase 10: Adds backend submit hook while preserving deterministic completion for now.
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

    def run(self, job_name: str, *, config: Optional[Dict[str, Any]] = None, backend_name: str = "local") -> Dict[str, Any]:
        rec = self.registry.get(job_name)
        if rec is None:
            raise FileNotFoundError(f"execution not found for job_name={job_name}")

        if rec.state == ExecutionState.SUCCEEDED:
            return rec.to_dict()

        if rec.state != ExecutionState.APPLIED:
            raise ValueError(f"run requires state=APPLIED; current={rec.state.value}")

        backend = BACKENDS.get(backend_name)
        if not backend:
            raise ValueError(f"Unsupported backend: {backend_name}")

        rec = self.registry.transition(job_name=job_name, dst=ExecutionState.RUNNING, message=f"running (backend={backend_name})")

        # Phase 10: submit to backend (no-op / placeholder backends are OK)
        backend.submit(job_name=job_name, config=config or {})

        # Keep Phase 8A deterministic completion for now
        rec = self.registry.transition(job_name=job_name, dst=ExecutionState.SUCCEEDED, message="succeeded")
        return rec.to_dict()