# tests/test_cost_estimator_v2.py
from app.core.cost.models import CostInputs
from app.core.cost.estimator_v2 import estimate_cost_v2


def test_cost_estimator_v2_deterministic():
    inp = CostInputs(provider="aws", region="us-east-1", executors=4, vcpu_per_executor=4.0, runtime_minutes=30.0)
    e1 = estimate_cost_v2(inp).to_dict()
    e2 = estimate_cost_v2(inp).to_dict()
    assert e1 == e2
    assert e1["estimated_total_cost_usd"] > 0.0


def test_cost_estimator_v2_spot_cheaper():
    ond = estimate_cost_v2(CostInputs(provider="aws", region="us-east-1", executors=4, vcpu_per_executor=4.0, runtime_minutes=30.0, spot=False)).to_dict()
    spot = estimate_cost_v2(CostInputs(provider="aws", region="us-east-1", executors=4, vcpu_per_executor=4.0, runtime_minutes=30.0, spot=True)).to_dict()
    assert spot["estimated_total_cost_usd"] < ond["estimated_total_cost_usd"]