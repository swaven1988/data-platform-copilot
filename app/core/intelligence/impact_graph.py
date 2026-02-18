from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.build_plan.models import BuildPlan, PlanStep
from app.core.build_plan.advisors import run_plan_advisors


def _load_plan(workspace_job_dir: Path, plan_id: str) -> BuildPlan:
    p = workspace_job_dir / ".copilot" / "plans" / f"{plan_id}.json"
    if not p.exists():
        raise FileNotFoundError(f"plan not found: {p}")
    obj = json.loads(p.read_text(encoding="utf-8"))

    steps = []
    for s in obj.get("steps", []):
        steps.append(
            PlanStep(
                step_id=s["step_id"],
                step_type=s["step_type"],
                depends_on=s.get("depends_on") or [],
                inputs=s.get("inputs") or {},
                outputs=s.get("outputs") or {},
                cache_key=s.get("cache_key"),
            )
        )

    return BuildPlan(
        plan_version=obj.get("plan_version", "v1"),
        spec_hash=obj.get("spec_hash", ""),
        job_name=obj.get("job_name", ""),
        baseline_ref=obj.get("baseline_ref"),
        plugin_fingerprint=obj.get("plugin_fingerprint", "core-only"),
        steps=steps,
        expected_files=obj.get("expected_files") or [],
        metadata=obj.get("metadata") or {},
    )


def build_impact_graph(
    workspace_job_dir: Path,
    *,
    plan_id: str,
) -> Dict[str, Any]:
    plan = _load_plan(workspace_job_dir, plan_id)

    # Re-run advisors against the plan to get findings.
    res = run_plan_advisors(plan, advisors=None, project_root=Path(__file__).resolve().parents[3])
    findings = res.findings or []

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []

    def node(kind: str, key: str, **attrs):
        nid = f"{kind}:{key}"
        if nid not in nodes:
            nodes[nid] = {"id": nid, "kind": kind, "key": key, **attrs}
        return nid

    plan_id_node = node("plan", plan_id, job_name=plan.job_name)
    for f in findings:
        code = f.get("code", "advisor.finding")
        sev = f.get("severity", "warn")
        msg = f.get("message", "")
        fid = node("finding", code + ":" + msg[:60], code=code, severity=sev, message=msg)
        edges.append({"from": plan_id_node, "to": fid, "type": "has_finding"})

        data = f.get("data") or {}
        paths: List[str] = []
        for k in ("path", "file"):
            if isinstance(data.get(k), str):
                paths.append(data[k])
        for k in ("paths", "files"):
            if isinstance(data.get(k), list):
                paths += [str(x) for x in data[k] if x is not None]

        for p in sorted(set(paths)):
            pid = node("path", p)
            edges.append({"from": fid, "to": pid, "type": "touches"})

    # Advisor runtime summary if available
    runtime = (res.plan.metadata or {}).get("advisor_runtime") if hasattr(res, "plan") else None

    return {
        "plan_id": plan_id,
        "job_name": plan.job_name,
        "nodes": list(nodes.values()),
        "edges": edges,
        "finding_count": len(findings),
        "advisor_runtime": runtime,
    }
