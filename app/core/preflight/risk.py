# app/core/preflight/risk.py

from .models import PreflightRequest, RiskReport, CostEstimate


def assess(req: PreflightRequest, estimate: CostEstimate) -> RiskReport:
    reasons = []
    risk_score = 0.0

    gb = req.dataset.estimated_input_gb
    shuffle = req.dataset.shuffle_multiplier

    if gb > 200:
        risk_score += 0.3
        reasons.append("large_input_dataset")

    if shuffle > 3.0:
        risk_score += 0.2
        reasons.append("high_shuffle_multiplier")

    if req.sla and req.sla.max_runtime_minutes:
        if estimate.runtime_minutes > req.sla.max_runtime_minutes:
            risk_score += 0.4
            reasons.append("sla_runtime_breach_predicted")

    if estimate.compute_cost_usd > 500:
        risk_score += 0.2
        reasons.append("high_cost_estimate")

    risk_score = min(1.0, risk_score)

    return RiskReport(
        risk_score=round(risk_score, 2),
        risk_reasons=reasons,
    )


def policy_decision(risk: RiskReport, estimate: CostEstimate, req: PreflightRequest) -> str:
    if risk.risk_score > 0.85:
        return "BLOCK"

    if estimate.compute_cost_usd > 300:
        return "WARN"

    if req.sla and req.sla.max_runtime_minutes:
        if estimate.runtime_minutes > req.sla.max_runtime_minutes:
            return "WARN"

    return "ALLOW"