from typing import List, Optional, Dict

from .registry import PluginRegistry
from .config import AdvisorsRunConfig


def resolve_advisors(
    registry: PluginRegistry,
    *,
    intent: Optional[str] = None,
    paths: Optional[list[str]] = None,
    cfg: Optional[AdvisorsRunConfig] = None,
):
    if cfg is None:
        cfg = AdvisorsRunConfig()

    all_plugins: Dict[str, object] = registry._plugins
    active_plugins = registry.get_active_plugins(cfg)

    active_names = {p.name for p in active_plugins}

    selected = []
    skipped = []

    for name, plugin in all_plugins.items():
        if name not in active_names:
            skipped.append({"name": name, "reason": "disabled"})
            continue

        # Intent filtering (if applies_to defined)
        applies_to = getattr(plugin, "applies_to", [])
        if applies_to and intent and intent not in applies_to:
            skipped.append({"name": name, "reason": "not_applicable"})
            continue

        selected.append(plugin)

    PHASE_ORDER = {
        "preflight": 10,
        "build": 20,
        "advise": 30,
        "post": 40,
    }

    selected.sort(
        key=lambda p: (
            PHASE_ORDER.get(getattr(p, "phase", "advise"), 999),
            getattr(p, "priority", 100),
            p.name,
        )
    )

    return selected, skipped
