from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from app.core.build_plan.models import BuildPlan
from app.core.plugins.contracts import AdvisorFinding


@dataclass
class BasicChecksAdvisor:
    name: str = "basic_checks"
    version: str = "0.1.0"
    enabled_by_default: bool = True
    applies_to = ["build"]

    def advise(
        self,
        plan: BuildPlan,
        options: Dict[str, Any] | None = None,
    ) -> Tuple[BuildPlan, List[AdvisorFinding]]:

        options = options or {}
        findings: List[AdvisorFinding] = []

        if options.get("strict"):
            findings.append(
                AdvisorFinding(
                    code="basic.strict_mode",
                    severity="warn",
                    message="Strict mode is enabled",
                    data={"job_name": plan.job_name},
                )
            )

        if not plan.expected_files:
            findings.append(
                AdvisorFinding(
                    code="plan.no_expected_files",
                    severity="warn",
                    message="Plan has no expected_files. This usually means a skipped build or misconfigured generator.",
                    data={"job_name": plan.job_name},
                )
            )

        if not plan.baseline_ref:
            findings.append(
                AdvisorFinding(
                    code="plan.no_baseline",
                    severity="warn",
                    message="Plan baseline_ref is missing. Drift detection may be degraded.",
                    data={"job_name": plan.job_name},
                )
            )

        return plan, findings

ADVISOR = BasicChecksAdvisor()

