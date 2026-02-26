from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class PolicyStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class PolicyResult:
    status: PolicyStatus
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
