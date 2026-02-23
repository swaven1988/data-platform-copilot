# app/api/endpoints/execution.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from app.core.execution.models import ExecutionState
from app.core.execution.registry import ExecutionRegistry
from app.core.execution.executor import Executor
from app.core.execution.audit import audit_context

# You likely already have a project root constant; keep aligned with your codebase:
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_WORKSPACE = PROJECT_ROOT / "workspace"


router = APIRouter(prefix="/api/v2/build", tags=["execution"])


class ApplyRequest(BaseModel):
    job_name: str
    workspace_dir: Optional[str] = None


class RunRequest(BaseModel):
    job_name: str
    workspace_dir: Optional[str] = None


def _workspace_dir(workspace_dir: Optional[str], job_name: str) -> Path:
    # default workspace pattern: workspace/<job_name>
    if workspace_dir:
        return Path(workspace_dir)
    return DEFAULT_WORKSPACE / job_name


def _tenant(x_tenant: Optional[str]) -> str:
    return x_tenant or "default"


@router.post("/apply")
def apply_build(
    req: ApplyRequest,
    contract_hash: str = Query(...),
    x_tenant: Optional[str] = Header(default=None, alias="X-Tenant"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> Dict[str, Any]:
    ws = _workspace_dir(req.workspace_dir, req.job_name)

    reg = ExecutionRegistry(workspace_dir=ws)

    # Init execution record at PRECHECK_PASSED (apply gate boundary)
    rec = reg.init_if_missing(
        job_name=req.job_name,
        build_id=contract_hash,
        tenant=_tenant(x_tenant),
        runtime_profile=None,
        preflight_hash=None,
        cost_estimate=None,
        request_id=x_request_id,
        initial_state=ExecutionState.PRECHECK_PASSED,
    )

    exec_ = Executor(registry=reg)
    try:
        out = exec_.apply(req.job_name)
        return {"ok": True, "execution": out, "audit": audit_context(tenant=_tenant(x_tenant), request_id=x_request_id)}
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
    reg = ExecutionRegistry(workspace_dir=ws)

    # Ensure record exists; if not, create in APPLIED (best-effort)
    reg.init_if_missing(
        job_name=req.job_name,
        build_id=contract_hash,
        tenant=_tenant(x_tenant),
        runtime_profile=None,
        preflight_hash=None,
        cost_estimate=None,
        request_id=x_request_id,
        initial_state=ExecutionState.APPLIED,
    )

    exec_ = Executor(registry=reg)
    try:
        out = exec_.run(req.job_name)
        return {"ok": True, "execution": out, "audit": audit_context(tenant=_tenant(x_tenant), request_id=x_request_id)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status/{job_name}")
def status(
    job_name: str,
    workspace_dir: Optional[str] = None,
    x_tenant: Optional[str] = Header(default=None, alias="X-Tenant"),
) -> Dict[str, Any]:
    ws = _workspace_dir(workspace_dir, job_name)
    reg = ExecutionRegistry(workspace_dir=ws)
    rec = reg.get(job_name)
    if rec is None:
        raise HTTPException(status_code=404, detail="execution not found")
    return {"job_name": job_name, "state": rec.state.value, "execution": rec.to_dict(), "tenant": _tenant(x_tenant)}


@router.get("/history/{job_name}")
def history(
    job_name: str,
    workspace_dir: Optional[str] = None,
) -> Dict[str, Any]:
    ws = _workspace_dir(workspace_dir, job_name)
    reg = ExecutionRegistry(workspace_dir=ws)
    return {"job_name": job_name, "events": reg.history(job_name)}