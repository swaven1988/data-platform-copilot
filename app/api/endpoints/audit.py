from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.core.audit.architecture_audit import run_architecture_audit
from app.core.auth.rbac_ext import require_roles

router = APIRouter(tags=["audit"])


@router.get("/audit/architecture")
def audit_architecture() -> Dict[str, Any]:
    project_root = Path(__file__).resolve().parents[3]
    return run_architecture_audit(project_root)


@router.get(
    "/api/v1/audit/log",
    dependencies=[Depends(require_roles("viewer", "admin"))],
)
def audit_log() -> Dict[str, Any]:
    audit_path = Path(os.getenv("COPILOT_AUDIT_PATH") or ".copilot/audit.log")
    if not audit_path.exists():
        return {"entries": []}

    entries: list[Dict[str, Any]] = []
    with audit_path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                row = json.loads(s)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                entries.append(row)
    return {"entries": entries}
