from fastapi import APIRouter, HTTPException
from pathlib import Path
from uuid import uuid4
from app.core.compiler.build_gate import BuildGate

router = APIRouter(prefix="/api/v3/build", tags=["build_v3"])

WORKSPACE_ROOT = Path("workspace")
gate = BuildGate(WORKSPACE_ROOT)


@router.post("/run")
def run_build(
    job_name: str,
    contract_hash: str,
    plan_hash: str,
    intelligence_hash: str,
    policy_eval_hash: str
):
    build_id = str(uuid4())

    try:
        verdict = gate.validate_inputs(
            job_name=job_name,
            contract_hash=contract_hash,
            plan_hash=plan_hash,
            intelligence_hash=intelligence_hash,
            policy_eval_hash=policy_eval_hash
        )

        # Placeholder hook — integrate with your existing Build V2 runner here.
        # You will call your existing build runner with build_id and job_name.

        lineage = gate.record_lineage(
            job_name=job_name,
            contract_hash=contract_hash,
            plan_hash=plan_hash,
            intelligence_hash=intelligence_hash,
            policy_eval_hash=policy_eval_hash,
            build_id=build_id
        )

        return {
            "build_id": build_id,
            "decision": verdict["decision"],
            "policy_profile": verdict["policy_profile"],
            "policy_reasons": verdict["reasons"],
            "lineage": lineage
        }

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))