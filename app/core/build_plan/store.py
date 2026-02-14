from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class PlanPointer:
    plan_id: str
    file_path: str
    created_ts: Optional[str] = None  # best-effort if present in file


def _copilot_dir(workspace_job_dir: Path) -> Path:
    d = workspace_job_dir / ".copilot"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _plans_dir(workspace_job_dir: Path) -> Path:
    d = _copilot_dir(workspace_job_dir) / "plans"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _events_log(workspace_job_dir: Path) -> Path:
    d = _copilot_dir(workspace_job_dir)
    return d / "events.log"


def list_plans(workspace_job_dir: Path, limit: int = 50) -> List[PlanPointer]:
    plans_dir = _plans_dir(workspace_job_dir)
    if not plans_dir.exists():
        return []

    files = sorted(plans_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: List[PlanPointer] = []
    for p in files[: max(1, min(limit, 200))]:
        plan_id = p.stem
        created_ts = None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            created_ts = data.get("created_ts") or data.get("metadata", {}).get("created_ts")
        except Exception:
            created_ts = None
        out.append(PlanPointer(plan_id=plan_id, file_path=str(p), created_ts=created_ts))
    return out


def load_plan(workspace_job_dir: Path, plan_id: str) -> Dict[str, Any]:
    p = _plans_dir(workspace_job_dir) / f"{plan_id}.json"
    if not p.exists():
        raise FileNotFoundError(f"Plan not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def tail_events(workspace_job_dir: Path, limit: int = 200) -> List[Dict[str, Any]]:
    """
    Return last N JSONL events from .copilot/events.log (best-effort).
    Uses a simple full read for now (small). We can optimize to seek later.
    """
    log = _events_log(workspace_job_dir)
    if not log.exists():
        return []
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    lines = lines[-max(1, min(limit, 2000)) :]
    out: List[Dict[str, Any]] = []
    for ln in lines:
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out
