from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.ai.gateway import AIGatewayService
from app.core.ai.intent_hybrid import parse_intent_hybrid
from app.core.auth.rbac_ext import require_roles


router = APIRouter(prefix="/api/v2/intent", tags=["intent"])

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_WORKSPACE_ROOT = _PROJECT_ROOT / "workspace"


class IntentParseRequest(BaseModel):
    requirement: str = Field(..., min_length=1)
    job_name_hint: Optional[str] = None
    defaults: Dict[str, Any] = Field(default_factory=dict)
    confidence_threshold: float = 0.75


class IntentParseResponse(BaseModel):
    spec: Dict[str, Any]
    parser_confidence: float
    final_confidence: float
    parser_warning_count: int
    augmented: bool
    augmentation: Dict[str, Any] | None
    explain: Dict[str, Any]


@router.post(
    "/parse",
    response_model=IntentParseResponse,
    dependencies=[Depends(require_roles("viewer", "operator", "admin"))],
)
def parse_intent(req: IntentParseRequest, request: Request):
    tenant = getattr(request.state, "tenant", None) or "default"
    gateway = AIGatewayService(workspace_dir=_DEFAULT_WORKSPACE_ROOT / "__ai__")

    result = parse_intent_hybrid(
        requirement=req.requirement,
        job_name_hint=req.job_name_hint,
        defaults=req.defaults,
        tenant=tenant,
        gateway=gateway,
        confidence_threshold=req.confidence_threshold,
    )

    return IntentParseResponse(
        spec=result.spec,
        parser_confidence=result.parser_confidence,
        final_confidence=result.final_confidence,
        parser_warning_count=result.parser_warning_count,
        augmented=result.augmented,
        augmentation=result.augmentation.model_dump() if result.augmentation else None,
        explain=result.explain,
    )

