from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# Keep consistent with app.core.auth.rbac.ROLE_ORDER
DEFAULT_REQUIRED_ROLE = "admin"


@dataclass(frozen=True)
class PolicyRule:
    method: str  # "GET", "POST", "*" etc.
    pattern: re.Pattern
    required_role: str


# Ordered: first match wins
RULES: list[PolicyRule] = [

    # -----------------------------
    # Liveness / Readiness (no admin required)
    # -----------------------------
    PolicyRule(
        method="GET",
        pattern=re.compile(r"^/api/v1/health/live$"),
        required_role="viewer",
    ),
    PolicyRule(
        method="GET",
        pattern=re.compile(r"^/api/v1/health/ready$"),
        required_role="viewer",
    ),

    # -----------------------------
    # Viewer-allowed tenant health
    # -----------------------------
    PolicyRule(
        method="GET",
        pattern=re.compile(r"^/api/v1/tenants/[^/]+/health$"),
        required_role="viewer",
    ),

    # -----------------------------
    # Modeling (Stage 23) — explicit RBAC
    # viewer: list/get/previews
    # admin:  register
    # -----------------------------
    PolicyRule(
        method="POST",
        pattern=re.compile(r"^/api/v[12]/modeling/register$"),
        required_role="admin",
    ),
    PolicyRule(
        method="*",
        pattern=re.compile(r"^/api/v[12]/modeling/"),
        required_role="viewer",
    ),

    # -----------------------------
    # Default for all versioned surfaces
    # -----------------------------
    PolicyRule(
        method="*",
        pattern=re.compile(r"^/api/v[12]/"),
        required_role=DEFAULT_REQUIRED_ROLE,
    ),
]


def required_role_for(method: str, path: str) -> Optional[str]:
    """
    Returns required role for this request, or None if policy does not apply.
    """
    m = (method or "GET").upper()
    for rule in RULES:
        if rule.method != "*" and rule.method != m:
            continue
        if rule.pattern.match(path):
            return rule.required_role
    return None
