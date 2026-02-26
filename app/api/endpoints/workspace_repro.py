from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.workspace.reproducibility import build_repro_manifest, manifest_to_json_dict

router = APIRouter(tags=["workspace"])


class WorkspaceReproResponse(BaseModel):
    kind: str
    job_name: str
    workspace_root: str
    includes: List[str]
    files: List[Dict[str, str]]


@router.get("/workspace/repro/manifest", response_model=WorkspaceReproResponse)
def get_workspace_repro_manifest(
    job_name: str = Query(...),
    includes: Optional[str] = Query(None, description="Comma-separated include dirs relative to workspace job root"),
):
    project_root = Path(__file__).resolve().parents[3]  # ✅ project root
    workspace_root = project_root / "workspace"

    inc_list = [s.strip() for s in (includes or "").split(",") if s.strip()] or None

    try:
        manifest = build_repro_manifest(
            workspace_root=workspace_root,
            job_name=job_name,
            includes=inc_list,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return manifest_to_json_dict(manifest)
