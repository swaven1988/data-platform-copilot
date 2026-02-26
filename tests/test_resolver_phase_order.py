from app.plugins.advisors._internal.registry import PluginRegistry
from app.plugins.advisors._internal.config import AdvisorsRunConfig
from app.plugins.advisors._internal.resolver import resolve_advisors


def test_resolver_orders_by_phase_then_priority_then_name():
    reg = PluginRegistry("app/plugins/advisors")
    reg.load_all()

    p1 = reg._plugins["always_warn"]
    setattr(p1, "phase", "preflight")
    setattr(p1, "priority", 100)

    p2 = reg._plugins["basic_checks"]
    setattr(p2, "phase", "advise")
    setattr(p2, "priority", 1)

    cfg = AdvisorsRunConfig(enabled=None, disabled=[], options={})

    selected, _ = resolve_advisors(reg, intent="build", cfg=cfg)

    names = [p.name for p in selected]

    # phase should dominate: preflight comes before advise
    assert names.index("always_warn") < names.index("basic_checks")
