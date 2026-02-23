# app/core/preflight/models.py

from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class SLAConfig(BaseModel):
    max_runtime_minutes: Optional[int] = None


class PricingHints(BaseModel):
    cost_per_executor_hour: float = 0.5
    executors: int = 2


class DatasetHints(BaseModel):
    estimated_input_gb: float = 1.0
    shuffle_multiplier: float = 1.5
    estimated_rows: Optional[int] = None


class PreflightRequest(BaseModel):
    job_name: str
    runtime_profile: str
    dataset: DatasetHints = Field(default_factory=DatasetHints)
    pricing: PricingHints = Field(default_factory=PricingHints)
    sla: Optional[SLAConfig] = None
    spark_conf: Optional[Dict[str, str]] = None


class CostEstimate(BaseModel):
    runtime_minutes: float
    compute_cost_usd: float
    confidence: float


class RiskReport(BaseModel):
    risk_score: float
    risk_reasons: List[str]


class PreflightReport(BaseModel):
    job_name: str
    preflight_hash: str
    estimate: CostEstimate
    risk: RiskReport
    policy_decision: str  # ALLOW | WARN | BLOCK