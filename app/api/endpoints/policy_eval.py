from fastapi import APIRouter, HTTPException
from pathlib import Path
from app.core.compiler.policy_binding import PolicyBinding
from app.core.compiler.policy_models import IntelligenceThresholds

router = APIRouter(prefix="/api/v2/policy", tags=["policy"])

WORKSPACE_ROOT = Path("workspace")
engine = PolicyBinding(WORKSPACE_ROOT)


@router.post("/evaluate")
def evaluate_policy(
    job_name: str,
    contract_hash: str,
    plan_hash: str,
    intelligence_hash: str,
    thresholds: IntelligenceThresholds
):
    try:
        return engine.evaluate(
            job_name=job_name,
            contract_hash=contract_hash,
            plan_hash=plan_hash,
            intelligence_hash=intelligence_hash,
            thresholds=thresholds
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{job_name}/{policy_eval_hash}")
def get_policy_eval(job_name: str, policy_eval_hash: str):
    obj = engine.load(job_name, policy_eval_hash)
    if not obj:
        raise HTTPException(status_code=404, detail="Policy evaluation not found")
    return obj