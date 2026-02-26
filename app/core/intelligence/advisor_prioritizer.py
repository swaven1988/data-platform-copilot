from typing import List, Dict


class AdvisorPrioritizer:

    @staticmethod
    def prioritize(resolved_advisors: List[Dict], hints: Dict) -> List[Dict]:
        """
        resolved_advisors: [
            {"name": "...", "phase": "...", "priority": int, ...}
        ]
        """

        def weight(advisor: Dict) -> int:
            score = advisor.get("priority", 0)

            name = advisor.get("name", "").lower()

            if hints.get("affects_policy") and "policy" in name:
                score += 50
            if hints.get("affects_dag") and "dag" in name:
                score += 30
            if hints.get("affects_spark") and "spark" in name:
                score += 30
            if hints.get("affects_api") and "api" in name:
                score += 20

            return score

        return sorted(
            resolved_advisors,
            key=lambda a: (-weight(a), a.get("name", ""))
        )
