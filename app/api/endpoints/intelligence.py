from fastapi import APIRouter, Body
from typing import List, Dict
from app.core.intelligence.intelligence_pipeline import IntelligencePipeline

router = APIRouter()


@router.get("/intelligence/analyze")
def analyze(base_ref: str = "upstream/main"):
    return IntelligenceEngine.analyze(base_ref)

@router.post("/intelligence/prioritize")
def prioritize_advisors(
    resolved_advisors: List[Dict] = Body(...),
    base_ref: str = "upstream/main"
):
    return IntelligencePipeline.run(resolved_advisors, base_ref)