# app/core/policy/execution_policy.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class ExecutionPolicyConfig:
    # Cost guardrails
    max_total_cost_usd: float = 50.0

    # Runtime guardrails
    max_runtime_minutes: float = 180.0

    # Resource guardrails
    max_executors: int = 200


def _tenant_defaults(tenant: str) -> ExecutionPolicyConfig:
    # Phase 9: simple per-tenant defaults.
    # You can later load from config/DB/secret manager.
    if tenant == "default":
        return ExecutionPolicyConfig(
            max_total_cost_usd=50.0,
            max_runtime_minutes=180.0,
            max_executors=200,
        )
    # fallback
    return ExecutionPolicyConfig()


def evaluate_execution_policy(
    *,
    tenant: str,
    cost_estimate: Optional[Dict[str, Any]],
    preflight_report: Optional[Dict[str, Any]],
) -> Tuple[str, Dict[str, Any]]:
    """
    Returns:
      ("ALLOW"|"WARN"|"BLOCK", details)
    """
    cfg = _tenant_defaults(tenant)

    reasons = []
    warnings = []

    # ---- cost checks ----
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

    # ---- resource checks (best-effort) ----
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

    if reasons:
        return "BLOCK", {"tenant": tenant, "limits": cfg.__dict__, "reasons": reasons, "warnings": warnings}

    if warnings:
        return "WARN", {"tenant": tenant, "limits": cfg.__dict__, "reasons": [], "warnings": warnings}

    return "ALLOW", {"tenant": tenant, "limits": cfg.__dict__, "reasons": [], "warnings": []}