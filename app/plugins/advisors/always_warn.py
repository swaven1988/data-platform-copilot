from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.core.build_plan.models import BuildPlan
from app.core.plugins.contracts import AdvisorFinding

@dataclass
class AlwaysWarnAdvisor:
    name: str = "always_warn"
    version: str = "0.1.0"
    enabled_by_default: bool = True

    def advise(self, plan: BuildPlan):
        findings: List[AdvisorFinding] = [
            AdvisorFinding(
                code="advisor.always_warn",
                severity="warn",
                message="This is a smoke-test warning from always_warn advisor.",
                data={"job_name": plan.job_name},
            )
        ]
        return plan, findings

ADVISOR = AlwaysWarnAdvisor()
