from pathlib import Path
from typing import Dict
import json
from .plan_models import (
    CompilerPlan,
    LogicalNode,
    PhysicalStage,
    PlanMetadata
)
from .contract_engine import ContractEngine


class PlanEngine:

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.contract_engine = ContractEngine(workspace_root)

    def _plan_dir(self, job_name: str) -> Path:
        path = self.workspace_root / job_name / ".copilot" / "plans"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def generate_plan(
        self,
        job_name: str,
        contract_hash: str,
        plugin_fingerprint: str,
        policy_profile: str
    ) -> Dict:

        contract = self.contract_engine.load_contract(job_name, contract_hash)
        if not contract:
            raise ValueError("Invalid contract hash")

        logical_nodes = []
        physical_stages = []

        # Logical DAG from transformations
        for idx, t in enumerate(contract.transformations):
            logical_nodes.append(
                LogicalNode(
                    node_id=f"node_{idx}",
                    node_type=t.type,
                    config=t.config
                )
            )

        # Physical stages (simple deterministic mapping)
        for idx, node in enumerate(logical_nodes):
            physical_stages.append(
                PhysicalStage(
                    stage_id=f"stage_{idx}",
                    depends_on=[f"stage_{idx-1}"] if idx > 0 else [],
                    shuffle_boundary=("join" in node.node_type.lower()),
                    estimated_parallelism=200
                )
            )

        metadata = PlanMetadata(
            contract_hash=contract_hash,
            plugin_fingerprint=plugin_fingerprint,
            policy_profile=policy_profile
        )

        plan = CompilerPlan(
            job_name=job_name,
            metadata=metadata,
            logical_dag=logical_nodes,
            physical_stages=physical_stages
        )

        plan_hash = plan.deterministic_hash()
        plan_path = self._plan_dir(job_name) / f"{plan_hash}.json"

        if not plan_path.exists():
            plan_path.write_text(
                json.dumps(
                    plan.model_dump(),
                    sort_keys=True,
                    indent=2
                )
            )

        return {
            "plan_hash": plan_hash,
            "stored": True,
            "path": str(plan_path)
        }

    def load_plan(self, job_name: str, plan_hash: str):
        plan_path = (
            self.workspace_root
            / job_name
            / ".copilot"
            / "plans"
            / f"{plan_hash}.json"
        )

        if not plan_path.exists():
            return None

        data = json.loads(plan_path.read_text())
        return CompilerPlan(**data)