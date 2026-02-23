from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from hashlib import sha256
import json


class LogicalNode(BaseModel):
    node_id: str
    node_type: str
    config: Dict = Field(default_factory=dict)


class PhysicalStage(BaseModel):
    stage_id: str
    depends_on: List[str] = Field(default_factory=list)
    shuffle_boundary: bool = False
    estimated_parallelism: Optional[int] = None


class PlanMetadata(BaseModel):
    contract_hash: str
    plugin_fingerprint: str
    policy_profile: str


class CompilerPlan(BaseModel):
    job_name: str
    metadata: PlanMetadata
    logical_dag: List[LogicalNode]
    physical_stages: List[PhysicalStage]

    def deterministic_hash(self) -> str:
        raw = json.dumps(
            self.model_dump(),
            sort_keys=True,
            separators=(",", ":")
        )
        return sha256(raw.encode()).hexdigest()