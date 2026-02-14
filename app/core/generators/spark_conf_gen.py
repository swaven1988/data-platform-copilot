from __future__ import annotations

from typing import Any, Dict

from app.core.spec_schema import CopilotSpec


def generate_spark_conf(spec: CopilotSpec) -> Dict[str, Any]:
    """
    Canonical Spark configuration generator.

    Returns JSON-serializable dict:

    {
        "conf": { ...spark key-values... },
        "tags": [...],
        "metadata": {...}
    }
    """

    conf: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Deterministic defaults
    # ------------------------------------------------------------------
    conf["spark.app.name"] = str(spec.job_name)
    conf["spark.sql.sources.partitionOverwriteMode"] = "dynamic"

    # Dynamic allocation
    if spec.spark_dynamic_allocation:
        conf["spark.dynamicAllocation.enabled"] = "true"
        conf.setdefault("spark.dynamicAllocation.minExecutors", "1")
        conf.setdefault("spark.dynamicAllocation.maxExecutors", "50")
    else:
        conf["spark.dynamicAllocation.enabled"] = "false"

    # ------------------------------------------------------------------
    # Apply user overrides last (highest precedence)
    # ------------------------------------------------------------------
    for k, v in sorted((spec.spark_conf_overrides or {}).items()):
        if k:
            conf[str(k)] = str(v)

    # ------------------------------------------------------------------
    # Final structure (stable contract)
    # ------------------------------------------------------------------
    return {
        "conf": conf,
        "tags": list(spec.tags or []),
        "metadata": {
            "preset": spec.preset,
            "env": spec.env,
            "owner": spec.owner,
            "timezone": spec.timezone,
        },
    }


# -------------------------------------------------------------------
# Stable public API surface (V1 + V2)
# -------------------------------------------------------------------
def render_spark_conf(spec: CopilotSpec) -> Dict[str, Any]:
    """Build V1 compatibility entrypoint."""
    return generate_spark_conf(spec)


def render_spark_conf_v2(spec: CopilotSpec) -> Dict[str, Any]:
    """Build V2 compatibility entrypoint."""
    return generate_spark_conf(spec)
