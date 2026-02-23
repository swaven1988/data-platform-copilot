# app/core/preflight/estimator.py

import hashlib
import json
from .models import PreflightRequest, CostEstimate


def _hash_request(req: PreflightRequest) -> str:
    payload = json.dumps(req.dict(), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def estimate(req: PreflightRequest) -> tuple[str, CostEstimate]:
    preflight_hash = _hash_request(req)

    gb = req.dataset.estimated_input_gb
    shuffle = req.dataset.shuffle_multiplier
    executors = req.pricing.executors
    cost_per_hour = req.pricing.cost_per_executor_hour

    runtime_minutes = max(1.0, (gb * shuffle) / max(0.5, executors) * 5.0)
    compute_cost = (runtime_minutes / 60.0) * executors * cost_per_hour

    confidence = 0.7
    if gb > 100:
        confidence = 0.6
    if gb < 10:
        confidence = 0.85

    return preflight_hash, CostEstimate(
        runtime_minutes=round(runtime_minutes, 2),
        compute_cost_usd=round(compute_cost, 2),
        confidence=confidence,
    )