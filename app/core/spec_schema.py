from pydantic import BaseModel
from typing import Optional


class JobSpec(BaseModel):
    name: str
    description: Optional[str]
    language: str


class ScheduleSpec(BaseModel):
    cron: str
    timezone: str


class SourceSpec(BaseModel):
    type: str
    identifier: str


class TargetSpec(BaseModel):
    type: str
    identifier: str
    write_mode: str
    partition_column: str


class SparkSpec(BaseModel):
    profile: str
    dynamic_allocation: bool = True


class DQSpec(BaseModel):
    enabled: bool = False
    mode: str = "none"


class MetadataSpec(BaseModel):
    owner: str
    environment: str
    created_by: str
    version: int


class CopilotSpec(BaseModel):
    job: JobSpec
    schedule: ScheduleSpec
    source: SourceSpec
    target: TargetSpec
    spark: SparkSpec
    dq: DQSpec
    metadata: MetadataSpec
