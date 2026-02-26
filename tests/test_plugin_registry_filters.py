from app.plugins.advisors._internal.config import AdvisorsRunConfig
from app.plugins.advisors._internal.registry import PluginRegistry


def test_enable_allowlist_only_runs_selected():
    reg = PluginRegistry("app/plugins/advisors")
    reg.load_all()

    cfg = AdvisorsRunConfig(enabled=["basic_checks"], disabled=[])
    active = [p.name for p in reg.get_active_plugins(cfg)]
    assert active == ["basic_checks"]


def test_disable_list_removes_plugin():
    reg = PluginRegistry("app/plugins/advisors")
    reg.load_all()

    cfg = AdvisorsRunConfig(enabled=None, disabled=["always_warn"])
    active = [p.name for p in reg.get_active_plugins(cfg)]
    assert "always_warn" not in active
