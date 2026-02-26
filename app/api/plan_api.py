from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.build_plan.store import list_plans, load_plan, tail_events

router = APIRouter(prefix="/build", tags=["Build (Plan APIs)"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"


def _job_dir(job_name: str) -> Path:
    p = WORKSPACE_ROOT / job_name
    return p


@router.get("/plans")
def get_plans(
    job_name: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    try:
        repo_dir = _job_dir(job_name)
        if not repo_dir.exists():
            raise FileNotFoundError(f"Workspace repo not found: {repo_dir}")

        plans = list_plans(repo_dir, limit=limit)
        return {
            "job_name": job_name,
            "count": len(plans),
            "plans": [
                {"plan_id": p.plan_id, "created_ts": p.created_ts, "file_path": p.file_path}
                for p in plans
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/plan/{plan_id}")
def get_plan(
    plan_id: str,
    job_name: str = Query(..., min_length=1),
) -> Dict[str, Any]:
    try:
        repo_dir = _job_dir(job_name)
        if not repo_dir.exists():
            raise FileNotFoundError(f"Workspace repo not found: {repo_dir}")

        return load_plan(repo_dir, plan_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/events")
def get_events(
    job_name: str = Query(..., min_length=1),
    limit: int = Query(200, ge=1, le=2000),
) -> Dict[str, Any]:
    try:
        repo_dir = _job_dir(job_name)
        if not repo_dir.exists():
            raise FileNotFoundError(f"Workspace repo not found: {repo_dir}")

        events = tail_events(repo_dir, limit=limit)
        return {
            "job_name": job_name,
            "count": len(events),
            "events": events,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
