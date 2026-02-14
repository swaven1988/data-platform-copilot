from dataclasses import dataclass
from typing import List, Dict


@dataclass
class ImpactItem:
    area: str
    severity: str
    reason: str
    files: List[str]


class ChangeImpactModel:

    AREA_RULES = {
        "api": ["app/api/"],
        "policy": ["app/core/policy/"],
        "cache": ["app/plugins/advisors/_internal/cache.py"],
        "advisors": ["app/plugins/"],
        "sync": ["app/core/sync/", "app/api/endpoints/sync.py"],
        "repo": ["app/core/git_ops/", "app/api/endpoints/repo.py"],
        "generators": ["app/core/generators/", "templates/"],
        "ui": ["ui/"],
    }

    @staticmethod
    def _match_area(files: List[str]) -> Dict[str, List[str]]:
        hits: Dict[str, List[str]] = {k: [] for k in ChangeImpactModel.AREA_RULES}
        for f in files:
            for area, patterns in ChangeImpactModel.AREA_RULES.items():
                if any(p in f for p in patterns):
                    hits[area].append(f)
        return {k: v for k, v in hits.items() if v}

    @staticmethod
    def assess(changed_files: List[str]) -> Dict:
        areas = ChangeImpactModel._match_area(changed_files)
        impacts: List[ImpactItem] = []

        for area, files in areas.items():
            if area in ("policy", "cache"):
                impacts.append(ImpactItem(area, "high", f"{area} changes can alter deterministic execution", files))
            elif area in ("api", "sync", "repo"):
                impacts.append(ImpactItem(area, "medium", f"{area} changes can affect external API contract/behavior", files))
            else:
                impacts.append(ImpactItem(area, "low", f"{area} changes are typically localized", files))

        return {
            "impacts": [i.__dict__ for i in impacts],
            "areas_touched": list(areas.keys()),
        }
