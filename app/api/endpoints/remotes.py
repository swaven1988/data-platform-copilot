from pathlib import Path
from fastapi import APIRouter, Query, Body, HTTPException
from typing import Dict, Any, Optional

from app.core.git_ops.remotes import add_remote, list_remotes, fetch, status

router = APIRouter(prefix="/repo/remotes", tags=["Repo"])

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"


def _repo(job_name: str) -> Path:
    p = WORKSPACE_ROOT / job_name
    if not p.exists():
        raise HTTPException(status_code=404, detail="workspace repo not found")
    return p


@router.get("")
def remotes_list(job_name: str = Query(...)):
    try:
        return list_remotes(_repo(job_name))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/add")
def remotes_add(job_name: str = Query(...), payload: Dict[str, Any] = Body(...)):
    name = (payload or {}).get("name")
    url = (payload or {}).get("url")
    try:
        return add_remote(_repo(job_name), name=name, url=url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/fetch")
def remotes_fetch(job_name: str = Query(...), payload: Dict[str, Any] = Body(...)):
    name = (payload or {}).get("name")
    try:
        return fetch(_repo(job_name), name=name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status")
def remotes_status(job_name: str = Query(...), name: str = Query(...), branch: str = Query("main")):
    try:
        return status(_repo(job_name), name=name, branch=branch)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
