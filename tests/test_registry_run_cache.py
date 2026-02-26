from app.plugins.advisors._internal.registry import PluginRegistry
from app.plugins.advisors._internal.config import AdvisorsRunConfig


def test_registry_run_uses_cache(monkeypatch):
    reg = PluginRegistry("app/plugins/advisors")
    reg.load_all()

    calls = {"n": 0}
    orig_invoke = reg._invoke

    def wrapped_invoke(*args, **kwargs):
        calls["n"] += 1
        return orig_invoke(*args, **kwargs)

    monkeypatch.setattr(reg, "_invoke", wrapped_invoke)

    class _Plan:
        job_name = "test_job"

    # include heads in ctx for cache key
    ctx = {"plan": _Plan(), "spec": {"x": 1}, "workspace_head": "A", "upstream_head": "B"}

    cfg = AdvisorsRunConfig(enabled=None, disabled=["basic_checks"], options={})

    # first run: invokes plugin(s)
    reg.run(context=ctx, cfg=cfg)
    first = calls["n"]

    # second run: cache hit (no new invokes)
    reg.run(context=ctx, cfg=cfg)
    second = calls["n"]

    assert first > 0
    assert second == first

    # changing heads should invalidate cache
    ctx["workspace_head"] = "A2"
    reg.run(context=ctx, cfg=cfg)
    third = calls["n"]
    assert third > second

    # force=True should bypass cache even if heads unchanged
    cfg_force = AdvisorsRunConfig(enabled=None, disabled=["basic_checks"], options={}, force=True)
    reg.run(context=ctx, cfg=cfg_force)
    fourth = calls["n"]
    assert fourth > third
