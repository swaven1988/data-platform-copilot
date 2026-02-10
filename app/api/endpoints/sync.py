from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from app.core.sync.sync_engine import build_sync_plan, apply_plan, load_plan, parse_paths

router = APIRouter(prefix="/sync", tags=["Sync"])

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"


class SyncPlanRequest(BaseModel):
    job_name: str = Field(..., description="Workspace job name under workspace/<job_name>")
    paths: str = Field("jobs,dags,configs", description="Comma-separated scope prefixes to include")
    max_diff_chars: int = Field(200000, ge=1000, le=500000)


class SyncApplyRequest(BaseModel):
    job_name: str
    plan_id: str
    apply_safe_auto: bool = True


@router.post("/plan")
def sync_plan(req: SyncPlanRequest) -> Dict[str, Any]:
    try:
        repo_dir = WORKSPACE_ROOT / req.job_name
        if not repo_dir.exists():
            raise FileNotFoundError(f"Workspace repo not found: {repo_dir}")

        scopes = parse_paths(req.paths)
        plan = build_sync_plan(repo_dir, scopes=scopes, max_diff_chars=req.max_diff_chars)
        return plan
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
    try:
        repo_dir = WORKSPACE_ROOT / req.job_name
        if not repo_dir.exists():
            raise FileNotFoundError(f"Workspace repo not found: {repo_dir}")

        return apply_plan(repo_dir, req.plan_id, apply_safe_auto=req.apply_safe_auto)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
