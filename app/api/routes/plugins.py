from __future__ import annotations

from fastapi import APIRouter, Query
from typing import Optional

from app.plugins.advisors._internal.registry import PluginRegistry
from app.plugins.advisors._internal.config import AdvisorsRunConfig
from app.plugins.advisors._internal.resolver import resolve_advisors
from app.plugins.advisors._internal.registry import get_run_cache



router = APIRouter()

def _registry() -> PluginRegistry:
    # adjust if you already have a singleton/provider
    reg = PluginRegistry("app/plugins/advisors")
    reg.load_all()
    return reg
    

@router.get("/plugins/resolve")
def resolve_plugins(
    intent: str | None = Query(None),
    enabled: Optional[str] = Query(default=None),
    disabled: Optional[str] = Query(default=None),
):
    reg = _registry()

    enabled_list = [x.strip() for x in (enabled or "").split(",") if x.strip()]
    disabled_list = [x.strip() for x in (disabled or "").split(",") if x.strip()]

    cfg = AdvisorsRunConfig(
        enabled=enabled_list or None,
        disabled=disabled_list,
        options={},
    )

    selected, skipped = resolve_advisors(
        reg,
        intent=intent,
        paths=None,
        cfg=cfg,
    )

    cache = get_run_cache()


    return {
        "selected": [p.name for p in selected],
        "skipped": skipped,
        "order": [p.name for p in selected],
        "cache": {
            "hits": cache.hits,
            "misses": cache.misses,
            "entries": len(cache._store),
            "ttl_seconds": cache.ttl_seconds,
            "max_entries": cache.max_entries,
        },
    }


@router.get("/plugins")
def list_plugins(
    enabled_only: bool = False,
    enabled: Optional[str] = Query(default=None),
    disabled: Optional[str] = Query(default=None),
):
    reg = _registry()

    enabled_list = [x.strip() for x in (enabled or "").split(",") if x.strip()]
    disabled_list = [x.strip() for x in (disabled or "").split(",") if x.strip()]

    cfg = AdvisorsRunConfig(
        enabled=enabled_list or None,
        disabled=disabled_list,
        options={},
    )

    names = sorted(reg._plugins.keys())
    if enabled_only:
        names = [p.name for p in reg.get_active_plugins(cfg)]

    plugins_out = []
    for name in names:
        p = reg._plugins[name]
        file_path = str(reg._plugin_files[name])
        plugins_out.append(
            {
                "name": getattr(p, "name", name),
                "version": getattr(p, "version", "0.0.0"),
                "enabled_by_default": bool(getattr(p, "enabled_by_default", True)),
                "module_path": file_path,
                "enabled": cfg.is_enabled_with_default(
                    name,
                    enabled_by_default=bool(getattr(p, "enabled_by_default", True)),
                ),
            }
        )

    return {
        "kind": "advisors",
        "count": len(plugins_out),
        "fingerprint": reg.fingerprint,
        "plugins": plugins_out,
        "warnings": [],
    }

@router.get("/cache/stats")
def cache_stats():
    cache = get_run_cache()
    return {
        "kind": "advisors_run_cache",
        "hits": cache.hits,
        "misses": cache.misses,
        "entries": len(cache._store),
        "ttl_seconds": cache.ttl_seconds,
        "max_entries": cache.max_entries,
    }
