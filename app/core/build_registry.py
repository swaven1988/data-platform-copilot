from __future__ import annotations

import json
import hashlib
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.core.spec_schema import CopilotSpec


class BuildRegistry:
    """
    Tracks build lifecycle per workspace job.

    Stored at:
      workspace/<job_name>/.copilot_meta.json
    """

    def __init__(self, workspace_root: Path, job_name: str):
        self.workspace_root = workspace_root
        self.job_name = job_name
        self.job_dir = workspace_root / job_name
        self.meta_file = self.job_dir / ".copilot_meta.json"

    # ----------------------------------------
    # Spec Hash
    # ----------------------------------------
    @staticmethod
    def compute_spec_hash(spec: CopilotSpec) -> str:
        return hashlib.sha256(
            json.dumps(spec.model_dump(), sort_keys=True).encode("utf-8")
        ).hexdigest()

    # ----------------------------------------
    # Load / Save
    # ----------------------------------------
    def load(self) -> Dict[str, Any]:
        if not self.meta_file.exists():
            return {
                "job_name": self.job_name,
                "builds": [],
                "current_build_id": None,
                "spec_hash": None,
            }

        with open(self.meta_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: Dict[str, Any]) -> None:
        self.job_dir.mkdir(parents=True, exist_ok=True)
        with open(self.meta_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # ----------------------------------------
    # Should Rebuild?
    # ----------------------------------------
    def should_rebuild(self, new_hash: str) -> bool:
        meta = self.load()
        return meta.get("spec_hash") != new_hash

    # ----------------------------------------
    # Register Build
    # ----------------------------------------
    def register_build(
        self,
        spec_hash: str,
        baseline_commit: Optional[str],
        confidence: Optional[float] = None,
        plan_id: Optional[str] = None,
        plugin_fingerprint: Optional[str] = None,
    ) -> None:

        meta = self.load()

        build_id = str(uuid.uuid4())

        build_entry = {
            "build_id": build_id,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "spec_hash": spec_hash,
            "baseline_commit": baseline_commit,
            "confidence": confidence,
            "plan_id": plan_id,
            "plugin_fingerprint": plugin_fingerprint,
        }

        meta.setdefault("builds", [])
        meta["builds"].append(build_entry)
        meta["current_build_id"] = build_id
        meta["spec_hash"] = spec_hash

        self._save(meta)

