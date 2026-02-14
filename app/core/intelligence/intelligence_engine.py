from typing import Dict
from .diff_analyzer import DiffAnalyzer
from .context_extractor import ContextExtractor
from .risk_engine import RiskEngine
from .insight_report import InsightReport


class IntelligenceEngine:

    @staticmethod
    def analyze(base_ref: str = "upstream/main", repo_dir: str | None = None) -> Dict:
        diff = DiffAnalyzer.get_changed_files(base_ref=base_ref, repo_dir=repo_dir)
        hints = ContextExtractor.extract(diff)
        risk_score = RiskEngine.score(hints)

        analysis = {
            "changed_files": diff.changed_files,
            "hints": hints,
            "risk_score": risk_score,
            "git_error": diff.git_error,
        }

        return {
            "analysis": analysis,
            "insight_report": InsightReport.build(analysis),
        }
