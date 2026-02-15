from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BuildEventOut(BaseModel):
    event_type: str
    ts: str
    job_name: str
    spec_hash: str
    plan_id: Optional[str] = None
    step_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class PolicyResultOut(BaseModel):
    status: str
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class BuildV2Response(BaseModel):
    message: str
    job_name: str
    spec_hash: str
    skipped: bool

    plan_id: Optional[str] = None
    workspace_dir: Optional[str] = None
    files: List[str] = Field(default_factory=list)
    baseline_commit: Optional[str] = None

    events: List[Dict[str, Any]] = Field(default_factory=list)
    advisor_findings: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: Optional[float] = None
    policy_results: List[Dict[str, Any]] = Field(default_factory=list)


class BuildIntentDryRunResponse(BaseModel):
    message: str
    parsed_spec: Dict[str, Any]
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    spec_hash: str
    confidence: Optional[float] = None
    plugin_fingerprint: str
    advisor_findings: List[Dict[str, Any]] = Field(default_factory=list)
    explain: Optional[Any] = None


class BuildIntentBuildResponse(BaseModel):
    message: str
    parsed_spec: Dict[str, Any]
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    spec_hash: str
    confidence: Optional[float] = None
    plugin_fingerprint: str
    advisor_findings: List[Dict[str, Any]] = Field(default_factory=list)
    build_result: Dict[str, Any]
    explain: Optional[Any] = None
