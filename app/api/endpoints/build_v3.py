import logging
import os

from fastapi import APIRouter, HTTPException
from pathlib import Path
from uuid import uuid4
from app.core.compiler.build_gate import BuildGate
from app.core.build_approval import BuildApprovalStore, evaluate_high_risk_requirement

router = APIRouter(prefix="/api/v3/build", tags=["build_v3"])

WORKSPACE_ROOT = Path("workspace")
gate = BuildGate(WORKSPACE_ROOT)
_RUNNER_ALLOWED_DECISIONS = {"allow", "proceed", "approved"}
logger = logging.getLogger(__name__)


def _risk_score_for_job(*, job_name: str, intelligence_hash: str) -> float | None:
    ip = WORKSPACE_ROOT / job_name / ".copilot" / "intelligence" / f"{intelligence_hash}.json"
    if not ip.exists():
        return None
    try:
        import json

        obj = json.loads(ip.read_text(encoding="utf-8"))
    except Exception:
        return None

    raw = obj.get("risk_score")
    if isinstance(raw, (int, float)):
        val = float(raw)
        # normalize integer risk-score scales if needed
        if val > 1.0:
            val = val / 100.0
        return max(0.0, min(1.0, val))
    return None


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

        risk_threshold = float(os.getenv("COPILOT_HIGH_RISK_APPROVAL_THRESHOLD", "0.70"))
        risk_score = _risk_score_for_job(job_name=job_name, intelligence_hash=intelligence_hash)
        approval_req = evaluate_high_risk_requirement(risk_score=risk_score, threshold=risk_threshold)

        approval = None
        if approval_req.required:
            approval_store = BuildApprovalStore(workspace_root=WORKSPACE_ROOT)
            approval = approval_store.get_approval(job_name=job_name, plan_hash=plan_hash)
            if approval is None:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "approval_required",
                        "message": "High-risk build requires approval before execution.",
                        "job_name": job_name,
                        "plan_hash": plan_hash,
                        "risk_score": approval_req.risk_score,
                    },
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
            "risk_score": risk_score,
            "approval_required": approval_req.required,
            "approval": approval,
            "lineage": lineage,
            "build_result": build_result,
        }

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
