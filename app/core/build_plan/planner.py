from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.build_plan.models import BuildPlan, PlanStep


def make_build_plan(
    *,
    job_name: str,
    spec_hash: str,
    baseline_ref: Optional[str],
    expected_files: List[str],
    plugin_fingerprint: str = "core",
    advisor_fingerprint: str = "core",
    metadata: Optional[Dict[str, Any]] = None,
) -> BuildPlan:
    md = dict(metadata or {})
    md.setdefault("advisor_fingerprint", advisor_fingerprint)
    # md.setdefault("plugin_fingerprint", plugin_fingerprint)

    steps = [
        PlanStep(
            step_id="acquire_baseline",
            step_type="AcquireBaseline",
            depends_on=[],
            inputs={"baseline_ref": baseline_ref},
            outputs={},
            cache_key=f"AcquireBaseline:{baseline_ref or ''}",
        ),
        PlanStep(
            step_id="generate_artifacts",
            step_type="GenerateArtifacts",
            depends_on=["acquire_baseline"],
            inputs={},
            outputs={},
            cache_key=f"GenerateArtifacts:{spec_hash}",
        ),
        PlanStep(
            step_id="materialize_workspace",
            step_type="MaterializeWorkspace",
            depends_on=["generate_artifacts"],
            inputs={},
            outputs={},
            cache_key=f"MaterializeWorkspace:{spec_hash}",
        ),
        PlanStep(
            step_id="finalize_baseline",
            step_type="FinalizeBaseline",
            depends_on=["materialize_workspace"],
            inputs={},
            outputs={},
            cache_key=f"FinalizeBaseline:{baseline_ref or ''}",
        ),
    ]

    return BuildPlan(
        plan_version="v1",
        job_name=job_name,
        spec_hash=spec_hash,
        baseline_ref=baseline_ref,
        plugin_fingerprint=plugin_fingerprint,
        expected_files=expected_files,
        metadata=md,
        steps=steps,
    )
