from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .models import PolicyResult, PolicyStatus


PolicyFn = Callable[[Dict[str, Any]], Optional[PolicyResult]]


class PolicyEngine:
    def __init__(self, policies: List[PolicyFn]):
        self._policies = policies

    def evaluate(self, context: Dict[str, Any]) -> List[PolicyResult]:
        results: List[PolicyResult] = []
        for fn in self._policies:
            r = fn(context)
            if r is not None:
                results.append(r)
        return results

    @staticmethod
    def is_blocking(results: List[PolicyResult]) -> bool:
        return any(r.status == PolicyStatus.FAIL for r in results)
