from typing import Dict, List
from .intelligence_engine import IntelligenceEngine
from .advisor_prioritizer import AdvisorPrioritizer
from .hint_mapper import HintMapper


class IntelligencePipeline:

    @staticmethod
    def run(resolved_advisors: List[Dict], base_ref: str = "upstream/main") -> Dict:
        analysis = IntelligenceEngine.analyze(base_ref)
        hints = analysis["hints"]

        prioritized = AdvisorPrioritizer.prioritize(resolved_advisors, hints)
        tags = HintMapper.map_to_advisor_tags(hints)

        return {
            "analysis": analysis,
            "prioritized_advisors": prioritized,
            "advisor_tags": tags,
        }
