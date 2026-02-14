from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.build_plan.events import BuildEvent
from app.core.build_plan.models import BuildPlan
from app.core.git_ops.repo_manager import read_baseline
from app.core.build_registry import BuildRegistry


@dataclass
class BuildResult:
    job_name: str
    spec_hash: str
    plan_id: str
    baseline_commit: Optional[str]
    files: List[str]
    skipped: bool
    events: List[Dict[str, Any]]
    advisor_findings: List[Dict[str, Any]]


class PlanRunner:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root

    def run(
        self,
        *,
        plan: BuildPlan,
        registry: BuildRegistry,
        workspace_job_dir: Path,
        generated_files: Dict[str, str],
        baseline_commit: Optional[str],
        skipped: bool,
        advisor_findings: Optional[List[Dict[str, Any]]] = None,
        confidence: Optional[float] = None,
    ) -> BuildResult:
        plan_id = plan.compute_plan_id()

        ev: List[BuildEvent] = []
        ev.append(BuildEvent.mk("PlanCreated", plan.job_name, plan.spec_hash, plan_id=plan_id, payload={
            "plan_version": plan.plan_version,
            "step_count": len(plan.steps),
            "plugin_fingerprint": plan.plugin_fingerprint,
        }))

        # NOTE: We keep execution in build_v2_impl for now.
        # This runner is mainly to normalize event emission + registry registration.

        if skipped:
            ev.append(BuildEvent.mk("BuildSkipped", plan.job_name, plan.spec_hash, plan_id=plan_id, payload={
                "reason": "spec_hash_unchanged",
            }))
            registry.register_build(
                spec_hash=plan.spec_hash,
                baseline_commit=read_baseline(workspace_job_dir),
                confidence=None,
                plan_id=plan_id,
                plugin_fingerprint=plan.plugin_fingerprint,
            )
            return BuildResult(
                job_name=plan.job_name,
                spec_hash=plan.spec_hash,
                plan_id=plan_id,
                baseline_commit=read_baseline(workspace_job_dir),
                files=list(generated_files.keys()),
                skipped=True,
                events=[
                    (e if isinstance(e, dict) else vars(e))
                    for e in ev
                ],
                advisor_findings=advisor_findings or [],
            )

        ev.append(BuildEvent.mk("ArtifactsWritten", plan.job_name, plan.spec_hash, plan_id=plan_id, payload={
            "file_count": len(generated_files),
            "files": list(generated_files.keys()),
        }))
        ev.append(BuildEvent.mk("BuildCompleted", plan.job_name, plan.spec_hash, plan_id=plan_id, payload={
            "baseline_commit": baseline_commit,
        }))

        registry.register_build(
            spec_hash=plan.spec_hash,
            baseline_commit=baseline_commit,
            confidence=None,
            plan_id=plan_id,
            plugin_fingerprint=plan.plugin_fingerprint,
        )

        return BuildResult(
            job_name=plan.job_name,
            spec_hash=plan.spec_hash,
            plan_id=plan_id,
            baseline_commit=baseline_commit,
            files=list(generated_files.keys()),
            skipped=False,
            events=[
                (e if isinstance(e, dict) else vars(e))
                for e in ev
            ],
            advisor_findings=advisor_findings or [],
        )
