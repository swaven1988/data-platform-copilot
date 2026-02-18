from pathlib import Path

from fastapi import APIRouter, Query, HTTPException

from app.core.intelligence.impact_graph import build_impact_graph

router = APIRouter(prefix="/advisors", tags=["Advisors"])

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"


@router.get("/impact-graph")
def advisors_impact_graph(job_name: str = Query(...), plan_id: str = Query(...)):
    workspace_job_dir = WORKSPACE_ROOT / job_name
    if not workspace_job_dir.exists():
        raise HTTPException(status_code=404, detail="workspace not found")
    try:
        return build_impact_graph(workspace_job_dir, plan_id=plan_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
