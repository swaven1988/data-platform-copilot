from typing import Dict
from .change_impact import ChangeImpactModel


class InsightReport:

    @staticmethod
    def build(analysis: Dict) -> Dict:
        changed_files = analysis.get("changed_files", [])
        impact = ChangeImpactModel.assess(changed_files)

        return {
            "changed_files": changed_files,
            "hints": analysis.get("hints", {}),
            "risk_score": analysis.get("risk_score", 0),
            "impact": impact,
            "recommendations": InsightReport._recommend(analysis, impact),
        }

    @staticmethod
    def _recommend(analysis: Dict, impact: Dict) -> Dict:
        rec = {"tests": [], "advisors": [], "notes": []}
        areas = impact.get("areas_touched", [])
        hints = analysis.get("hints", {})

        if "policy" in areas:
            rec["tests"].append("policy layer unit tests + build/v2 integration tests")
            rec["advisors"].append("run policy-gated advisors first")
            rec["notes"].append("validate FAIL blocks build and WARN continues")

        if "cache" in areas:
            rec["tests"].append("cache key + head invalidation tests")
            rec["notes"].append("verify hit/miss counters remain deterministic")

        if hints.get("affects_api"):
            rec["tests"].append("endpoint contract tests (/build/v2, /cache/stats, /plugins/resolve)")
            rec["notes"].append("ensure policy_results always present in responses")

        if hints.get("affects_dag"):
            rec["tests"].append("advisor DAG topo ordering + circular detection tests")

        return rec
