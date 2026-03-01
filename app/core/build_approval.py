"""Build approval workflow storage and evaluation helpers."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


_DEFAULT_APPROVAL_TTL_SECONDS = 3600  # 1 hour


def _approval_ttl_seconds() -> float:
    try:
        return float(os.getenv("COPILOT_APPROVAL_TTL_SECONDS", str(_DEFAULT_APPROVAL_TTL_SECONDS)))
    except (TypeError, ValueError):
        return float(_DEFAULT_APPROVAL_TTL_SECONDS)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _approval_root(workspace_root: Path) -> Path:
    p = workspace_root / ".copilot" / "approvals"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _approval_file(workspace_root: Path, job_name: str, plan_hash: str) -> Path:
    safe_job = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "_" for ch in (job_name or "job"))
    safe_hash = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "_" for ch in (plan_hash or "plan"))
    return _approval_root(workspace_root) / f"{safe_job}__{safe_hash}.json"


@dataclass(frozen=True)
class ApprovalDecision:
    required: bool
    reason: str
    risk_score: Optional[float]


class BuildApprovalStore:
    def __init__(self, *, workspace_root: Path):
        self.workspace_root = workspace_root

    def save_approval(
        self,
        *,
        job_name: str,
        plan_hash: str,
        approver: str,
        notes: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        obj = {
            "job_name": job_name,
            "plan_hash": plan_hash,
            "approver": approver,
            "notes": notes or "",
            "metadata": metadata or {},
            "approved": True,
            "approved_at": _utc_now_iso(),
        }
        p = _approval_file(self.workspace_root, job_name, plan_hash)
        p.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
        return obj

    def get_approval(
        self, *, job_name: str, plan_hash: str
    ) -> Optional[Dict[str, Any]]:
        """Return approval if it exists and has not expired. Returns None if missing or stale."""
        p = _approval_file(self.workspace_root, job_name, plan_hash)
        if not p.exists():
            return None
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

        # TTL check — approved_at is ISO-8601 UTC string
        approved_at_str = obj.get("approved_at", "")
        if approved_at_str:
            try:
                approved_at_dt = datetime.fromisoformat(
                    approved_at_str.replace("Z", "+00:00")
                )
                age_seconds = (
                    datetime.now(timezone.utc) - approved_at_dt
                ).total_seconds()
                if age_seconds > _approval_ttl_seconds():
                    return None  # expired — treat as if no approval exists
            except Exception:
                pass  # unparseable timestamp — fail open, return the record

        return obj

    def revoke_approval(self, *, job_name: str, plan_hash: str) -> bool:
        """Delete an approval file. Returns True if it existed, False if already gone."""
        p = _approval_file(self.workspace_root, job_name, plan_hash)
        if p.exists():
            p.unlink()
            return True
        return False

    def list_approvals(self, *, job_name: str) -> list:
        """Return all approval records for a job across all plan hashes."""
        root = _approval_root(self.workspace_root)
        safe_job = "".join(
            ch if (ch.isalnum() or ch in {"-", "_"}) else "_"
            for ch in (job_name or "job")
        )
        results = []
        for p in sorted(root.glob(f"{safe_job}__*.json")):
            try:
                results.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                continue
        return results


def evaluate_high_risk_requirement(
    *,
    risk_score: Optional[float],
    threshold: float = 0.70,
) -> ApprovalDecision:
    score = float(risk_score) if isinstance(risk_score, (int, float)) else None
    if score is None:
        return ApprovalDecision(required=False, reason="risk_score_missing", risk_score=None)
    if score >= float(threshold):
        return ApprovalDecision(required=True, reason="high_risk_requires_approval", risk_score=score)
    return ApprovalDecision(required=False, reason="risk_below_threshold", risk_score=score)

