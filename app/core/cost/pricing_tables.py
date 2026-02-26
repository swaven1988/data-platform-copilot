# app/core/cost/pricing_tables.py
from __future__ import annotations

from typing import Dict, Tuple

# Phase 8B: lightweight static tables (calibration later via loader)
# Units: USD per vCPU-hour equivalent (normalized), best-effort defaults
# NOTE: these are placeholders for realism scaffolding, not authoritative cloud pricing.

DEFAULT_VCPU_HOUR: Dict[Tuple[str, str], float] = {
    ("aws", "us-east-1"): 0.045,
    ("aws", "eu-west-1"): 0.052,
    ("gcp", "us-central1"): 0.044,
    ("gcp", "europe-west1"): 0.050,
    ("azure", "eastus"): 0.047,
    ("azure", "westeurope"): 0.053,
    ("k8s", "default"): 0.040,
}

SPOT_DISCOUNT: float = 0.60  # 60% off baseline (simple)


def vcpu_hour_price(provider: str, region: str | None) -> float:
    key = (provider.lower(), (region or "default"))
    if key in DEFAULT_VCPU_HOUR:
        return DEFAULT_VCPU_HOUR[key]
    # fallback to provider default
    key2 = (provider.lower(), "default")
    return DEFAULT_VCPU_HOUR.get(key2, 0.05)