from app.plugins.advisors._internal.registry import PluginRegistry


def test_fingerprint_is_stable_across_loads():
    reg1 = PluginRegistry("app/plugins/advisors")
    reg1.load_all()

    reg2 = PluginRegistry("app/plugins/advisors")
    reg2.load_all()

    assert reg1.fingerprint == reg2.fingerprint
