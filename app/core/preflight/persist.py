# app/core/preflight/persist.py

import json
from pathlib import Path
from .models import PreflightReport


def _preflight_dir(workspace_dir: Path) -> Path:
    d = workspace_dir / ".copilot" / "preflight"
    d.mkdir(parents=True, exist_ok=True)
    return d


def persist_report(report: PreflightReport, workspace_dir: Path) -> str:
    """Persist a preflight report to workspace_dir/.copilot/preflight/<hash>.json."""
    path = _preflight_dir(workspace_dir) / f"{report.preflight_hash}.json"
    path.write_text(json.dumps(report.model_dump(), indent=2), encoding="utf-8")
    return str(path)


def load_report(job_name: str, preflight_hash: str, workspace_dir: Path):
    """Load a preflight report; returns None if not found."""
    path = _preflight_dir(workspace_dir) / f"{preflight_hash}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
