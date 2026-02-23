from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict
from hashlib import sha256
import json


CloudVendor = Literal["aws", "azure", "gcp", "onprem"]
ClusterMode = Literal["yarn", "k8s", "standalone"]


class ComputeProfile(BaseModel):
    engine: Literal["spark"]
    spark_version: str
    cluster_mode: ClusterMode
    cloud: CloudVendor


class SourceSpec(BaseModel):
    type: str
    location: str
    format: str


class TransformationSpec(BaseModel):
    name: str
    type: str
    config: Dict = Field(default_factory=dict)


class SinkSpec(BaseModel):
    type: str
    location: str
    format: str


class SLASpec(BaseModel):
    max_runtime_minutes: Optional[int] = None
    freshness_minutes: Optional[int] = None


class DataPipelineContract(BaseModel):
    job_name: str
    compute_profile: ComputeProfile
    source: SourceSpec
    transformations: List[TransformationSpec]
    sink: SinkSpec
    sla: Optional[SLASpec] = None
    policy_profile: str = "default"

    def deterministic_hash(self) -> str:
        raw = json.dumps(
            self.model_dump(),
            sort_keys=True,
            separators=(",", ":")
        )
        return sha256(raw.encode()).hexdigest()