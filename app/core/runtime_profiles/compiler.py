from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.core.spec_schema import CopilotSpec
from app.core.compiler.contract_models import DataPipelineContract
from app.core.compiler.intelligence_models import ClusterProfile

from .registry import RuntimeProfileRegistry


def _default_profile_name(contract: DataPipelineContract) -> str:
    cloud = contract.compute_profile.cloud
    mode = contract.compute_profile.cluster_mode
    if cloud == "aws" and mode == "yarn":
        return "aws_emr_yarn_default"
    if cloud == "gcp" and mode == "yarn":
        return "gcp_dataproc_yarn_default"
    if cloud == "azure" and mode == "yarn":
        return "azure_synapse_yarn_default"
    if mode == "k8s":
        return "k8s_spark_default"
    return "aws_emr_yarn_default"


def compile_runtime_profile(
    *,
    project_root: Path,
    contract: DataPipelineContract,
    profile_name: Optional[str] = None,
    pricing_overrides: Optional[Dict[str, Any]] = None,
    spark_conf_overrides: Optional[Dict[str, Any]] = None,
) -> Tuple[dict, ClusterProfile]:
    """Returns (spark_conf_obj, cluster_profile) deterministically."""

    registry = RuntimeProfileRegistry(project_root)
    selected = profile_name or _default_profile_name(contract)
    rp = registry.get(selected)
    if rp is None:
        # Fallback: empty profile, deterministic.
        rp = registry.get("aws_emr_yarn_default")

    base_conf: Dict[str, str] = {str(k): str(v) for k, v in sorted((rp.spark_conf or {}).items())}

    # Apply spark conf overrides after profile (highest precedence here)
    for k, v in sorted((spark_conf_overrides or {}).items()):
        if k:
            base_conf[str(k)] = str(v)

    pricing = rp.pricing.model_dump()
    pricing.update({k: v for k, v in (pricing_overrides or {}).items() if k})
    rate = float(pricing.get("instance_hourly_rate") or 0.0)

    cd = rp.cluster_defaults
    cluster = ClusterProfile(
        executor_instances=int(cd.executor_instances),
        executor_cores=int(cd.executor_cores),
        executor_memory_gb=int(cd.executor_memory_gb),
        instance_hourly_rate=rate,
    )

    spark_conf_obj = {
        "conf": base_conf,
        "tags": [],
        "metadata": {
            "runtime_profile": rp.name,
            "cloud": rp.cloud,
            "cluster_mode": rp.cluster_mode,
            "spark_version": rp.spark_version,
            "pricing": pricing,
        },
    }

    return spark_conf_obj, cluster


def compile_spark_conf_for_contract(
    *,
    project_root: Path,
    contract: DataPipelineContract,
    spec: CopilotSpec,
    profile_name: Optional[str] = None,
    pricing_overrides: Optional[Dict[str, Any]] = None,
) -> Tuple[dict, ClusterProfile]:
    """Full merge order:

    runtime_profile.spark_conf
      -> spec-derived deterministic defaults (spark.app.name, partitionOverwriteMode, dyn alloc)
      -> spec.spark_conf_overrides (highest precedence)
    """

    spark_conf_overrides: Dict[str, Any] = {}
    spark_conf_overrides.update({k: v for k, v in (spec.spark_conf_overrides or {}).items() if k})

    spark_conf_obj, cluster = compile_runtime_profile(
        project_root=project_root,
        contract=contract,
        profile_name=profile_name,
        pricing_overrides=pricing_overrides,
        spark_conf_overrides={},
    )

    conf = spark_conf_obj.get("conf", {})
    conf["spark.app.name"] = str(spec.job_name)
    conf.setdefault("spark.sql.sources.partitionOverwriteMode", "dynamic")

    if spec.spark_dynamic_allocation:
        conf["spark.dynamicAllocation.enabled"] = "true"
        conf.setdefault("spark.dynamicAllocation.minExecutors", "1")
        conf.setdefault("spark.dynamicAllocation.maxExecutors", "50")
    else:
        conf["spark.dynamicAllocation.enabled"] = "false"

    for k, v in sorted(spark_conf_overrides.items()):
        conf[str(k)] = str(v)

    spark_conf_obj["tags"] = list(spec.tags or [])
    spark_conf_obj["metadata"].update(
        {
            "preset": spec.preset,
            "env": spec.env,
            "owner": spec.owner,
            "timezone": spec.timezone,
        }
    )

    return spark_conf_obj, cluster