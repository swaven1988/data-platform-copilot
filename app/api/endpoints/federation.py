from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.federation.federation_manager import (
    FederatedRepoSpec,
    FederationError,
    load_federation_config,
    upsert_repo,
    sync_repo,
    sync_all,
)

# IMPORTANT: keep workspace root resolution consistent with your existing workspace code.
# If you already have a central WORKSPACE_ROOT helper, replace this with it.
REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = REPO_ROOT / "workspace"

router = APIRouter(prefix="/federation", tags=["federation"])


class FederationConnectRequest(BaseModel):
    job_name: str
    name: str = Field(..., description="Logical repo name for federation")
    url: str
    ref: str = "main"
    subdir: Optional[str] = None
    paths: Optional[List[str]] = None
    sync: bool = True


@router.get("/config")
def get_config(job_name: str) -> Dict[str, Any]:
    return load_federation_config(WORKSPACE_ROOT, job_name)


@router.post("/connect")
def connect_repo(req: FederationConnectRequest) -> Dict[str, Any]:
    try:
        spec = FederatedRepoSpec(
            name=req.name,
            url=req.url,
            ref=req.ref,
            subdir=req.subdir,
            paths=req.paths,
        )
        cfg = upsert_repo(WORKSPACE_ROOT, req.job_name, spec)
        out: Dict[str, Any] = {"job_name": req.job_name, "config": cfg}
        if req.sync:
            out["sync_result"] = sync_repo(WORKSPACE_ROOT, req.job_name, spec)
        return out
    except FederationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sync")
def sync(req: Dict[str, Any]) -> Dict[str, Any]:
    # body: {"job_name":"...", "name":"optional"}
    job_name = req.get("job_name")
    if not job_name:
        raise HTTPException(status_code=400, detail="job_name is required")

    name = req.get("name")
    try:
        if name:
            cfg = load_federation_config(WORKSPACE_ROOT, job_name)
            match = next((r for r in cfg.get("repos", []) if r.get("name") == name), None)
            if not match:
                raise HTTPException(status_code=404, detail=f"repo not found: {name}")
            spec = FederatedRepoSpec(
                name=match["name"],
                url=match["url"],
                ref=match.get("ref", "main"),
                subdir=match.get("subdir"),
                paths=match.get("paths"),
            )
            return {"job_name": job_name, "synced": [sync_repo(WORKSPACE_ROOT, job_name, spec)]}
        return sync_all(WORKSPACE_ROOT, job_name)
    except FederationError as e:
        raise HTTPException(status_code=400, detail=str(e))
