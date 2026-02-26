from __future__ import annotations
from .cache import AdvisorsRunCache, make_cache_key

_RUN_CACHE = AdvisorsRunCache(max_entries=256, ttl_seconds=300)

def get_run_cache() -> AdvisorsRunCache:
    return _RUN_CACHE


import hashlib
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional

from app.plugins.advisors._internal.config import AdvisorsRunConfig
from app.plugins.advisors._internal.types import AdvisorFinding, AdvisorPlugin
from app.plugins.advisors._internal.graph import AdvisorNode, AdvisorExecutionGraph

import logging
import time

@dataclass(frozen=True)
class PluginInfo:
    name: str
    file: str


class PluginRegistry:
    def __init__(self, plugins_dir: str | Path):
        self._plugins_dir = Path(plugins_dir)
        self._plugins: Dict[str, Any] = {}
        self._plugin_files: Dict[str, Path] = {}
        self._fingerprint: Optional[str] = None

    @property
    def fingerprint(self) -> str:
        if self._fingerprint is None:
            self._fingerprint = self._compute_fingerprint()
        return self._fingerprint

    def reload(self) -> None:
        self._plugins.clear()
        self._plugin_files.clear()
        self._fingerprint = None
        self.load_all()

    def load_all(self) -> None:
        for py in sorted(self._plugins_dir.glob("*.py")):
            if py.name.startswith("_"):
                continue
            plugin = self._load_plugin_from_file(py)
            if plugin.name in self._plugins:
                raise ValueError(f"Duplicate plugin name: {plugin.name} ({py})")
            self._plugins[plugin.name] = plugin
            self._plugin_files[plugin.name] = py

    def list_plugins(self) -> List[PluginInfo]:
        return [PluginInfo(name=n, file=str(self._plugin_files[n])) for n in sorted(self._plugins.keys())]

    def get_active_plugins(self, cfg: AdvisorsRunConfig) -> List[Any]:
        active: List[Any] = []
        for name in sorted(self._plugins.keys()):
            p = self._plugins[name]
            if cfg.is_enabled_with_default(
                name,
                enabled_by_default=bool(getattr(p, "enabled_by_default", True)),
            ):
                active.append(p)
        return active

    def run(self, *, context: Dict[str, Any], cfg: AdvisorsRunConfig) -> List[AdvisorFinding]:
        from .resolver import resolve_advisors

        log = logging.getLogger(__name__)

        t0_total = time.perf_counter()
        findings: List[AdvisorFinding] = []

        # Ensure advisor_outputs exists and is a dict
        ao = context.setdefault("advisor_outputs", {})
        if not isinstance(ao, dict):
            ao = {}
            context["advisor_outputs"] = ao

        cache_key = make_cache_key(
            intent=getattr(cfg, "intent", None),
            paths=getattr(cfg, "paths", None),
            cfg=cfg,
            context=context,
            plugins_fingerprint=self.fingerprint,
        )

        cache_hit = False
        if not getattr(cfg, "force", False):
            t0_cache = time.perf_counter()
            cached = _RUN_CACHE.get(cache_key)
            t1_cache = time.perf_counter()

            if cached is not None:
                cache_hit = True
                context["plan"] = cached.plan

                ao["__meta__"] = {
                    **(ao.get("__meta__", {}) if isinstance(ao.get("__meta__"), dict) else {}),
                    "cache": "hit",
                    "cache_lookup_ms": int(round((t1_cache - t0_cache) * 1000)),
                    "total_ms": int(round((time.perf_counter() - t0_total) * 1000)),
                    "plugins_fingerprint": self.fingerprint,
                }

                log.debug(
                    "advisors.run cache=hit lookup_ms=%s findings=%s",
                    ao["__meta__"]["cache_lookup_ms"],
                    len(cached.findings or []),
                )
                return list(cached.findings)

            # cache miss
            ao["__meta__"] = {
                **(ao.get("__meta__", {}) if isinstance(ao.get("__meta__"), dict) else {}),
                "cache": "miss",
                "cache_lookup_ms": int(round((t1_cache - t0_cache) * 1000)),
                "plugins_fingerprint": self.fingerprint,
            }

        # Resolve advisors
        t0_resolve = time.perf_counter()
        plugins, _skipped = resolve_advisors(
            self,
            intent=getattr(cfg, "intent", None),
            paths=getattr(cfg, "paths", None),
            cfg=cfg,
        )
        t1_resolve = time.perf_counter()

        # Build graph
        t0_graph = time.perf_counter()
        graph = AdvisorExecutionGraph()
        name_to_plugin: Dict[str, Any] = {}

        for p in (plugins or []):
            pname = getattr(p, "name", None) or type(p).__name__
            name_to_plugin[pname] = p

            deps = getattr(p, "depends_on", None) or getattr(p, "requires", None) or []
            if isinstance(deps, str):
                deps = [deps]
            deps = [d for d in deps if isinstance(d, str) and d]

            phase = getattr(p, "phase", "advise")
            priority = getattr(p, "priority", 100)
            graph.add_node(AdvisorNode(name=pname, phase=phase, priority=priority, depends_on=deps))

        t1_graph = time.perf_counter()

        # Topological sort timing
        t0_sort = time.perf_counter()
        order = graph.topological_sort()
        t1_sort = time.perf_counter()

        # Execute in order
        for pname in order:
            plugin = name_to_plugin.get(pname)
            if plugin is None:
                f = AdvisorFinding(
                    code="advisor.failed",
                    severity="warn",
                    message="Advisor dependency missing from resolved plugin set.",
                    data={"advisor": pname},
                )
                findings.append(f)
                ao[pname] = {"findings": [f], "duration_ms": 0}
                continue

            opts = cfg.plugin_options(getattr(plugin, "name", pname))

            t0_inv = time.perf_counter()
            try:
                out = self._invoke(plugin, context=context, options=opts) or []
            except Exception as e:
                out = [AdvisorFinding(
                    code="advisor.failed",
                    severity="warn",
                    message=f"Advisor execution failed: {e}",
                    data={"advisor": getattr(plugin, "name", pname)},
                )]
            t1_inv = time.perf_counter()

            ao[pname] = {
                "findings": out,
                "duration_ms": int(round((t1_inv - t0_inv) * 1000)),
            }
            findings.extend(out)

        # Persist cache
        _RUN_CACHE.set(cache_key, findings, context.get("plan"))

        # Final meta timings
        meta = ao.get("__meta__", {})
        if not isinstance(meta, dict):
            meta = {}

        meta.update({
            "cache": meta.get("cache") or ("hit" if cache_hit else "miss"),
            "resolve_ms": int(round((t1_resolve - t0_resolve) * 1000)),
            "graph_build_ms": int(round((t1_graph - t0_graph) * 1000)),
            "toposort_ms": int(round((t1_sort - t0_sort) * 1000)),
            "plugin_count": len(order),
            "finding_count": len(findings),
            "total_ms": int(round((time.perf_counter() - t0_total) * 1000)),
            "plugins_fingerprint": self.fingerprint,
        })
        ao["__meta__"] = meta

        log.debug(
            "advisors.run cache=%s resolve_ms=%s graph_ms=%s sort_ms=%s plugins=%s findings=%s total_ms=%s",
            meta.get("cache"),
            meta.get("resolve_ms"),
            meta.get("graph_build_ms"),
            meta.get("toposort_ms"),
            meta.get("plugin_count"),
            meta.get("finding_count"),
            meta.get("total_ms"),
        )

        return findings


    def get(self, name: str):
        return self._plugins.get(name)


    # --- internals ---

    def _compute_fingerprint(self) -> str:
        h = hashlib.sha256()
        for py in sorted(self._plugins_dir.glob("*.py")):
            if py.name.startswith("_"):
                continue
            h.update(py.name.encode("utf-8"))
            h.update(b"\0")
            h.update(py.read_bytes())
            h.update(b"\0")
        return h.hexdigest()[:16]

    def _load_symbol(self, *, file_path: Path, module_qualname: str) -> ModuleType:
        spec = importlib.util.spec_from_file_location(module_qualname, str(file_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load spec for {module_qualname} from {file_path}")

        module = importlib.util.module_from_spec(spec)

        # critical fix: register in sys.modules BEFORE exec_module
        sys.modules[module_qualname] = module
        spec.loader.exec_module(module)
        return module

    def _load_plugin_from_file(self, file_path: Path) -> AdvisorPlugin:
        module_name = f"app.plugins.advisors._runtime.{file_path.stem}"
        module = self._load_symbol(file_path=file_path, module_qualname=module_name)

        # support both names; your repo uses ADVISOR
        sym = None
        if hasattr(module, "ADVISOR"):
            sym = "ADVISOR"
        elif hasattr(module, "PLUGIN"):
            sym = "PLUGIN"

        if sym is None:
            raise AttributeError(f"{file_path.name} must define ADVISOR (or PLUGIN)")

        plugin = getattr(module, sym)

        if not hasattr(plugin, "name"):
            raise AttributeError(f"{file_path.name}: {sym} must have 'name'")

        if not (
            (hasattr(plugin, "run") and callable(getattr(plugin, "run")))
            or (hasattr(plugin, "advise") and callable(getattr(plugin, "advise")))
            or callable(plugin)
        ):
            raise AttributeError(f"{file_path.name}: {sym} must implement run() or advise() or be callable")

        return plugin
    
    def _normalize_result(self, result: Any, *, context: Dict[str, Any]) -> List[AdvisorFinding]:
        if result is None:
            return []

        # 1) Most common: already a list of findings
        if isinstance(result, list):
            return list(result)

        # 2) Tuple shape: (plan, findings) OR (findings, plan)
        if isinstance(result, tuple) and len(result) == 2:
            a, b = result

            # expected: (plan, findings)
            if isinstance(b, list):
                plan, findings = a, b
            # tolerate: (findings, plan)
            elif isinstance(a, list):
                findings, plan = a, b
            else:
                return []

            if plan is not None:
                context["plan"] = plan
            return list(findings or [])

        return []


    def _invoke(self, plugin: Any, *, context: Dict[str, Any], options: Dict[str, Any]) -> List[AdvisorFinding]:
        # 1) run(context=..., options=...)
        if hasattr(plugin, "run") and callable(getattr(plugin, "run")):
            try:
                return self._normalize_result(plugin.run(context=context, options=options), context=context)
            except TypeError:
                try:
                    return self._normalize_result(plugin.run(context, options), context=context)
                except TypeError:
                    return self._normalize_result(plugin.run(context), context=context)


        # 2) advise(...) : try kw variants, then positional
        if hasattr(plugin, "advise") and callable(getattr(plugin, "advise")):
            fn = plugin.advise

            plan = context.get("plan")

            kwargs_variants = []
            if plan is not None:
                kwargs_variants.extend([
                    {"plan": plan, "options": options},
                    {"plan": plan},
                ])

            kwargs_variants.extend([
                {"context": context, "options": options},
                {"spec": context.get("spec"), "options": options},
                {"spec": context.get("spec")},
                {"payload": context, "options": options},
                {"payload": context},
                {"input": context, "options": options},
                {"input": context},
            ])

            for kwargs in kwargs_variants:
                try:
                    return self._normalize_result(fn(**kwargs), context=context)
                except TypeError:
                    pass


            plan = context.get("plan")

            positional_args = []
            if plan is not None:
                positional_args.extend([
                    (plan,),
                    (plan, options),
                ])

            positional_args.extend([
                (context, options),
                (context,),
                (context.get("spec"), options),
                (context.get("spec"),),
            ])

            for args in positional_args:
                try:
                    return self._normalize_result(fn(*args), context=context)
                except TypeError:
                    pass


            raise TypeError(f"{getattr(plugin, 'name', '<unknown>')}.advise() signature not supported by _invoke()")

        # 3) callable plugin
        if callable(plugin):
            try:
                return self._normalize_result(plugin(context=context, options=options), context=context)
            except TypeError:
                try:
                    return self._normalize_result(plugin(context, options), context=context)
                except TypeError:
                    return self._normalize_result(plugin(context), context=context)

        raise AttributeError(f"{getattr(plugin, 'name', '<unknown>')} has no run()/advise() and is not callable")
