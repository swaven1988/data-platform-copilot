"""
Phase H — Spark Optimizer API endpoint.

Exposes recommend_spark_config() as GET /advisors/spark-config.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

from app.core.compiler.spark_optimizer import recommend_spark_config

router = APIRouter(prefix="/advisors", tags=["Advisors"])


@router.get("/spark-config")
def get_spark_config_recommendation(
    data_gb: float = Query(..., description="Estimated input data size in GB", ge=0),
    joins: int = Query(0, description="Number of join operations in the job", ge=0),
    sla_minutes: Optional[int] = Query(
        None,
        description="SLA deadline in minutes (used to enable speculation for tight SLAs)",
        ge=0,
    ),
) -> Dict[str, Any]:
    """
    Returns a recommended Spark executor configuration based on
    data size, join complexity, and SLA constraints.
    """
    config = recommend_spark_config(
        data_gb=data_gb,
        joins=joins,
        sla_minutes=sla_minutes,
    )
    return {
        "config": config,
        "data_gb": data_gb,
        "joins": joins,
        "sla_minutes": sla_minutes,
    }
