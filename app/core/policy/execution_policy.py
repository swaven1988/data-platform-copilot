from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class ExecutionPolicyConfig:
    # Cost guardrails (single-run)
    max_total_cost_usd: float = 50.0

    # Runtime guardrails
    max_runtime_minutes: float = 180.0

    # Resource guardrails
    max_executors: int = 200


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


def _tenant_defaults(tenant: str) -> ExecutionPolicyConfig:
    # Fix 17: policy limits are env-configurable
    max_cost = _env_float("COPILOT_MAX_COST_USD", 50.0)
    max_runtime = _env_float("COPILOT_MAX_RUNTIME_MINUTES", 180.0)
    max_executors = _env_int("COPILOT_MAX_EXECUTORS", 200)

    return ExecutionPolicyConfig(
        max_total_cost_usd=max_cost,
        max_runtime_minutes=max_runtime,
        max_executors=max_executors,
    )



def evaluate_execution_policy(
    *,
    tenant: str,
    cost_estimate: Optional[Dict[str, Any]],
    preflight_report: Optional[Dict[str, Any]],
    billing: Optional[Dict[str, Any]] = None,  # Phase 11
) -> Tuple[str, Dict[str, Any]]:
    """
    Returns:
      ("ALLOW"|"WARN"|"BLOCK", details)

    billing (optional):
      {
        "month": "YYYY-MM",
        "limit_usd": float,
        "spent_usd": float,
        "new_estimate_usd": float|None
      }
    """
    cfg = _tenant_defaults(tenant)

    reasons = []
    warnings = []

    # ---- cost checks (single-run) ----
    total_cost = None
    if isinstance(cost_estimate, dict):
        total_cost = cost_estimate.get("estimated_total_cost_usd", None)
        if isinstance(total_cost, (int, float)) and total_cost > cfg.max_total_cost_usd:
            reasons.append(
                {
                    "kind": "cost",
                    "code": "exec.cost.too_high",
                    "message": f"Estimated total cost ${total_cost:.2f} exceeds tenant max ${cfg.max_total_cost_usd:.2f}.",
                }
            )

    # ---- runtime checks ----
    runtime_minutes = None
    src = preflight_report if isinstance(preflight_report, dict) else None
    if isinstance(src, dict):
        runtime_minutes = src.get("runtime_minutes", None) or src.get("estimate", {}).get("runtime_minutes", None)
        if isinstance(runtime_minutes, (int, float)) and runtime_minutes > cfg.max_runtime_minutes:
            reasons.append(
                {
                    "kind": "runtime",
                    "code": "exec.runtime.too_high",
                    "message": f"Estimated runtime {runtime_minutes:.1f}m exceeds tenant max {cfg.max_runtime_minutes:.1f}m.",
                }
            )

    # ---- resource checks ----
    executors = None
    if isinstance(src, dict):
        executors = src.get("pricing", {}).get("executors", None) if isinstance(src.get("pricing", None), dict) else None
        if isinstance(executors, int) and executors > cfg.max_executors:
            reasons.append(
                {
                    "kind": "resources",
                    "code": "exec.executors.too_high",
                    "message": f"Executors {executors} exceeds tenant max {cfg.max_executors}.",
                }
            )

    # ---- Phase 11: monthly budget ledger check ----
    billing_details = {}
    if isinstance(billing, dict):
        month = billing.get("month")
        limit_usd = billing.get("limit_usd")
        spent_usd = billing.get("spent_usd")
        new_est = billing.get("new_estimate_usd")

        billing_details = {
            "month": month,
            "limit_usd": limit_usd,
            "spent_usd": spent_usd,
            "new_estimate_usd": new_est,
        }

        if isinstance(limit_usd, (int, float)) and isinstance(spent_usd, (int, float)) and isinstance(new_est, (int, float)):
            projected = float(spent_usd) + float(new_est)
            if projected > float(limit_usd):
                reasons.append(
                    {
                        "kind": "budget",
                        "code": "exec.budget.exceeded",
                        "message": f"Monthly budget exceeded for {month}: spent=${float(spent_usd):.2f} + new=${float(new_est):.2f} > limit=${float(limit_usd):.2f}.",
                    }
                )

    # ---- high risk warning (does not block) ----
    risk_score = None
    if isinstance(src, dict):
        risk_score = src.get("risk_score", None)
        if isinstance(risk_score, (int, float)) and risk_score >= 0.70:
            warnings.append(
                {
                    "kind": "risk",
                    "code": "exec.risk.high",
                    "message": f"High risk score {risk_score:.2f} (execution allowed, but risky).",
                }
            )

    details = {"tenant": tenant, "limits": cfg.__dict__, "reasons": reasons, "warnings": warnings}
    if billing_details:
        details["billing"] = billing_details

    if reasons:
        return "BLOCK", details

    if warnings:
        return "WARN", details

    return "ALLOW", details