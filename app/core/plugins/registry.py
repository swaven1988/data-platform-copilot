from __future__ import annotations

import hashlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import sys


@dataclass(frozen=True)
class PluginInfo:
    kind: str
    name: str
    version: str
    enabled_by_default: bool
    module_path: str


@dataclass
class PluginResolution:
    kind: str
    plugins: List[PluginInfo]
    fingerprint: str
    warnings: List[Dict[str, Any]]


class PluginRegistry:
    """
    Production plugin registry.

    Discovers plugins from:
      <project_root>/app/plugins/<kind>/*.py

    Each plugin module must expose:
      ADVISOR = <object with fields: name, version, enabled_by_default and method advise(plan)->(plan, findings)>
    """

    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            # app/core/plugins/registry.py -> parents[3] = repo root
            project_root = Path(__file__).resolve().parents[3]
        self.project_root = Path(project_root)

    def _plugins_root(self) -> Path:
        return self.project_root / "app" / "plugins"

    def _kind_dir(self, kind: str) -> Path:
        return self._plugins_root() / kind

    def discover(self, kind: str) -> Tuple[List[PluginInfo], List[Dict[str, Any]]]:
        """
        Returns (plugins, warnings). Never raises for a single bad plugin;
        bad ones are skipped with a warning.
        """
        warnings: List[Dict[str, Any]] = []
        plugins: List[PluginInfo] = []

        kind_dir = self._kind_dir(kind)
        if not kind_dir.exists():
            return [], [{
                "code": "plugins.kind_dir_missing",
                "severity": "warn",
                "message": f"No plugin directory found for kind='{kind}' at {str(kind_dir)}",
                "data": {"kind": kind, "path": str(kind_dir)},
            }]

        for py in sorted(kind_dir.glob("*.py")):
            if py.name.startswith("_") or py.name == "__init__.py":
                continue

            try:
                advisor = self._load_symbol(py, symbol="ADVISOR")
                if advisor is None:
                    warnings.append({
                        "code": "plugins.missing_symbol",
                        "severity": "warn",
                        "message": f"Plugin {py.name} missing ADVISOR symbol; skipped",
                        "data": {"module_path": str(py)},
                    })
                    continue

                name = getattr(advisor, "name", None) or py.stem
                version = getattr(advisor, "version", None) or "0.0.0"
                enabled = bool(getattr(advisor, "enabled_by_default", True))

                plugins.append(PluginInfo(
                    kind=kind,
                    name=str(name),
                    version=str(version),
                    enabled_by_default=enabled,
                    module_path=str(py),
                ))

            except Exception as e:
                warnings.append({
                    "code": "plugins.load_failed",
                    "severity": "warn",
                    "message": f"Failed to load plugin {py.name}: {e}",
                    "data": {"module_path": str(py)},
                })

        return plugins, warnings

    def resolve(
        self,
        kind: str,
        *,
        enabled: Optional[List[str]] = None,
        disabled: Optional[List[str]] = None,
        enable_all: bool = False,
    ) -> PluginResolution:
        """
        Resolve active plugins + compute fingerprint.
        """
        plugins, warnings = self.discover(kind)
        enabled = [p.strip() for p in (enabled or []) if p and p.strip()]
        disabled = {p.strip() for p in (disabled or []) if p and p.strip()}

        active: List[PluginInfo] = []
        for p in plugins:
            if p.name in disabled:
                continue
            if enable_all:
                active.append(p)
                continue
            if enabled:
                if p.name in enabled:
                    active.append(p)
            else:
                if p.enabled_by_default:
                    active.append(p)

        fp = self._fingerprint(active)
        return PluginResolution(kind=kind, plugins=active, fingerprint=fp, warnings=warnings)

    def load_advisors(self) -> PluginResolution:
        """
        Backward-compatible helper used by older codepaths.
        """
        return self.resolve("advisors")

    def load_advisor_objects(
        self,
        *,
        enabled: Optional[List[str]] = None,
        disabled: Optional[List[str]] = None,
        enable_all: bool = False,
    ) -> Tuple[List[Any], str, List[Dict[str, Any]]]:
        """
        Returns: (advisor_objects, fingerprint, warnings)
        """
        res = self.resolve("advisors", enabled=enabled, disabled=disabled, enable_all=enable_all)
        objs: List[Any] = []
        for p in res.plugins:
            try:
                objs.append(self._load_symbol(Path(p.module_path), symbol="ADVISOR"))
            except Exception as e:
                res.warnings.append({
                    "code": "plugins.instantiate_failed",
                    "severity": "warn",
                    "message": f"Failed to instantiate advisor '{p.name}': {e}",
                    "data": {"module_path": p.module_path},
                })
        objs = [o for o in objs if o is not None]
        return objs, res.fingerprint, res.warnings

    def _fingerprint(self, plugins: List[PluginInfo]) -> str:
        """
        Stable fingerprint for the active plugin set.

        - Deterministic across restarts
        - Deterministic across machines (uses relative path)
        - Does NOT include mtime (mtime makes fingerprints non-reproducible)
        """
        h = hashlib.sha256()

        plugins_root = self._plugins_root().resolve()

        # sort to guarantee stable ordering
        for p in sorted(plugins, key=lambda x: (x.name, x.version, x.module_path)):
            mp = Path(p.module_path).resolve()
            try:
                rel = mp.relative_to(plugins_root).as_posix()
            except Exception:
                rel = mp.as_posix()

            h.update(f"{p.name}:{p.version}:{rel}".encode("utf-8"))

        return h.hexdigest()[:16]

    def _load_symbol(self, module_path: Path, symbol: str):
        module_path = Path(module_path).resolve()

        # IMPORTANT: module name must be deterministic across interpreter restarts
        path_key = str(module_path).replace("\\", "/").lower().encode("utf-8")
        path_hash = hashlib.sha1(path_key).hexdigest()[:16]
        module_name = f"copilot_plugin_{module_path.stem}_{path_hash}"

        spec = importlib.util.spec_from_file_location(module_name, str(module_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {module_path}")

        mod = importlib.util.module_from_spec(spec)

        # ✅ CRITICAL FIX: register the module BEFORE exec_module (dataclasses needs this)
        sys.modules[module_name] = mod

        try:
            spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        except Exception:
            # cleanup on failure so we don't leave a broken module cached
            sys.modules.pop(module_name, None)
            raise

        obj = getattr(mod, symbol, None)
        return obj
