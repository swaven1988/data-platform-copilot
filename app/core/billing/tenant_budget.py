from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class TenantMonthlyBudget:
    tenant: str
    month: str  # YYYY-MM
    limit_usd: float


def _billing_root_from_workspace(workspace_dir: Path) -> Path:
    # workspace_dir points to workspace/<job>
    # keep tenant budgets shared at workspace root (workspace/.copilot/billing)
    root = workspace_dir.parent / ".copilot" / "billing"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _budgets_path(workspace_dir: Path) -> Path:
    return _billing_root_from_workspace(workspace_dir) / "budgets.json"


def load_budgets_file(workspace_dir: Path) -> Dict[str, Any]:
    p = _budgets_path(workspace_dir)
    if not p.exists():
        return {
            "kind": "tenant_budgets",
            "defaults": {"limit_usd": 250.0},
            "tenants": {},
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {
            "kind": "tenant_budgets",
            "defaults": {"limit_usd": 250.0},
            "tenants": {},
        }


def get_tenant_monthly_budget(*, workspace_dir: Path, tenant: str, month: str) -> TenantMonthlyBudget:
    obj = load_budgets_file(workspace_dir)
    defaults = obj.get("defaults", {}) if isinstance(obj, dict) else {}
    tenants = obj.get("tenants", {}) if isinstance(obj, dict) else {}

    limit = None
    if isinstance(tenants, dict):
        t = tenants.get(tenant, None)
        if isinstance(t, dict):
            limit = t.get("limit_usd", None)

    if not isinstance(limit, (int, float)):
        limit = defaults.get("limit_usd", 250.0) if isinstance(defaults, dict) else 250.0

    return TenantMonthlyBudget(tenant=tenant, month=month, limit_usd=float(limit))


def set_tenant_limit_usd(*, workspace_dir: Path, tenant: str, limit_usd: float) -> None:
    obj = load_budgets_file(workspace_dir)
    if not isinstance(obj, dict):
        obj = {"kind": "tenant_budgets", "defaults": {"limit_usd": 250.0}, "tenants": {}}

    obj.setdefault("kind", "tenant_budgets")
    obj.setdefault("defaults", {"limit_usd": 250.0})
    obj.setdefault("tenants", {})

    if not isinstance(obj["tenants"], dict):
        obj["tenants"] = {}

    obj["tenants"][tenant] = {"limit_usd": float(limit_usd)}

    p = _budgets_path(workspace_dir)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")