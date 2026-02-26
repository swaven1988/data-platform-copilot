from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Literal


EventType = Literal[
    "BuildRequested",
    "SpecValidated",
    "PlanCreated",
    "StepStarted",
    "StepCompleted",
    "StepFailed",
    "ArtifactsWritten",
    "BuildCompleted",
    "BuildSkipped",
]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class BuildEvent:
    event_type: EventType
    ts: str
    job_name: str
    spec_hash: str
    plan_id: Optional[str] = None
    step_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def mk(
        event_type: EventType,
        job_name: str,
        spec_hash: str,
        plan_id: Optional[str] = None,
        step_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> "BuildEvent":
        return BuildEvent(
            event_type=event_type,
            ts=now_utc_iso(),
            job_name=job_name,
            spec_hash=spec_hash,
            plan_id=plan_id,
            step_id=step_id,
            payload=payload or {},
        )
