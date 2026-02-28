# FILE: app/api/endpoints/execution.py
# app/api/endpoints/execution.py
# PATCH: apply policy guardrails BEFORE transitioning to APPLIED.
# PATCH: Phase 10 - backend selector for run()
# PATCH: Phase 10.1 - real RUNNING + status polling + cancel

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query
from pydantic import BaseModel

from app.core.ai.gateway import AIGatewayService
from app.core.ai.memory_store import TenantMemoryStore
from app.core.ai.triage_engine import FailureTriageEngine
from app.core.execution.audit import audit_context
from app.core.execution.executor import Executor
from app.core.execution.guards import evaluate_apply_guardrails
from app.core.execution.models import ExecutionState
from app.core.execution.registry import ExecutionRegistry

import os

PROJECT_ROOT = Path(__file__).resolve().parents[3]
_workspace_root_env = os.getenv("COPILOT_WORKSPACE_ROOT", "")
DEFAULT_WORKSPACE = Path(_workspace_root_env).resolve() if _workspace_root_env else PROJECT_ROOT / "workspace"

router = APIRouter(prefix="/api/v2/build", tags=["execution"])



class ApplyRequest(BaseModel):
    job_name: str
    workspace_dir: Optional[str] = None

    # Phase 9: execution enforcement inputs
    preflight_hash: Optional[str] = None

    # Optional explicit override (deterministic tests / future pipeline)
    cost_estimate: Optional[Dict[str, Any]] = None


class RunRequest(BaseModel):
    job_name: str
    workspace_dir: Optional[str] = None
    backend: Optional[str] = "local"


class CancelRequest(BaseModel):
    job_name: str
    workspace_dir: Optional[str] = None


import re

_JOB_NAME_RE = re.compile(r'^[a-zA-Z0-9_\-]{1,128}$')


def _workspace_dir(workspace_dir: Optional[str], job_name: str) -> Path:
    if not _JOB_NAME_RE.match(job_name):
        raise HTTPException(
            status_code=400,
            detail="Invalid job_name: must be alphanumeric, underscores, or hyphens, max 128 chars",
        )
    if workspace_dir:
        candidate = Path(workspace_dir).resolve()
        allowed = DEFAULT_WORKSPACE.resolve()
        try:
            candidate.relative_to(allowed)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid workspace_dir: must be within the allowed workspace root",
            )
        return candidate
    return DEFAULT_WORKSPACE / job_name



def _tenant(x_tenant: Optional[str]) -> str:
    return x_tenant or "default"


def _run_background_triage(
    *,
    tenant: str,
    job_name: str,
    build_id: str,
    error_text: str,
    workspace_root: Path,
) -> None:
    """Fire-and-forget triage. Errors are logged, never raised."""
    try:
        memory = TenantMemoryStore(workspace_root=workspace_root)
        gateway = AIGatewayService(workspace_dir=workspace_root / "__ai__")
        engine = FailureTriageEngine(memory=memory, gateway=gateway)
        engine.triage(
            tenant=tenant,
            job_name=job_name,
            build_id=build_id,
            error_text=error_text,
            persist_memory=True,
        )
    except Exception:
        import logging

        logging.getLogger("copilot.triage").warning(
            "Background triage failed for job=%s build=%s", job_name, build_id, exc_info=True
        )


@router.post("/apply")
def apply_build(
    req: ApplyRequest,
    contract_hash: str = Query(...),
    x_tenant: Optional[str] = Header(default=None, alias="X-Tenant"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> Dict[str, Any]:
    ws = _workspace_dir(req.workspace_dir, req.job_name)
    tenant = _tenant(x_tenant)

    reg = ExecutionRegistry(workspace_dir=ws)

    # init at PRECHECK_PASSED (apply boundary)
    reg.init_if_missing(
        job_name=req.job_name,
        build_id=contract_hash,
        tenant=tenant,
        runtime_profile=None,
        preflight_hash=req.preflight_hash,
        cost_estimate=req.cost_estimate,
        request_id=x_request_id,
        initial_state=ExecutionState.PRECHECK_PASSED,
    )

    # Phase 9: policy/cost enforcement
    decision, details, preflight_report, cost_used = evaluate_apply_guardrails(
        tenant=tenant,
        workspace_dir=ws,
        build_id=contract_hash,
        preflight_hash=req.preflight_hash,
        cost_estimate_override=req.cost_estimate,
    )

    # attach to record (persisted)
    rec = reg.get(req.job_name)
    if rec is not None:
        rec.preflight_hash = req.preflight_hash or rec.preflight_hash
        rec.cost_estimate = cost_used or rec.cost_estimate
        reg.upsert(rec)

    if decision == "BLOCK":
        # Transition to BLOCKED and return 409 (conflict / execution denied)
        try:
            reg.transition(
                job_name=req.job_name,
                dst=ExecutionState.BLOCKED,
                message="blocked by execution policy",
                data={"decision": decision, "details": details},
            )
        except Exception:
            # even if transition fails, still block
            pass
        raise HTTPException(status_code=409, detail={"blocked": True, "decision": decision, "details": details})

    # WARN does not block: store as audit event (non-terminal)
    if decision == "WARN":
        try:
            reg.transition(
                job_name=req.job_name,
                dst=ExecutionState.PRECHECK_PASSED,
                message="warned by execution policy",
                data={"decision": decision, "details": details},
            )
        except Exception:
            pass

    exec_ = Executor(registry=reg)
    try:
        out = exec_.apply(req.job_name)
        return {
            "ok": True,
            "decision": decision,
            "policy": details,
            "execution": out,
            "audit": audit_context(tenant=tenant, request_id=x_request_id),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/run")
def run_build(
    req: RunRequest,
    contract_hash: str = Query(...),
    x_tenant: Optional[str] = Header(default=None, alias="X-Tenant"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> Dict[str, Any]:
    ws = _workspace_dir(req.workspace_dir, req.job_name)
    tenant = _tenant(x_tenant)

    reg = ExecutionRegistry(workspace_dir=ws)

    reg.init_if_missing(
        job_name=req.job_name,
        build_id=contract_hash,
        tenant=tenant,
        runtime_profile=None,
        preflight_hash=None,
        cost_estimate=None,
        request_id=x_request_id,
        initial_state=ExecutionState.APPLIED,
    )

    exec_ = Executor(registry=reg)
    try:
        backend = req.backend or "local"
        out = exec_.run(
            req.job_name,
            config={},
            backend_name=backend,
        )
        return {"ok": True, "execution": out, "audit": audit_context(tenant=tenant, request_id=x_request_id)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cancel")
def cancel_build(
    req: CancelRequest,
    x_tenant: Optional[str] = Header(default=None, alias="X-Tenant"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> Dict[str, Any]:
    ws = _workspace_dir(req.workspace_dir, req.job_name)
    tenant = _tenant(x_tenant)
    reg = ExecutionRegistry(workspace_dir=ws)
    exec_ = Executor(registry=reg)

    try:
        # IMPORTANT: match your Phase-13 Executor.cancel signature
        out = exec_.cancel(job_name=req.job_name, tenant=tenant, request_id=x_request_id)
        return {"ok": True, "execution": out, "audit": audit_context(tenant=tenant, request_id=x_request_id)}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="execution not found")
    except ValueError as e:
        msg = str(e)
        low = msg.lower()
        if "not found" in low:
            raise HTTPException(status_code=404, detail=msg)
        if "illegal transition" in low or "requires state" in low:
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status/{job_name}")
def status(
    job_name: str,
    workspace_dir: Optional[str] = None,
    x_tenant: Optional[str] = Header(default=None, alias="X-Tenant"),
    background_tasks: BackgroundTasks = None,
) -> Dict[str, Any]:
    ws = _workspace_dir(workspace_dir, job_name)
    tenant = _tenant(x_tenant)
    reg = ExecutionRegistry(workspace_dir=ws)

    rec = reg.get(job_name)
    if rec is None:
        raise HTTPException(status_code=404, detail="execution not found")

    exec_ = Executor(registry=reg)
    try:
        updated = exec_.refresh_status(job_name)
    except Exception:
        updated = rec.to_dict()

    if updated.get("state") == ExecutionState.FAILED.value and background_tasks is not None:
        build_id = str(updated.get("build_id") or "")
        if build_id:
            background_tasks.add_task(
                _run_background_triage,
                tenant=tenant,
                job_name=job_name,
                build_id=build_id,
                error_text=str(updated.get("last_error") or "execution failed"),
                workspace_root=ws if ws.name == "workspace" else ws.parent,
            )

    return {"job_name": job_name, "state": updated["state"], "execution": updated, "tenant": tenant}


@router.get("/history/{job_name}")
def history(
    job_name: str,
    workspace_dir: Optional[str] = None,
) -> Dict[str, Any]:
    ws = _workspace_dir(workspace_dir, job_name)
    reg = ExecutionRegistry(workspace_dir=ws)
    return {"job_name": job_name, "events": reg.history(job_name)}
