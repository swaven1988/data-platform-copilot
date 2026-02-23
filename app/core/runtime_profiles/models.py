from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Dict, Optional, Literal


CloudVendor = Literal["aws", "azure", "gcp", "onprem"]
ClusterMode = Literal["yarn", "k8s", "standalone"]


class PricingHints(BaseModel):
    # Vendor-neutral: caller can inject their own exact pricing.
    # These are defaults for demo/testing and must remain deterministic.
    instance_type: Optional[str] = None
    instance_hourly_rate: Optional[float] = None


class ClusterDefaults(BaseModel):
    executor_instances: int = 4
    executor_cores: int = 4
    executor_memory_gb: int = 16


class RuntimeProfile(BaseModel):
    name: str
    cloud: CloudVendor
    cluster_mode: ClusterMode
    spark_version: Optional[str] = None

    spark_conf: Dict[str, str] = Field(default_factory=dict)
    cluster_defaults: ClusterDefaults = Field(default_factory=ClusterDefaults)
    pricing: PricingHints = Field(default_factory=PricingHints)

    description: Optional[str] = None