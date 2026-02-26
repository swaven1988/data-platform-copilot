from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.endpoints.workspace_repro import get_workspace_repro_manifest  # reuse existing handler

router = APIRouter(tags=["workspace"])


class ReproCompareResponse(BaseModel):
    kind: str
    job_a: str
    job_b: str
    summary: Dict[str, int]
    added: List[Dict[str, Any]]
    removed: List[Dict[str, Any]]
    changed: List[Dict[str, Any]]


@router.get("/workspace/repro/compare", response_model=ReproCompareResponse)
def compare_workspace_repro_manifests(
    job_a: str = Query(...),
    job_b: str = Query(...),
):
    a = get_workspace_repro_manifest(job_name=job_a, includes=None)
    b = get_workspace_repro_manifest(job_name=job_b, includes=None)

    a_map = {x["path"]: x["sha256"] for x in a["files"]}
    b_map = {x["path"]: x["sha256"] for x in b["files"]}

    added = [{"path": p, "sha256": b_map[p]} for p in sorted(set(b_map) - set(a_map))]
    removed = [{"path": p, "sha256": a_map[p]} for p in sorted(set(a_map) - set(b_map))]

    changed = []
    for p in sorted(set(a_map) & set(b_map)):
        if a_map[p] != b_map[p]:
            changed.append({"path": p, "sha256_a": a_map[p], "sha256_b": b_map[p]})

    return {
        "kind": "workspace_repro_compare",
        "job_a": job_a,
        "job_b": job_b,
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
        },
        "added": added,
        "removed": removed,
        "changed": changed,
    }
