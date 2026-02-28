from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.ai.gateway import AIGatewayService
from app.core.ai.models import (
    AIBudgetExceededError,
    AIGatewayNotConfiguredError,
    AIGatewayRequest,
    AIGatewayResponse,
    AIOutputValidationError,
)
from app.core.auth.rbac_ext import require_roles
from app.core.billing.ledger import utc_month_key


router = APIRouter(prefix="/api/v2/ai", tags=["ai"])

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_WORKSPACE_ROOT = _PROJECT_ROOT / "workspace"


@router.post(
    "/gateway/complete",
    response_model=AIGatewayResponse,
    dependencies=[Depends(require_roles("viewer", "operator", "admin"))],
)
def complete_gateway(req: AIGatewayRequest, request: Request):
    tenant = getattr(request.state, "tenant", None) or "default"
    month = utc_month_key()
    svc = AIGatewayService(workspace_dir=_DEFAULT_WORKSPACE_ROOT / "__ai__")

    try:
        out = svc.complete(req, tenant=tenant, month=month)
    except AIGatewayNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIBudgetExceededError as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "ai_budget_exceeded",
                "tenant": exc.tenant,
                "month": exc.month,
                "limit_usd": exc.limit_usd,
                "current_usd": exc.current_usd,
            },
        ) from exc
    except AIOutputValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "ai_output_validation_failed",
                "validation_error": exc.validation_error,
            },
        ) from exc

    return AIGatewayResponse(
        content=out.content,
        model=out.model,
        prompt_tokens=out.prompt_tokens,
        completion_tokens=out.completion_tokens,
        cost_usd=out.cost_usd,
        tenant=tenant,
        month=month,
    )

