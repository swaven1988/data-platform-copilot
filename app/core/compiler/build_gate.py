from pathlib import Path
from typing import Dict
import json
from .contract_engine import ContractEngine
from .plan_engine import PlanEngine
from .policy_binding import PolicyBinding


class BuildGate:

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.contract_engine = ContractEngine(workspace_root)
        self.plan_engine = PlanEngine(workspace_root)
        self.policy_binding = PolicyBinding(workspace_root)

    def _intelligence_path(self, job_name: str, intelligence_hash: str) -> Path:
        return (
            self.workspace_root
            / job_name
            / ".copilot"
            / "intelligence"
            / f"{intelligence_hash}.json"
        )

    def validate_inputs(
        self,
        *,
        job_name: str,
        contract_hash: str,
        plan_hash: str,
        intelligence_hash: str,
        policy_eval_hash: str
    ) -> Dict:

        contract = self.contract_engine.load_contract(job_name, contract_hash)
        if not contract:
            raise ValueError("Invalid contract hash")

        plan = self.plan_engine.load_plan(job_name, plan_hash)
        if not plan:
            raise ValueError("Invalid plan hash")

        ip = self._intelligence_path(job_name, intelligence_hash)
        if not ip.exists():
            raise ValueError("Invalid intelligence hash")

        policy_eval = self.policy_binding.load(job_name, policy_eval_hash)
        if not policy_eval:
            raise ValueError("Invalid policy evaluation hash")

        # Cross-link consistency checks
        if policy_eval.get("contract_hash") != contract_hash:
            raise ValueError("Policy evaluation does not match contract hash")

        if policy_eval.get("plan_hash") != plan_hash:
            raise ValueError("Policy evaluation does not match plan hash")

        if policy_eval.get("intelligence_hash") != intelligence_hash:
            raise ValueError("Policy evaluation does not match intelligence hash")

        decision = policy_eval.get("decision")
        if decision == "BLOCK":
            raise PermissionError(
                "Build blocked by policy: " + "; ".join(policy_eval.get("reasons", []))
            )

        return {
            "decision": decision,
            "reasons": policy_eval.get("reasons", []),
            "policy_profile": policy_eval.get("policy_profile", "default"),
        }

    def record_lineage(
        self,
        *,
        job_name: str,
        contract_hash: str,
        plan_hash: str,
        intelligence_hash: str,
        policy_eval_hash: str,
        build_id: str
    ) -> Dict:

        out_dir = (
            self.workspace_root
            / job_name
            / ".copilot"
            / "build_lineage"
        )
        out_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "build_id": build_id,
            "contract_hash": contract_hash,
            "plan_hash": plan_hash,
            "intelligence_hash": intelligence_hash,
            "policy_eval_hash": policy_eval_hash,
        }

        out_path = out_dir / f"{build_id}.json"
        if not out_path.exists():
            out_path.write_text(json.dumps(payload, sort_keys=True, indent=2))

        return {"stored": True, "path": str(out_path)}