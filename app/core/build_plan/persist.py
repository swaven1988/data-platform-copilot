from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.build_plan.models import BuildPlan


def _copilot_dir(workspace_job_dir: Path) -> Path:
    d = workspace_job_dir / ".copilot"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _plans_dir(workspace_job_dir: Path) -> Path:
    d = _copilot_dir(workspace_job_dir) / "plans"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_plan(workspace_job_dir: Path, plan: BuildPlan) -> str:
    from datetime import datetime, timezone

    plan_id = plan.compute_plan_id()
    out = _plans_dir(workspace_job_dir) / f"{plan_id}.json"

    created_ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    payload: Dict[str, Any] = {
        "plan_id": plan_id,
        "created_ts": created_ts,  # ✅ added
        "plan_version": plan.plan_version,
        "job_name": plan.job_name,
        "spec_hash": plan.spec_hash,
        "baseline_ref": plan.baseline_ref,
        "plugin_fingerprint": plan.plugin_fingerprint,
        "expected_files": plan.expected_files,
        "metadata": plan.metadata or {},
        "steps": [
            {
                "step_id": s.step_id,
                "step_type": s.step_type,
                "depends_on": s.depends_on,
                "inputs": s.inputs,
                "outputs": s.outputs,
                "cache_key": s.cache_key,
            }
            for s in plan.steps
        ],
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return plan_id


def append_events(workspace_job_dir: Path, events: List[Dict[str, Any]]) -> None:
    """
    Append JSONL events to workspace/<job>/.copilot/events.log
    Robust: if existing file doesn't end with newline, add one first.
    """
    if not events:
        return

    log = _copilot_dir(workspace_job_dir) / "events.log"
    log.parent.mkdir(parents=True, exist_ok=True)

    with log.open("ab+") as f:
        # Ensure newline boundary before appending
        f.seek(0, 2)  # end
        size = f.tell()
        if size > 0:
            f.seek(-1, 2)
            last = f.read(1)
            if last != b"\n":
                f.write(b"\n")

        # Append events as JSONL
        for e in events:
            f.write((json.dumps(e) + "\n").encode("utf-8"))

