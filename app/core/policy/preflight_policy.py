# --------------------------------
# Phase 7.2 — Cost Threshold Policy Config
# --------------------------------

# app/core/policy/preflight_policy.py

DEFAULT_COST_WARN_THRESHOLD = 300.0
DEFAULT_RISK_BLOCK_THRESHOLD = 0.85


def evaluate_policy(risk_score: float, cost: float) -> str:
    if risk_score > DEFAULT_RISK_BLOCK_THRESHOLD:
        return "BLOCK"
    if cost > DEFAULT_COST_WARN_THRESHOLD:
        return "WARN"
    return "ALLOW"