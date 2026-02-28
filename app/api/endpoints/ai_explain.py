from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.ai.gateway import AIGatewayService
from app.core.ai.llm_advisor import LLMExplainableAdvisor, explain_semantic_diff_with_llm
from app.core.auth.rbac_ext import require_roles


router = APIRouter(prefix="/api/v2/ai", tags=["ai"])

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_WORKSPACE_ROOT = _PROJECT_ROOT / "workspace"

_AI_ADVISOR_REGISTRY: dict[str, type] = {
    "llm_semantic_diff_explainer": LLMExplainableAdvisor,
}


class AIExplainRequest(BaseModel):
    advisor_name: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)
    finding: Dict[str, Any] = Field(default_factory=dict)


class AIExplainResponse(BaseModel):
    advisor_name: str
    code: str
    explanation: str
    sections: Dict[str, str]
    finding: Dict[str, Any]


@router.post(
    "/explain",
    response_model=AIExplainResponse,
    dependencies=[Depends(require_roles("viewer", "operator", "admin"))],
)
def ai_explain(req: AIExplainRequest, request: Request):
    tenant = getattr(request.state, "tenant", None) or "default"
    if req.advisor_name not in _AI_ADVISOR_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown AI advisor: {req.advisor_name}. "
                f"Known advisors: {sorted(_AI_ADVISOR_REGISTRY.keys())}"
            ),
        )

    gateway = AIGatewayService(workspace_dir=_DEFAULT_WORKSPACE_ROOT / "__ai__")
    sections = explain_semantic_diff_with_llm(gateway=gateway, finding=req.finding, tenant=tenant)
    explanation = " | ".join([p for p in [sections.get("summary"), sections.get("impact"), sections.get("recommendation")] if p])

    return AIExplainResponse(
        advisor_name=req.advisor_name,
        code=req.code,
        explanation=explanation,
        sections=sections,
        finding=req.finding,
    )

