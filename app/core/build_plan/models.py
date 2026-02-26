from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Literal


StepType = Literal[
    "AcquireBaseline",
    "GenerateArtifacts",
    "MaterializeWorkspace",
    "FinalizeBaseline",
]


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    step_type: StepType
    depends_on: List[str] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    cache_key: Optional[str] = None


@dataclass(frozen=True)
class BuildPlan:
    plan_version: str
    spec_hash: str
    job_name: str
    baseline_ref: Optional[str]
    plugin_fingerprint: str = "core-only"
    steps: List[PlanStep] = field(default_factory=list)
    expected_files: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def compute_plan_id(self) -> str:
        payload = {
            "plan_version": self.plan_version,
            "spec_hash": self.spec_hash,
            "job_name": self.job_name,
            "baseline_ref": self.baseline_ref,
            "plugin_fingerprint": self.plugin_fingerprint,
            "steps": [
                {
                    "step_id": s.step_id,
                    "step_type": s.step_type,
                    "depends_on": s.depends_on,
                    "inputs": s.inputs,
                    "cache_key": s.cache_key,
                }
                for s in self.steps
            ],
            "expected_files": self.expected_files,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
