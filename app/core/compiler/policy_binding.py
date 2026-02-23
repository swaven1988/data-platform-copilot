from pathlib import Path
from typing import Dict
import json
from .policy_models import IntelligenceThresholds, PolicyEvaluation
from .contract_engine import ContractEngine
from .plan_engine import PlanEngine


class PolicyBinding:

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.contract_engine = ContractEngine(workspace_root)
        self.plan_engine = PlanEngine(workspace_root)

    def _policy_dir(self, job_name: str) -> Path:
        path = self.workspace_root / job_name / ".copilot" / "policy"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _load_intelligence_report(self, job_name: str, intelligence_hash: str) -> Dict:
        p = (
            self.workspace_root
            / job_name
            / ".copilot"
            / "intelligence"
            / f"{intelligence_hash}.json"
        )
        if not p.exists():
            raise ValueError("Invalid intelligence hash")
        return json.loads(p.read_text())

    def evaluate(
        self,
        *,
        job_name: str,
        contract_hash: str,
        plan_hash: str,
        intelligence_hash: str,
        thresholds: IntelligenceThresholds
    ) -> Dict:

        contract = self.contract_engine.load_contract(job_name, contract_hash)
        if not contract:
            raise ValueError("Invalid contract hash")

        plan = self.plan_engine.load_plan(job_name, plan_hash)
        if not plan:
            raise ValueError("Invalid plan hash")

        report = self._load_intelligence_report(job_name, intelligence_hash)

        reasons = []

        cost = float(report.get("cost_estimate_usd", 0.0))
        risk_score = int(report.get("risk_score", 0))
        failure_prob = float(report.get("failure_probability", 0.0))
        confidence = float(report.get("confidence_score", 0.0))

        if cost > thresholds.max_cost_usd:
            reasons.append(f"cost_estimate_usd {cost} exceeds max_cost_usd {thresholds.max_cost_usd}")

        if risk_score > thresholds.max_risk_score:
            reasons.append(f"risk_score {risk_score} exceeds max_risk_score {thresholds.max_risk_score}")

        if failure_prob > thresholds.max_failure_probability:
            reasons.append(
                f"failure_probability {failure_prob} exceeds max_failure_probability {thresholds.max_failure_probability}"
            )

        if confidence < thresholds.min_confidence_score:
            reasons.append(
                f"confidence_score {confidence} below min_confidence_score {thresholds.min_confidence_score}"
            )

        # Decision logic (deterministic)
        # strict: any violation => BLOCK
        # balanced: cost/risk/failure => BLOCK, low confidence => WARN
        # permissive: violations => WARN unless extreme
        decision = "ALLOW"

        if thresholds.mode == "strict":
            if reasons:
                decision = "BLOCK"

        elif thresholds.mode == "balanced":
            hard = []
            soft = []
            for r in reasons:
                if r.startswith("confidence_score"):
                    soft.append(r)
                else:
                    hard.append(r)
            if hard:
                decision = "BLOCK"
                reasons = hard + soft
            elif soft:
                decision = "WARN"
                reasons = soft

        elif thresholds.mode == "permissive":
            if reasons:
                decision = "WARN"
            # extreme guardrails
            if risk_score >= 90 or failure_prob >= 0.6:
                decision = "BLOCK"

        policy_profile = getattr(contract, "policy_profile", "default")

        eval_obj = PolicyEvaluation(
            job_name=job_name,
            contract_hash=contract_hash,
            plan_hash=plan_hash,
            intelligence_hash=intelligence_hash,
            policy_profile=policy_profile,
            decision=decision,
            reasons=reasons
        )

        policy_eval_hash = eval_obj.deterministic_hash()
        out_path = self._policy_dir(job_name) / f"{policy_eval_hash}.json"

        if not out_path.exists():
            out_path.write_text(
                json.dumps(
                    eval_obj.model_dump(),
                    sort_keys=True,
                    indent=2
                )
            )

        return {
            "policy_eval_hash": policy_eval_hash,
            "decision": decision,
            "reasons": reasons,
            "stored": True,
            "path": str(out_path)
        }

    def load(self, job_name: str, policy_eval_hash: str) -> Dict | None:
        p = self._policy_dir(job_name) / f"{policy_eval_hash}.json"
        if not p.exists():
            return None
        return json.loads(p.read_text())