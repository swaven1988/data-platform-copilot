from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import ExecutionEvent, ExecutionRecord, ExecutionState, _utc_now_iso
from .state_machine import ensure_transition


def _exec_dir(workspace_dir: Path) -> Path:
    d = workspace_dir / ".copilot" / "execution"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _exec_path(workspace_dir: Path, job_name: str) -> Path:
    return _exec_dir(workspace_dir) / f"{job_name}.json"


class ExecutionRegistry:
    """File-backed execution registry.

    Path: <workspace>/.copilot/execution/{job_name}.json
    """

    def __init__(self, *, workspace_dir: Path):
        self.workspace_dir = workspace_dir

    def get(self, job_name: str) -> Optional[ExecutionRecord]:
        p = _exec_path(self.workspace_dir, job_name)
        if not p.exists():
            return None
        obj = json.loads(p.read_text(encoding="utf-8"))
        return ExecutionRecord.from_dict(obj)

    def upsert(self, rec: ExecutionRecord) -> None:
        p = _exec_path(self.workspace_dir, rec.job_name)
        p.write_text(json.dumps(rec.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    def init_if_missing(
        self,
        *,
        job_name: str,
        build_id: str,
        tenant: str,
        runtime_profile: Optional[str],
        preflight_hash: Optional[str],
        cost_estimate: Optional[Dict],
        request_id: Optional[str],
        initial_state: ExecutionState = ExecutionState.PLAN_READY,
    ) -> ExecutionRecord:
        existing = self.get(job_name)
        if existing is not None:
            return existing

        now = _utc_now_iso()
        rec = ExecutionRecord(
            job_name=job_name,
            build_id=build_id,
            tenant=tenant,
            state=initial_state,
            created_ts=now,
            updated_ts=now,
            runtime_profile=runtime_profile,
            preflight_hash=preflight_hash,
            cost_estimate=cost_estimate,
            request_id=request_id,
            events=[
                ExecutionEvent(
                    ts=now,
                    state=initial_state,
                    message="initialized",
                    data={},
                )
            ],
        )
        self.upsert(rec)
        return rec

    def transition(
        self,
        *,
        job_name: str,
        dst: ExecutionState,
        message: str = "",
        data: Optional[Dict[str, Any]] = None,
    ) -> ExecutionRecord:
        rec = self.get(job_name)
        if rec is None:
            raise FileNotFoundError(f"execution not found for job_name={job_name}")

        ensure_transition(rec.state, dst)

        now = _utc_now_iso()
        rec.state = dst
        rec.updated_ts = now
        rec.events.append(
            ExecutionEvent(
                ts=now,
                state=dst,
                message=message,
                data=data or {},
            )
        )
        self.upsert(rec)
        return rec

    def update_fields(
        self,
        *,
        job_name: str,
        fields: Dict[str, Any],
        message: str = "",
        data: Optional[Dict[str, Any]] = None,
        emit_event: bool = False,
    ) -> ExecutionRecord:
        rec = self.get(job_name)
        if rec is None:
            raise FileNotFoundError(f"execution not found for job_name={job_name}")

        for k, v in (fields or {}).items():
            if not hasattr(rec, k):
                raise AttributeError(f"ExecutionRecord has no field: {k}")
            setattr(rec, k, v)

        now = _utc_now_iso()
        rec.updated_ts = now
        if emit_event:
            rec.events.append(
                ExecutionEvent(
                    ts=now,
                    state=rec.state,
                    message=message or "updated",
                    data=data or {},
                )
            )

        self.upsert(rec)
        return rec

    def history(self, job_name: str) -> List[Dict[str, Any]]:
        rec = self.get(job_name)
        if rec is None:
            return []
        return [e.__dict__ | {"state": e.state.value} for e in rec.events]