from typing import List, Optional
from pydantic import BaseModel, Field
from hashlib import sha256
import json


class SourceSpec(BaseModel):
    type: str
    location: str
    format: str


class TransformationSpec(BaseModel):
    name: str
    type: str
    config: dict = Field(default_factory=dict)


class SinkSpec(BaseModel):
    type: str
    location: str
    format: str


class DQRule(BaseModel):
    rule_type: str
    column: Optional[str] = None
    threshold: Optional[float] = None


class SLASpec(BaseModel):
    max_runtime_minutes: Optional[int]
    freshness_minutes: Optional[int]


class DataPipelineContract(BaseModel):
    job_name: str
    source: SourceSpec
    transformations: List[TransformationSpec]
    sink: SinkSpec
    dq_rules: List[DQRule] = Field(default_factory=list)
    sla: Optional[SLASpec] = None

    def deterministic_hash(self) -> str:
        raw = json.dumps(self.model_dump(), sort_keys=True)
        return sha256(raw.encode()).hexdigest()