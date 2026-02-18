from pathlib import Path

from fastapi import APIRouter, Query, HTTPException

from app.core.git_ops.conflict_engine import detect_conflicts, conflict_help

router = APIRouter(prefix="/repo", tags=["Repo"])

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"


@router.get("/conflicts")
def repo_conflicts(job_name: str = Query(...)):
    repo_path = WORKSPACE_ROOT / job_name
    if not repo_path.exists():
        raise HTTPException(status_code=404, detail="workspace repo not found")
    try:
        return detect_conflicts(repo_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/conflicts/help")
def repo_conflicts_help(job_name: str = Query(...)):
    repo_path = WORKSPACE_ROOT / job_name
    if not repo_path.exists():
        raise HTTPException(status_code=404, detail="workspace repo not found")
    try:
        return conflict_help(repo_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
