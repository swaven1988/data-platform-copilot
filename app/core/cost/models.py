# app/core/cost/models.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class CostInputs:
    provider: str  # aws|gcp|azure|k8s
    region: Optional[str] = None
    instance_type: Optional[str] = None
    executors: int = 2
    vcpu_per_executor: float = 4.0
    mem_gb_per_executor: float = 16.0
    spot: bool = False
    runtime_minutes: float = 30.0


@dataclass
class CostEstimate:
    runtime_minutes: float
    compute_cost_usd: float
    infra_cost_usd: float
    estimated_total_cost_usd: float
    confidence: float
    assumptions: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runtime_minutes": self.runtime_minutes,
            "compute_cost_usd": self.compute_cost_usd,
            "infra_cost_usd": self.infra_cost_usd,
            "estimated_total_cost_usd": self.estimated_total_cost_usd,
            "confidence": self.confidence,
            "assumptions": self.assumptions,
        }