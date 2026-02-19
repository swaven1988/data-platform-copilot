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
    # Viewer-allowed tenant health (Stage 15: explicit policy)
    PolicyRule(
        method="GET",
        pattern=re.compile(r"^/api/v1/tenants/[^/]+/health$"),
        required_role="viewer",
    ),
    # Default for all versioned surfaces
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
