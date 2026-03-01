"""Build approval API for high-risk plan execution gates."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth.rbac_ext import require_roles
from app.core.build_approval import BuildApprovalStore


PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"

router = APIRouter(prefix="/api/v2/build/approvals", tags=["build_approvals"])


class ApprovalCreateRequest(BaseModel):
    job_name: str
    plan_hash: str
    approver: str
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@router.post("", dependencies=[Depends(require_roles("operator", "admin"))])
def create_approval(req: ApprovalCreateRequest) -> Dict[str, Any]:
    store = BuildApprovalStore(workspace_root=WORKSPACE_ROOT)
    obj = store.save_approval(
        job_name=req.job_name,
        plan_hash=req.plan_hash,
        approver=req.approver,
        notes=req.notes,
        metadata=req.metadata,
    )
    return {"ok": True, "approval": obj}


@router.get("/{job_name}/{plan_hash}", dependencies=[Depends(require_roles("viewer", "operator", "admin"))])
def get_approval(job_name: str, plan_hash: str) -> Dict[str, Any]:
    store = BuildApprovalStore(workspace_root=WORKSPACE_ROOT)
    obj = store.get_approval(job_name=job_name, plan_hash=plan_hash)
    if obj is None:
        raise HTTPException(status_code=404, detail="approval_not_found")
    return {"ok": True, "approval": obj}


@router.delete(
    "/{job_name}/{plan_hash}",
    dependencies=[Depends(require_roles("admin"))],
)
def revoke_approval(job_name: str, plan_hash: str) -> Dict[str, Any]:
    """Revoke (delete) an existing approval. Requires admin role."""
    store = BuildApprovalStore(workspace_root=WORKSPACE_ROOT)
    existed = store.revoke_approval(job_name=job_name, plan_hash=plan_hash)
    if not existed:
        raise HTTPException(status_code=404, detail="approval_not_found")
    return {"ok": True, "revoked": True, "job_name": job_name, "plan_hash": plan_hash}


@router.get(
    "/{job_name}",
    dependencies=[Depends(require_roles("viewer", "operator", "admin"))],
)
def list_approvals(job_name: str) -> Dict[str, Any]:
    """List all stored approvals for a job (across all plan hashes)."""
    store = BuildApprovalStore(workspace_root=WORKSPACE_ROOT)
    approvals = store.list_approvals(job_name=job_name)
    return {"ok": True, "job_name": job_name, "approvals": approvals}

