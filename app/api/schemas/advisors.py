from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AdvisorsRunConfigModel(BaseModel):
    enabled: Optional[List[str]] = Field(default=None, description="Allowlist. If set, only these run.")
    disabled: List[str] = Field(default_factory=list)
    options: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    force: bool = False


class AdvisorsRunRequest(BaseModel):
    context: Dict[str, Any] = Field(default_factory=dict)
    advisors: AdvisorsRunConfigModel = Field(default_factory=AdvisorsRunConfigModel)


class AdvisorFindingModel(BaseModel):
    plugin: str
    level: str
    code: str
    message: str
    data: Dict[str, Any] | None = None


class AdvisorsRunResponse(BaseModel):
    plugin_fingerprint: str
    findings: List[AdvisorFindingModel]
