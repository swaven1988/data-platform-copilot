from typing import Dict
from .intelligence_engine import IntelligenceEngine
from .advisor_hint_injector import AdvisorHintInjector


class IntelligenceFacade:

    @staticmethod
    def analyze_and_inject(build_plan: Dict, base_ref: str = "upstream/main") -> Dict:
        repo_dir = None
        if isinstance(build_plan, dict):
            repo_dir = build_plan.get("workspace_dir") or build_plan.get("repo_dir")

        out = IntelligenceEngine.analyze(base_ref=base_ref, repo_dir=repo_dir)
        insight = out.get("insight_report", {})
        return AdvisorHintInjector.inject(build_plan, insight)
