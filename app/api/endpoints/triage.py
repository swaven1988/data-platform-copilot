from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.ai.gateway import AIGatewayService
from app.core.ai.memory_store import TenantMemoryStore
from app.core.ai.triage_engine import FailureTriageEngine
from app.core.auth.rbac_ext import require_roles
from app.core.execution.models import ExecutionState
from app.core.execution.registry import ExecutionRegistry


router = APIRouter(prefix="/api/v2/triage", tags=["triage"])

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_WORKSPACE_ROOT = _PROJECT_ROOT / "workspace"


class TriageRequest(BaseModel):
    job_name: str = Field(..., min_length=1)
    build_id: str = Field(..., min_length=1)
    error_text: Optional[str] = None
    workspace_dir: Optional[str] = None


@router.post(
    "/failure",
    dependencies=[Depends(require_roles("viewer", "operator", "admin"))],
)
def triage_failure(req: TriageRequest, request: Request):
    tenant = getattr(request.state, "tenant", None) or "default"

    ws = Path(req.workspace_dir) if req.workspace_dir else (_DEFAULT_WORKSPACE_ROOT / req.job_name)
    reg = ExecutionRegistry(workspace_dir=ws)

    err_text = (req.error_text or "").strip()
    rec = reg.get(req.job_name)
    if rec is not None:
        if rec.state != ExecutionState.FAILED and not err_text:
            raise HTTPException(status_code=400, detail="triage requires FAILED state or explicit error_text")
        if not err_text:
            err_text = rec.last_error or "unknown failure"

    if not err_text:
        raise HTTPException(status_code=400, detail="error_text is required when no execution record exists")

    memory = TenantMemoryStore(workspace_root=ws if ws.name == "workspace" else ws.parent)
    gateway = AIGatewayService(workspace_dir=(ws if ws.name == "workspace" else ws.parent) / "__ai__")
    engine = FailureTriageEngine(memory=memory, gateway=gateway)

    report = engine.triage(
        tenant=tenant,
        job_name=req.job_name,
        build_id=req.build_id,
        error_text=err_text,
        persist_memory=True,
    )

    return {
        "job_name": req.job_name,
        "build_id": req.build_id,
        "tenant": tenant,
        "report": report.model_dump(),
    }

