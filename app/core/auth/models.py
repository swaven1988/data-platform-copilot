from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: List[str]

    def has_any_role(self, allowed: List[str]) -> bool:
        s = set(self.roles or [])
        return any(r in s for r in allowed)
