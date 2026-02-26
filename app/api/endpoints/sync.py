from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.sync.sync_engine import (
    apply_plan,
    build_sync_plan,
    load_plan,
    parse_paths,
    simulate_rebase_for_plan,
)

from app.core.sync.guardrails import (
    SyncGuardError,
    validate_clean_workspace,
    validate_baseline,
)

router = APIRouter(prefix="/sync", tags=["Sync"])

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"


class SyncPlanRequest(BaseModel):
    job_name: str
    paths: str = "jobs,dags,configs"
    max_diff_chars: int = Field(200000, ge=1000, le=500000)


class SyncApplyRequest(BaseModel):
    job_name: str
    plan_id: str
    apply_safe_auto: bool = True
    # Phase 21 hardening inputs (optional for backward compatibility)
    baseline_commit: str | None = None


class SyncRebaseSimulateRequest(BaseModel):
    job_name: str
    plan_id: str


@router.post("/plan")
def sync_plan(req: SyncPlanRequest) -> Dict[str, Any]:
    try:
        repo_dir = WORKSPACE_ROOT / req.job_name
        if not repo_dir.exists():
            raise FileNotFoundError(f"Workspace repo not found: {repo_dir}")

        scopes = parse_paths(req.paths)
        return build_sync_plan(repo_dir, scopes=scopes, max_diff_chars=req.max_diff_chars)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/plan/{plan_id}")
def get_plan(plan_id: str, job_name: str = Query(...)) -> Dict[str, Any]:
    try:
        repo_dir = WORKSPACE_ROOT / job_name
        if not repo_dir.exists():
            raise FileNotFoundError(f"Workspace repo not found: {repo_dir}")
        return load_plan(repo_dir, plan_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/apply")
def sync_apply(req: SyncApplyRequest) -> Dict[str, Any]:
    """
    Canonical apply endpoint: /sync/apply (router prefix already includes /sync).
    Phase 21 guardrails:
      - block dirty workspace
      - optional baseline commit validation (if provided)
    """
    try:
        repo_dir = WORKSPACE_ROOT / req.job_name
        if not repo_dir.exists():
            raise FileNotFoundError(f"Workspace repo not found: {repo_dir}")

        # Phase 21 guardrails
        validate_clean_workspace(repo_dir)
        if req.baseline_commit:
            validate_baseline(repo_dir, req.baseline_commit)

        return apply_plan(repo_dir, req.plan_id, apply_safe_auto=req.apply_safe_auto)

    except SyncGuardError as e:
        # conflict / drift / dirty workspace => 409 is appropriate
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/rebase/simulate")
def simulate_rebase(req: SyncRebaseSimulateRequest) -> Dict[str, Any]:
    try:
        repo_dir = WORKSPACE_ROOT / req.job_name
        if not repo_dir.exists():
            raise FileNotFoundError(f"Workspace repo not found: {repo_dir}")
        return simulate_rebase_for_plan(repo_dir, req.plan_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))