from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter

from app.core.audit.architecture_audit import run_architecture_audit

router = APIRouter(tags=["audit"])


@router.get("/audit/architecture")
def audit_architecture() -> Dict[str, Any]:
    project_root = Path(__file__).resolve().parents[3]
    return run_architecture_audit(project_root)
