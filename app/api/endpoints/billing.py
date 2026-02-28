from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel

from app.core.billing.ledger import LedgerStore, utc_month_key
from app.core.billing.tenant_budget import get_tenant_monthly_budget


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_WORKSPACE_ROOT = PROJECT_ROOT / "workspace"


router = APIRouter(prefix="/api/v2/billing", tags=["billing"])


def _tenant(x_tenant: Optional[str]) -> str:
    return x_tenant or "default"


def _billing_workspace_dir(workspace_dir: Optional[str]) -> Path:
    """
    Ledger/Budgets live at: <workspace_root>/.copilot/billing/*
    We accept either:
      - a job workspace_dir (<workspace_root>/<job>)
      - a workspace_root itself
    And normalize by picking a sentinel child so ledger/budget code uses parent.
    """
    if workspace_dir:
        p = Path(workspace_dir)
        if p.name == "workspace":
            root = p
        else:
            root = p.parent if p.name else p
    else:
        root = DEFAULT_WORKSPACE_ROOT
    return root / "__billing__"


class BillingSummaryResponse(BaseModel):
    tenant: str
    month: str
    limit_usd: float
    spent_estimated_usd: float
    spent_actual_usd: float
    ai_spent_actual_usd: float
    non_ai_spent_actual_usd: float
    remaining_estimated_usd: float
    utilization_estimated: float
    projected_spent_usd: float
    projected_utilization: float
    budget_status: str
    entries_count: int


@router.get("/summary", response_model=BillingSummaryResponse)
def billing_summary(
    month: Optional[str] = Query(default=None),
    workspace_dir: Optional[str] = Query(default=None),
    x_tenant: Optional[str] = Header(default=None, alias="X-Tenant"),
) -> Dict[str, Any]:
    tenant = _tenant(x_tenant)
    m = month or utc_month_key()

    ws = _billing_workspace_dir(workspace_dir)
    ledger = LedgerStore(workspace_dir=ws)

    spent_est = float(ledger.spent_usd(tenant=tenant, month=m))
    spent_act = float(ledger.spent_actual_usd(tenant=tenant, month=m))
    breakdown = ledger.spent_actual_breakdown_usd(tenant=tenant, month=m)

    bud = get_tenant_monthly_budget(workspace_dir=ws, tenant=tenant, month=m)
    limit_usd = float(bud.limit_usd)

    remaining = max(0.0, limit_usd - spent_est)
    util = 0.0 if limit_usd <= 0 else min(1.0, spent_est / limit_usd)

    projected_spent = spent_est
    projected_util = 0.0 if limit_usd <= 0 else min(1.0, projected_spent / limit_usd)
    if limit_usd > 0 and projected_spent >= limit_usd:
        budget_status = "exceeded"
    elif projected_util >= 0.80:
        budget_status = "warning"
    else:
        budget_status = "ok"

    return {
        "tenant": tenant,
        "month": m,
        "limit_usd": limit_usd,
        "spent_estimated_usd": spent_est,
        "spent_actual_usd": spent_act,
        "ai_spent_actual_usd": float(breakdown.get("ai_actual_usd", 0.0)),
        "non_ai_spent_actual_usd": float(breakdown.get("non_ai_actual_usd", 0.0)),
        "remaining_estimated_usd": remaining,
        "utilization_estimated": util,
        "projected_spent_usd": projected_spent,
        "projected_utilization": projected_util,
        "budget_status": budget_status,
        "entries_count": ledger.entries_count(tenant=tenant, month=m),
    }
