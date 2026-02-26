from __future__ import annotations
from pathlib import Path

from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.intelligence.explainability import explain_with_registry

# IMPORTANT: use the advisors plugin registry you already have
from app.plugins.advisors._internal.registry import PluginRegistry as AdvisorsRegistry

router = APIRouter(tags=["advisors"])


class ExplainPayload(BaseModel):
    advisor_name: str = Field(..., description="Advisor/plugin name")
    code: str = Field(..., description="Finding code")
    finding: Dict[str, Any] = Field(default_factory=dict, description="Original finding payload from advisors")


class ExplainResponse(BaseModel):
    advisor_name: str
    code: str
    explanation: str
    finding: Dict[str, Any]


def _get_registry() -> AdvisorsRegistry:
    # app/api/endpoints/advisor_explain.py -> project root -> app/plugins/advisors
    plugins_dir = Path(__file__).resolve().parents[3] / "plugins" / "advisors"
    return AdvisorsRegistry(str(plugins_dir))


@router.post("/advisors/explain", response_model=ExplainResponse)
def explain_advisor_finding(payload: ExplainPayload):
    registry = _get_registry()
    return explain_with_registry(
        registry=registry,
        advisor_name=payload.advisor_name,
        code=payload.code,
        finding=payload.finding,
    )
