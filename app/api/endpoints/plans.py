from fastapi import APIRouter, HTTPException
from pathlib import Path
from app.core.compiler.plan_engine import PlanEngine

router = APIRouter(prefix="/api/v2/plans", tags=["plans"])

WORKSPACE_ROOT = Path("workspace")
engine = PlanEngine(WORKSPACE_ROOT)


@router.post("/create")
def create_plan(
    job_name: str,
    contract_hash: str,
    plugin_fingerprint: str,
    policy_profile: str
):
    try:
        result = engine.generate_plan(
            job_name=job_name,
            contract_hash=contract_hash,
            plugin_fingerprint=plugin_fingerprint,
            policy_profile=policy_profile
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{job_name}/{plan_hash}")
def get_plan(job_name: str, plan_hash: str):
    plan = engine.load_plan(job_name, plan_hash)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan.model_dump()