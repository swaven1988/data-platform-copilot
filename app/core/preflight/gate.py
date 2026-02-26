# ================================
# Phase 7.1 — Build Gate Integration (Preflight Mandatory)
# ================================

# --------------------------------
# app/core/preflight/gate.py
# --------------------------------

from app.core.preflight.models import PreflightRequest, PreflightReport
from app.core.preflight.estimator import estimate
from app.core.preflight.risk import assess, policy_decision
from app.core.preflight.persist import persist_report


class PreflightBlockedException(Exception):
    pass


def run_preflight_gate(req: PreflightRequest) -> PreflightReport:
    preflight_hash, estimate_obj = estimate(req)
    risk_obj = assess(req, estimate_obj)
    decision = policy_decision(risk_obj, estimate_obj, req)

    report = PreflightReport(
        job_name=req.job_name,
        preflight_hash=preflight_hash,
        estimate=estimate_obj,
        risk=risk_obj,
        policy_decision=decision,
    )

    persist_report(report)

    if decision == "BLOCK":
        raise PreflightBlockedException(
            f"Preflight BLOCK: risk_score={risk_obj.risk_score}, reasons={risk_obj.risk_reasons}"
        )

    return report