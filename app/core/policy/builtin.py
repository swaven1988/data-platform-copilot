from __future__ import annotations

from typing import Any, Dict, Optional

from .models import PolicyResult, PolicyStatus


def policy_require_owner_email(ctx: Dict[str, Any]) -> Optional[PolicyResult]:
    spec = (ctx.get("spec") or {})
    owner = spec.get("owner_email") or spec.get("owneremail") or spec.get("owner")
    if not owner:
        return PolicyResult(
            status=PolicyStatus.WARN,
            code="OWNER_MISSING",
            message="owner_email is missing in spec (warn only for now).",
            details={"field": "owner_email"},
        )
    return None


def policy_require_source_target(ctx: Dict[str, Any]) -> Optional[PolicyResult]:
    spec = (ctx.get("spec") or {})
    src = spec.get("source_table")
    tgt = spec.get("target_table")
    if not src or "." not in str(src):
        return PolicyResult(
            status=PolicyStatus.FAIL,
            code="SOURCE_TABLE_INVALID",
            message="Invalid source_table format. Expected <db>.<table>.",
            details={"source_table": src},
        )
    if not tgt or "." not in str(tgt):
        return PolicyResult(
            status=PolicyStatus.FAIL,
            code="TARGET_TABLE_INVALID",
            message="Invalid target_table format. Expected <db>.<table>.",
            details={"target_table": tgt},
        )
    return None
