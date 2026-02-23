# app/core/execution/guards.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.core.policy.execution_policy import evaluate_execution_policy


def load_preflight_report(workspace_dir: Path, preflight_hash: Optional[str]) -> Optional[Dict[str, Any]]:
    if not preflight_hash:
        return None
    p = workspace_dir / ".copilot" / "preflight" / f"{preflight_hash}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_cost_estimate_from_preflight(preflight_report: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(preflight_report, dict):
        return None

    # Support both formats:
    # - {"estimate": {"estimated_total_cost_usd": ...}} (older)
    # - {"cost_estimate": {...}} (if you add later)
    if isinstance(preflight_report.get("cost_estimate", None), dict):
        return preflight_report["cost_estimate"]

    est = preflight_report.get("estimate", None)
    if isinstance(est, dict):
        keys = [
            "runtime_minutes",
            "compute_cost_usd",
            "infra_cost_usd",
            "estimated_total_cost_usd",
            "confidence",
            "assumptions",
        ]
        if any(k in est for k in keys):
            return est

    return None


def evaluate_apply_guardrails(
    *,
    tenant: str,
    workspace_dir: Path,
    preflight_hash: Optional[str],
    cost_estimate_override: Optional[Dict[str, Any]],
) -> Tuple[str, Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Returns:
      decision ("ALLOW"|"WARN"|"BLOCK"),
      details,
      preflight_report,
      cost_estimate_used
    """
    preflight_report = load_preflight_report(workspace_dir, preflight_hash)

    cost_estimate_used = None
    if isinstance(cost_estimate_override, dict):
        cost_estimate_used = cost_estimate_override
    else:
        cost_estimate_used = load_cost_estimate_from_preflight(preflight_report)

    decision, details = evaluate_execution_policy(
        tenant=tenant,
        cost_estimate=cost_estimate_used,
        preflight_report=preflight_report,
    )
    return decision, details, preflight_report, cost_estimate_used