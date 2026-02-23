# app/api/endpoints/preflight.py

from fastapi import APIRouter, HTTPException
from app.core.preflight.models import (
    PreflightRequest,
    PreflightReport,
)
from app.core.preflight.estimator import estimate
from app.core.preflight.risk import assess, policy_decision
from app.core.preflight.persist import persist_report, load_report

router = APIRouter(prefix="/api/v2/preflight", tags=["preflight"])


@router.post("/analyze", response_model=PreflightReport)
def analyze(req: PreflightRequest):
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
    return report


@router.get("/report/{job_name}/{preflight_hash}")
def get_report(job_name: str, preflight_hash: str):
    data = load_report(job_name, preflight_hash)
    if not data:
        raise HTTPException(status_code=404, detail="preflight_report_not_found")
    return data