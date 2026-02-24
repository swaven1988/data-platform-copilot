from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.core.billing.ledger import LedgerStore, utc_month_key
from app.core.billing.tenant_budget import get_tenant_monthly_budget
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
    build_id: str,
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

    if isinstance(cost_estimate_override, dict):
        cost_estimate_used = cost_estimate_override
    else:
        cost_estimate_used = load_cost_estimate_from_preflight(preflight_report)

    # Phase 11: compute billing context
    month = utc_month_key()
    budget = get_tenant_monthly_budget(workspace_dir=workspace_dir, tenant=tenant, month=month)
    ledger = LedgerStore(workspace_dir=workspace_dir)
    spent = ledger.spent_usd(tenant=tenant, month=month)

    new_est = None
    if isinstance(cost_estimate_used, dict):
        v = cost_estimate_used.get("estimated_total_cost_usd")
        if isinstance(v, (int, float)):
            new_est = float(v)

    decision, details = evaluate_execution_policy(
        tenant=tenant,
        cost_estimate=cost_estimate_used,
        preflight_report=preflight_report,
        billing={
            "month": month,
            "limit_usd": budget.limit_usd,
            "spent_usd": spent,
            "new_estimate_usd": new_est,
        },
    )

    # Record ledger entry ONLY if allowed to proceed (ALLOW/WARN) and estimate exists.
    # Idempotent key handled by LedgerStore.upsert_estimate().
    if decision in ("ALLOW", "WARN") and isinstance(new_est, (int, float)):
        job_name = workspace_dir.name
        ledger.upsert_estimate(
            tenant=tenant,
            month=month,
            job_name=job_name,
            build_id=build_id,
            estimated_cost_usd=float(new_est),
        )

    return decision, details, preflight_report, cost_estimate_used