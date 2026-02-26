from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Query

from app.core.plugins.registry import PluginRegistry

# plugins_api.py lives at: <repo_root>/app/api/plugins_api.py
# parents[0]=api, parents[1]=app, parents[2]=<repo_root>
PROJECT_ROOT = Path(__file__).resolve().parents[2]

router = APIRouter(prefix="/plugins", tags=["Plugins"])


@router.get("")
def list_plugins(kind: str = Query("advisors", pattern="^(advisors)$")) -> Dict[str, Any]:
    reg = PluginRegistry(PROJECT_ROOT)
    res = reg.resolve(kind)

    return {
        "kind": res.kind,
        "count": len(res.plugins),
        "fingerprint": res.fingerprint,
        "plugins": [
            {
                "name": p.name,
                "version": p.version,
                "enabled_by_default": p.enabled_by_default,
                "module_path": p.module_path,
            }
            for p in res.plugins
        ],
        "warnings": res.warnings or [],
    }
