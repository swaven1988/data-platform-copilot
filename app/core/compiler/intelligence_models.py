from pydantic import BaseModel, Field
from typing import List, Dict
from hashlib import sha256
import json


class ClusterProfile(BaseModel):
    executor_instances: int
    executor_cores: int
    executor_memory_gb: int
    instance_hourly_rate: float  # injected vendor pricing


class IntelligenceReport(BaseModel):
    plan_hash: str
    runtime_estimate_minutes: float
    cost_estimate_usd: float
    failure_probability: float
    risk_score: int
    risk_level: str
    confidence_score: float
    primary_risk_factors: List[str] = Field(default_factory=list)
    optimization_suggestions: List[str] = Field(default_factory=list)

    def deterministic_hash(self) -> str:
        raw = json.dumps(
            self.model_dump(),
            sort_keys=True,
            separators=(",", ":")
        )
        return sha256(raw.encode()).hexdigest()