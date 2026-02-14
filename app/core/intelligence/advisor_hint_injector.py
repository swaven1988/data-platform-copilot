from typing import Dict, List


class AdvisorHintInjector:

    @staticmethod
    def inject(build_plan: Dict, insight_report: Dict) -> Dict:
        """
        Non-breaking: attaches hints under build_plan["intelligence"].
        """
        bp = dict(build_plan) if isinstance(build_plan, dict) else {"build_plan": build_plan}

        bp["intelligence"] = {
            "risk_score": insight_report.get("risk_score", 0),
            "areas_touched": insight_report.get("impact", {}).get("areas_touched", []),
            "recommendations": insight_report.get("recommendations", {}),
            "hints": insight_report.get("hints", {}),
        }
        return bp
