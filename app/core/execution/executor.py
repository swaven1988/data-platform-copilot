from __future__ import annotations

from typing import Any, Dict, Optional
from datetime import datetime, timezone

from .models import ExecutionState, _utc_now_iso
from .registry import ExecutionRegistry
from .state_machine import is_terminal

# Phase 10: pluggable execution backends
from .backends import BACKENDS

from app.core.billing.ledger import LedgerStore, utc_month_key

def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    t = ts.strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(t)
    except Exception:
        return None


def _maybe_write_actuals(*, registry: ExecutionRegistry, job_name: str) -> None:
    rec = registry.get(job_name)
    if rec is None:
        return
    if not rec.finished_ts:
        return

    # runtime
    started = _parse_iso(rec.submitted_ts)
    finished = _parse_iso(rec.finished_ts)
    runtime_s = None
    if started and finished:
        runtime_s = max(0.0, (finished - started).total_seconds())

    # cost: default to estimate (until real backend metering exists)
    est = None
    if isinstance(rec.cost_estimate, dict):
        v = rec.cost_estimate.get("estimated_total_cost_usd")
        if isinstance(v, (int, float)):
            est = float(v)

    month = utc_month_key()
    ledger = LedgerStore(workspace_dir=registry.workspace_dir)
    ledger.upsert_actual(
        tenant=rec.tenant,
        month=month,
        job_name=rec.job_name,
        build_id=rec.build_id,
        actual_cost_usd=est,
        actual_runtime_seconds=runtime_s,
        finished_ts=rec.finished_ts,
    )

    # persist in execution record as well (non-breaking)
    fields = {}
    if runtime_s is not None:
        fields["actual_runtime_seconds"] = runtime_s
    if est is not None:
        fields["actual_cost_usd"] = est
    if fields:
        try:
            registry.update_fields(job_name=job_name, fields=fields)
        except Exception:
            pass


class Executor:
    """Execution orchestrator.

    Phase 9: apply-time enforcement.
    Phase 10: pluggable backends.

    Phase 10.1: RUNNING is real.
    - run(): transitions APPLIED -> RUNNING, stores backend metadata, returns immediately
    - refresh_status(): polls backend and transitions RUNNING -> (SUCCEEDED|FAILED) when terminal
    - cancel(): best-effort cancel and transitions RUNNING -> FAILED
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

    def run(
        self,
        job_name: str,
        *,
        config: Optional[Dict[str, Any]] = None,
        backend_name: str = "local",
    ) -> Dict[str, Any]:
        rec = self.registry.get(job_name)
        if rec is None:
            raise FileNotFoundError(f"execution not found for job_name={job_name}")

        if is_terminal(rec.state):
            return rec.to_dict()

        if rec.state != ExecutionState.APPLIED:
            raise ValueError(f"run requires state=APPLIED; current={rec.state.value}")

        backend = BACKENDS.get(backend_name)
        if not backend:
            raise ValueError(f"Unsupported backend: {backend_name}")

        submit_out = backend.submit(job_name=job_name, config=config or {})
        backend_ref = submit_out.get("backend_ref")
        backend_meta = submit_out.get("meta") or {}

        now = _utc_now_iso()
        self.registry.update_fields(
            job_name=job_name,
            fields={
                "backend": backend_name,
                "backend_ref": backend_ref,
                "backend_meta": backend_meta,
                "submitted_ts": now,
                "finished_ts": None,
                "last_error": None,
            },
        )

        rec = self.registry.transition(
            job_name=job_name,
            dst=ExecutionState.RUNNING,
            message=f"running (backend={backend_name})",
            data={"backend": backend_name, "backend_ref": backend_ref},
        )
        return rec.to_dict()

    def refresh_status(self, job_name: str) -> Dict[str, Any]:
        rec = self.registry.get(job_name)
        if rec is None:
            raise FileNotFoundError(f"execution not found for job_name={job_name}")

        if rec.state != ExecutionState.RUNNING:
            return rec.to_dict()

        backend_name = rec.backend or "local"
        backend = BACKENDS.get(backend_name)
        if not backend:
            # Should never happen; mark failed.
            rec = self.registry.update_fields(
                job_name=job_name,
                fields={"last_error": f"Unsupported backend on record: {backend_name}"},
            )
            rec = self.registry.transition(job_name=job_name, dst=ExecutionState.FAILED, message="failed (unsupported backend)")
            return rec.to_dict()

        st = backend.status(job_name=job_name, backend_ref=rec.backend_ref)
        state = (st.get("state") or "").upper().strip()

        if state == ExecutionState.RUNNING.value:
            # still running: optionally persist last seen backend status
            if st:
                self.registry.update_fields(
                    job_name=job_name,
                    fields={"backend_meta": {**(rec.backend_meta or {}), "last_status": st}},
                )
            return self.registry.get(job_name).to_dict()  # type: ignore[union-attr]

        if state in {ExecutionState.SUCCEEDED.value, ExecutionState.FAILED.value}:
            now = _utc_now_iso()
            self.registry.update_fields(
                job_name=job_name,
                fields={"finished_ts": now, "backend_meta": {**(rec.backend_meta or {}), "final_status": st}},
            )
            rec = self.registry.transition(
                job_name=job_name,
                dst=ExecutionState(state),
                message=f"{state.lower()} (backend)",
                data={"backend": backend_name, "backend_ref": rec.backend_ref, "status": st},
            )
            _maybe_write_actuals(registry=self.registry, job_name=job_name)
            return rec.to_dict()

        # Unknown => treat as RUNNING but store diagnostics
        self.registry.update_fields(
            job_name=job_name,
            fields={"backend_meta": {**(rec.backend_meta or {}), "last_status": st}},
        )
        return self.registry.get(job_name).to_dict()  # type: ignore[union-attr]

    def cancel(self, job_name: str) -> Dict[str, Any]:
        rec = self.registry.get(job_name)
        if rec is None:
            raise FileNotFoundError(f"execution not found for job_name={job_name}")

        if rec.state != ExecutionState.RUNNING:
            return rec.to_dict()

        backend_name = rec.backend or "local"
        backend = BACKENDS.get(backend_name)
        if not backend:
            rec = self.registry.transition(job_name=job_name, dst=ExecutionState.FAILED, message="failed (unsupported backend)")
            return rec.to_dict()

        try:
            backend.cancel(job_name=job_name, backend_ref=rec.backend_ref)
        except Exception as e:
            # best-effort cancel: still mark failed but keep error
            self.registry.update_fields(job_name=job_name, fields={"last_error": str(e)})

        now = _utc_now_iso()
        self.registry.update_fields(job_name=job_name, fields={"finished_ts": now})
        rec = self.registry.transition(
            job_name=job_name,
            dst=ExecutionState.FAILED,
            message="cancelled",
            data={"backend": backend_name, "backend_ref": rec.backend_ref},
        )
        return rec.to_dict()