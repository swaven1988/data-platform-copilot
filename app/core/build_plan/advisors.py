from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.build_plan.models import BuildPlan
from app.plugins.advisors._internal.config import AdvisorsRunConfig
from app.plugins.advisors._internal.registry import PluginRegistry
from app.plugins.advisors._internal.types import AdvisorFinding


def _finding_to_dict(f: Any) -> Dict[str, Any]:
    if f is None:
        return {"code": "advisor.unknown", "severity": "warn", "message": "Empty advisor finding", "data": {}}

    # already a dict
    if isinstance(f, dict):
        out = dict(f)
        if "severity" not in out and "level" in out:
            out["severity"] = out.get("level")
        out.setdefault("code", "advisor.finding")
        out.setdefault("severity", "warn")
        out.setdefault("message", str(f))
        out.setdefault("data", out.get("data", {}))
        # optional: strip "level" if you want only one key
        # out.pop("level", None)
        return out

    d = getattr(f, "__dict__", None)
    if isinstance(d, dict):
        out = dict(d)
        if "severity" not in out and "level" in out:
            out["severity"] = out.get("level")
        out.setdefault("code", "advisor.finding")
        out.setdefault("severity", "warn")
        out.setdefault("message", out.get("message", str(f)))
        out.setdefault("data", out.get("data", {}))
        return out

    return {"code": "advisor.finding", "severity": "warn", "message": str(f), "data": {}}



def run_plan_advisors(
    plan: BuildPlan,
    *,
    advisors: Optional[List[Any]] = None,
    project_root: Optional[Path] = None,
    options: Optional[Dict[str, Any]] = None,
):
    options = options or {}
    project_root = project_root or Path(__file__).resolve().parents[3]

    findings: List[Dict[str, Any]] = []

    if advisors is None or isinstance(advisors, dict):
        plugins_dir = project_root / "app" / "plugins" / "advisors"
        reg = PluginRegistry(plugins_dir)
        reg.load_all()

        # advisors payload may come directly OR via options["advisors"]
        adv_payload = advisors if isinstance(advisors, dict) else ((options or {}).get("advisors") or {})
        cfg = AdvisorsRunConfig.from_payload(adv_payload)


        fp = reg.fingerprint
        plan = replace(
            plan,
            plugin_fingerprint=fp,
            metadata={**(plan.metadata or {}), "advisor_fingerprint": fp},
        )

        ctx: Dict[str, Any] = {"plan": plan, "spec": None}
        adv_findings: List[AdvisorFinding] = reg.run(context=ctx, cfg=cfg) or []

        plan = ctx.get("plan", plan)

        for f in adv_findings:
            findings.append(_finding_to_dict(f))

    else:
        # Manual advisors list supplied. Normalize strings -> plugin instances.
        plugins_dir = project_root / "app" / "plugins" / "advisors"
        reg = PluginRegistry(plugins_dir)
        reg.load_all()

        normalized: List[Any] = []
        for adv in (advisors or []):
            if adv is None:
                continue

            if isinstance(adv, str):
                # NOTE: implement reg.get(name) if missing
                plugin = reg.get(adv)  # must return plugin instance or None
                if plugin is None:
                    findings.append({
                        "code": "advisor.failed",
                        "severity": "warn",
                        "message": "Advisor name could not be resolved to a plugin instance.",
                        "data": {"advisor": adv},
                    })
                    continue
                normalized.append(plugin)
            else:
                normalized.append(adv)

        plan = replace(
            plan,
            plugin_fingerprint=(plan.plugin_fingerprint or "manual"),
            metadata={
                **(plan.metadata or {}),
                "advisor_fingerprint": (plan.metadata or {}).get("advisor_fingerprint", "manual"),
            },
        )

        adv_cfg = (options or {}).get("advisors") or {}
        adv_opts_by_name = adv_cfg.get("options") or {}

        for adv in normalized:
            try:
                plugin_opts = adv_opts_by_name.get(getattr(adv, "name", ""), {})

                try:
                    res = adv.advise(plan, options=plugin_opts)
                except TypeError:
                    res = adv.advise(plan)

                if isinstance(res, tuple) and len(res) == 2:
                    plan2, f2 = res
                    if plan2 is not None:
                        plan = plan2
                    for f in (f2 or []):
                        findings.append(_finding_to_dict(f))
                else:
                    if isinstance(res, list):
                        for f in res:
                            findings.append(_finding_to_dict(f))
                    elif res is not None:
                        findings.append(_finding_to_dict(res))

            except Exception as e:
                findings.append({
                    "code": "advisor.failed",
                    "severity": "warn",
                    "message": f"Advisor execution failed: {e}",
                    "data": {"advisor": getattr(adv, "name", type(adv).__name__)},
                })

    class _Result:
        def __init__(self, plan, findings):
            self.plan = plan
            self.findings = findings

    return _Result(plan=plan, findings=findings)


