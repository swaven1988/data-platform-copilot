from pathlib import Path
import json
from .intelligence_models import IntelligenceReport, ClusterProfile
from .runtime_model import estimate_runtime_minutes
from .cost_model import estimate_cost_usd
from .risk_model import compute_risk
from .optimizer import suggest_optimizations
from .plan_engine import PlanEngine


class IntelligenceEngine:

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.plan_engine = PlanEngine(workspace_root)

    def _intelligence_dir(self, job_name: str) -> Path:
        path = self.workspace_root / job_name / ".copilot" / "intelligence"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def analyze(
        self,
        job_name: str,
        plan_hash: str,
        cluster_profile: ClusterProfile
    ):

        plan = self.plan_engine.load_plan(job_name, plan_hash)
        if not plan:
            raise ValueError("Invalid plan hash")

        num_stages = len(plan.physical_stages)
        shuffle_stages = sum(1 for s in plan.physical_stages if s.shuffle_boundary)
        base_parallelism = 200

        runtime = estimate_runtime_minutes(
            num_stages,
            shuffle_stages,
            base_parallelism
        )

        cost = estimate_cost_usd(
            runtime,
            cluster_profile.executor_instances,
            cluster_profile.instance_hourly_rate
        )

        risk = compute_risk(
            shuffle_stages,
            cluster_profile.executor_memory_gb,
            runtime
        )

        suggestions = suggest_optimizations(
            shuffle_stages,
            cluster_profile.executor_memory_gb
        )

        report = IntelligenceReport(
            plan_hash=plan_hash,
            runtime_estimate_minutes=runtime,
            cost_estimate_usd=cost,
            failure_probability=risk["failure_probability"],
            risk_score=risk["risk_score"],
            risk_level=risk["risk_level"],
            confidence_score=risk["confidence_score"],
            primary_risk_factors=risk["factors"],
            optimization_suggestions=suggestions
        )

        intelligence_hash = report.deterministic_hash()
        path = self._intelligence_dir(job_name) / f"{intelligence_hash}.json"

        if not path.exists():
            path.write_text(
                json.dumps(
                    report.model_dump(),
                    sort_keys=True,
                    indent=2
                )
            )

        return {
            "intelligence_hash": intelligence_hash,
            "stored": True,
            "path": str(path)
        }