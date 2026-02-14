from app.plugins.advisors._internal.registry import PluginRegistry
from app.plugins.advisors._internal.config import AdvisorsRunConfig
from app.plugins.advisors._internal.resolver import resolve_advisors


def test_resolver_skips_not_applicable():
    reg = PluginRegistry("app/plugins/advisors")
    reg.load_all()

    # force applies_to on a known plugin
    p = reg._plugins["basic_checks"]
    setattr(p, "applies_to", ["build"])

    cfg = AdvisorsRunConfig(enabled=None, disabled=[], options={})

    selected, skipped = resolve_advisors(reg, intent="analyze", cfg=cfg)

    selected_names = [x.name for x in selected]
    assert "basic_checks" not in selected_names

    skipped_map = {x["name"]: x["reason"] for x in skipped}
    assert skipped_map["basic_checks"] == "not_applicable"
