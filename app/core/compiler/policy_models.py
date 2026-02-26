from pydantic import BaseModel, Field
from typing import List, Literal
from hashlib import sha256
import json


Decision = Literal["ALLOW", "WARN", "BLOCK"]


class IntelligenceThresholds(BaseModel):
    max_cost_usd: float = 999999.0
    max_risk_score: int = 100
    max_failure_probability: float = 1.0
    min_confidence_score: float = 0.0
    mode: Literal["strict", "balanced", "permissive"] = "balanced"


class PolicyEvaluation(BaseModel):
    job_name: str
    contract_hash: str
    plan_hash: str
    intelligence_hash: str
    policy_profile: str
    decision: Decision
    reasons: List[str] = Field(default_factory=list)

    def deterministic_hash(self) -> str:
        raw = json.dumps(
            self.model_dump(),
            sort_keys=True,
            separators=(",", ":")
        )
        return sha256(raw.encode()).hexdigest()