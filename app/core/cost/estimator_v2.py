# app/core/cost/estimator_v2.py
from __future__ import annotations

from .models import CostEstimate, CostInputs
from .pricing_tables import SPOT_DISCOUNT, vcpu_hour_price


def estimate_cost_v2(inp: CostInputs) -> CostEstimate:
    provider = inp.provider.lower()
    region = inp.region or ("default" if provider == "k8s" else "us-east-1")

    price = vcpu_hour_price(provider, region)
    if inp.spot:
        price = price * (1.0 - SPOT_DISCOUNT)

    runtime_hours = max(inp.runtime_minutes, 1.0) / 60.0
    total_vcpu = max(inp.executors, 1) * max(inp.vcpu_per_executor, 0.5)

    compute = total_vcpu * price * runtime_hours
    infra = compute * 0.08  # small overhead (network/storage) placeholder
    total = compute + infra

    # Confidence: higher if provider+region known and inputs present
    confidence = 0.80
    if inp.region is None:
        confidence -= 0.05
    if inp.instance_type is None:
        confidence -= 0.05
    confidence = max(0.50, min(0.95, confidence))

    return CostEstimate(
        runtime_minutes=float(inp.runtime_minutes),
        compute_cost_usd=float(round(compute, 4)),
        infra_cost_usd=float(round(infra, 4)),
        estimated_total_cost_usd=float(round(total, 4)),
        confidence=float(round(confidence, 3)),
        assumptions={
            "provider": provider,
            "region": region,
            "executors": inp.executors,
            "vcpu_per_executor": inp.vcpu_per_executor,
            "spot": inp.spot,
            "price_per_vcpu_hour": price,
            "infra_overhead_pct": 0.08,
        },
    )