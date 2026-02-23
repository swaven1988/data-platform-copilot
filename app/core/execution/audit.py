# app/core/execution/audit.py
from __future__ import annotations

from typing import Any, Dict, Optional


def audit_context(*, tenant: str, request_id: Optional[str]) -> Dict[str, Any]:
    return {
        "tenant": tenant,
        "request_id": request_id,
    }   