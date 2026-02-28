"""
Phase F — Pricing tables unit tests.
"""
from __future__ import annotations

import pytest

from app.core.cost.pricing_tables import vcpu_hour_price, DEFAULT_VCPU_HOUR, SPOT_DISCOUNT


@pytest.mark.parametrize("provider,region,expected", [
    ("aws",   "us-east-1",    0.045),
    ("aws",   "eu-west-1",    0.052),
    ("gcp",   "us-central1",  0.044),
    ("gcp",   "europe-west1", 0.050),
    ("azure", "eastus",       0.047),
    ("azure", "westeurope",   0.053),
    ("k8s",   "default",      0.040),
])
def test_known_regions_return_expected_price(provider, region, expected):
    assert vcpu_hour_price(provider, region) == expected


def test_unknown_region_falls_back_to_provider_default():
    # k8s has a "default" key; unknown region should fall back to it
    price = vcpu_hour_price("k8s", "eu-north-99")
    assert price == DEFAULT_VCPU_HOUR[("k8s", "default")]


def test_completely_unknown_provider_returns_fallback():
    price = vcpu_hour_price("alibaba", "cn-hangzhou")
    assert price == 0.05


def test_case_insensitive_provider():
    lower = vcpu_hour_price("aws", "us-east-1")
    upper = vcpu_hour_price("AWS", "us-east-1")
    assert lower == upper


def test_none_region_treated_as_default():
    # should not crash and should return a numeric fallback
    price = vcpu_hour_price("k8s", None)
    assert isinstance(price, float)
    assert price > 0


def test_spot_discount_is_fraction():
    assert 0.0 < SPOT_DISCOUNT < 1.0


def test_spot_discount_applied_example():
    base = vcpu_hour_price("aws", "us-east-1")
    discounted = base * (1 - SPOT_DISCOUNT)
    assert discounted < base
    assert discounted > 0
