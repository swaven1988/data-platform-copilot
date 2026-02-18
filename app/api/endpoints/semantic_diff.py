from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Query, HTTPException

from app.core.git_ops.semantic_diff import semantic_diff

router = APIRouter(prefix="/repo", tags=["Repo"])

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"


def _parse_paths(paths: Optional[str]) -> Optional[List[str]]:
    if not paths:
        return None
    items = [p.strip() for p in paths.split(",") if p.strip()]
    return items or None


@router.get("/semantic-diff")
def repo_semantic_diff(
    job_name: str = Query(...),
    ref_a: str = Query(...),
    ref_b: str = Query(...),
    paths: Optional[str] = Query(None),
):
    repo_path = WORKSPACE_ROOT / job_name
    if not repo_path.exists():
        raise HTTPException(status_code=404, detail="workspace repo not found")
    try:
        return semantic_diff(repo_path, ref_a=ref_a, ref_b=ref_b, paths=_parse_paths(paths))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
