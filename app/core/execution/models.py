from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ExecutionState(str, Enum):
    DRAFT = "DRAFT"
    PLAN_READY = "PLAN_READY"
    PRECHECK_PASSED = "PRECHECK_PASSED"
    APPLIED = "APPLIED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELED = "CANCELED"


@dataclass
class ExecutionEvent:
    ts: str
    state: ExecutionState
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionRecord:
    job_name: str
    build_id: str
    tenant: str
    state: ExecutionState
    created_ts: str
    updated_ts: str

    # provenance / attribution
    runtime_profile: Optional[str] = None
    preflight_hash: Optional[str] = None
    cost_estimate: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None

    # execution runtime
    backend: Optional[str] = None
    backend_ref: Optional[str] = None
    submitted_ts: Optional[str] = None
    finished_ts: Optional[str] = None

    # Phase 12.2: actuals (optional)
    actual_runtime_seconds: Optional[float] = None
    actual_cost_usd: Optional[float] = None

    backend_meta: Dict[str, Any] = field(default_factory=dict)

    last_error: Optional[str] = None
    events: List[ExecutionEvent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_name": self.job_name,
            "build_id": self.build_id,
            "tenant": self.tenant,
            "state": self.state.value,
            "created_ts": self.created_ts,
            "updated_ts": self.updated_ts,
            "runtime_profile": self.runtime_profile,
            "preflight_hash": self.preflight_hash,
            "cost_estimate": self.cost_estimate,
            "request_id": self.request_id,
            "backend": self.backend,
            "backend_ref": self.backend_ref,
            "submitted_ts": self.submitted_ts,
            "finished_ts": self.finished_ts,
            "actual_runtime_seconds": self.actual_runtime_seconds,
            "actual_cost_usd": self.actual_cost_usd,
            "backend_meta": self.backend_meta or {},
            "last_error": self.last_error,
            "events": [
                {
                    "ts": e.ts,
                    "state": e.state.value,
                    "message": e.message,
                    "data": e.data,
                }
                for e in self.events
            ],
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ExecutionRecord":
        evs: List[ExecutionEvent] = []
        for e in d.get("events", []) or []:
            evs.append(
                ExecutionEvent(
                    ts=e["ts"],
                    state=ExecutionState(e["state"]),
                    message=e.get("message", ""),
                    data=e.get("data", {}) or {},
                )
            )

        return ExecutionRecord(
            job_name=d["job_name"],
            build_id=d["build_id"],
            tenant=d.get("tenant", "default"),
            state=ExecutionState(d["state"]),
            created_ts=d.get("created_ts") or _utc_now_iso(),
            updated_ts=d.get("updated_ts") or _utc_now_iso(),
            runtime_profile=d.get("runtime_profile"),
            preflight_hash=d.get("preflight_hash"),
            cost_estimate=d.get("cost_estimate"),
            request_id=d.get("request_id"),
            backend=d.get("backend"),
            backend_ref=d.get("backend_ref"),
            submitted_ts=d.get("submitted_ts"),
            finished_ts=d.get("finished_ts"),
            actual_runtime_seconds=d.get("actual_runtime_seconds"),
            actual_cost_usd=d.get("actual_cost_usd"),
            backend_meta=d.get("backend_meta") or {},
            last_error=d.get("last_error"),
            events=evs,
        )