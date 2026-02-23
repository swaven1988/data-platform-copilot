import json
from fastapi import APIRouter, HTTPException
from pathlib import Path
from app.core.compiler.intelligence_engine import IntelligenceEngine
from app.core.compiler.intelligence_models import ClusterProfile

router = APIRouter(prefix="/api/v2/intelligence", tags=["intelligence"])

WORKSPACE_ROOT = Path("workspace")
engine = IntelligenceEngine(WORKSPACE_ROOT)


@router.post(
    "/analyze",
    operation_id="v2_intelligence_analyze",
)
def analyze(
    job_name: str,
    plan_hash: str,
    cluster_profile: ClusterProfile
):
    try:
        return engine.analyze(
            job_name=job_name,
            plan_hash=plan_hash,
            cluster_profile=cluster_profile
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{job_name}/{intelligence_hash}",
    operation_id="v2_intelligence_get_report",
)
def get_report(job_name: str, intelligence_hash: str):
    path = (
        WORKSPACE_ROOT
        / job_name
        / ".copilot"
        / "intelligence"
        / f"{intelligence_hash}.json"
    )

    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    return json.loads(path.read_text())