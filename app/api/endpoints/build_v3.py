import logging

from fastapi import APIRouter, HTTPException
from pathlib import Path
from uuid import uuid4
from app.core.compiler.build_gate import BuildGate

router = APIRouter(prefix="/api/v3/build", tags=["build_v3"])

WORKSPACE_ROOT = Path("workspace")
gate = BuildGate(WORKSPACE_ROOT)
_RUNNER_ALLOWED_DECISIONS = {"allow", "proceed", "approved"}
logger = logging.getLogger(__name__)


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

        lineage = gate.record_lineage(
            job_name=job_name,
            contract_hash=contract_hash,
            plan_hash=plan_hash,
            intelligence_hash=intelligence_hash,
            policy_eval_hash=policy_eval_hash,
            build_id=build_id
        )

        # Wire to Build V2 runner when all hashes are valid and policy allows.
        # Only attempt a full build if the workspace exists (avoids test-env errors).
        build_result = None
        decision = str(verdict.get("decision", "")).strip().lower()
        if decision in _RUNNER_ALLOWED_DECISIONS:
            workspace_job_dir = WORKSPACE_ROOT / job_name
            if workspace_job_dir.exists():
                try:
                    from app.api.endpoints.build_v2_impl import build_v2_from_spec
                    from app.core.spec_schema import CopilotSpec
                    import yaml
                    spec_path = workspace_job_dir / "copilot_spec.yaml"
                    if spec_path.exists():
                        raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
                        spec = CopilotSpec(**raw)
                        build_result = build_v2_from_spec(
                            spec,
                            write_spec_yaml=False,
                            contract_hash=contract_hash,
                        )
                except Exception as exc:
                    # Non-fatal: v3 gate decision still returned even if runner fails
                    logger.exception(
                        "Build V3 runner failed: job=%s build_id=%s",
                        job_name,
                        build_id,
                    )
                    build_result = {
                        "status": "failed",
                        "message": "Build execution failed",
                    }

        return {
            "build_id": build_id,
            "decision": verdict["decision"],
            "policy_profile": verdict["policy_profile"],
            "policy_reasons": verdict["reasons"],
            "lineage": lineage,
            "build_result": build_result,
        }

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
