from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol


@dataclass(frozen=True)
class AdvisorFinding:
    plugin: str
    level: str   # "info" | "warn" | "error"
    code: str
    message: str
    data: Dict[str, Any] | None = None


class AdvisorPlugin(Protocol):
    name: str

    def run(self, *, context: Dict[str, Any], options: Dict[str, Any]) -> List[AdvisorFinding]:
        ...
