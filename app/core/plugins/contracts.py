from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol


@dataclass
class AdvisorFinding:
    code: str
    severity: str  # "info" | "warn" | "error"
    message: str
    data: Dict[str, Any]


class AdvisorPlugin(Protocol):
    """
    Minimal stable plugin contract for advisors.
    Plugin modules must export: ADVISOR (instance implementing this protocol)
    """
    name: str
    version: str
    enabled_by_default: bool

    def advise(self, plan: Any) -> tuple[Any, List[AdvisorFinding]]:
        ...
