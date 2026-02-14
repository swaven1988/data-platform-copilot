from typing import Dict
from .diff_analyzer import DiffContext


class ContextExtractor:

    @staticmethod
    def extract(diff: DiffContext) -> Dict:
        hints = {
            "affects_dag": any("dag" in f for f in diff.changed_files),
            "affects_spark": any("spark" in f for f in diff.changed_files),
            "affects_policy": any("policy" in f for f in diff.changed_files),
            "affects_api": any("app/api" in f for f in diff.changed_files),
        }
        return hints
