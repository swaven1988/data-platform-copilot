import json
from app.core.spec_schema import CopilotSpec


def render_spark_conf(spec: CopilotSpec) -> str:
    # Minimal, safe defaults for MVP. Later we can add profiles and tuning policies.
    conf = {
        "spark.app.name": spec.job.name,
        "spark.sql.adaptive.enabled": "true",
        "spark.sql.shuffle.partitions": "400",
        "spark.dynamicAllocation.enabled": str(spec.spark.dynamic_allocation).lower(),
        "spark.dynamicAllocation.minExecutors": "2",
        "spark.dynamicAllocation.maxExecutors": "50",
    }
    return json.dumps(conf, indent=2, sort_keys=True)
