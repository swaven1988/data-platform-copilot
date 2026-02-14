from typing import Dict


class RiskEngine:

    @staticmethod
    def score(hints: Dict) -> int:
        score = 0
        if hints.get("affects_policy"):
            score += 3
        if hints.get("affects_dag"):
            score += 2
        if hints.get("affects_spark"):
            score += 2
        if hints.get("affects_api"):
            score += 1
        return score
