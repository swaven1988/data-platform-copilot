from __future__ import annotations

from typing import Dict

from app.core.spec_schema import CopilotSpec


def generate_airflow_dag(spec: CopilotSpec) -> Dict[str, str]:
    """
    Canonical Airflow DAG generator.

    Returns:
      {"dags/<job_name>_pipeline.py": "<python code>"}
    """
    dag_id = f"{spec.job_name}_pipeline"
    dag_file = f"dags/{dag_id}.py"

    # Keep it simple: BashOperator spark-submit.
    # Enterprise can swap to SparkSubmitOperator / LivyOperator / K8sPodOperator later.
    cmd = (
        "spark-submit "
        "--properties-file configs/spark_conf_default.json "
        f"jobs/pyspark/src/{spec.job_name}.py "
        f"--env {spec.env}"
    )

    code = f'''\
"""
COPILOT-GENERATED AIRFLOW DAG
job_name: {spec.job_name}
preset: {spec.preset}
schedule: {spec.schedule}
timezone: {spec.timezone}
"""

from __future__ import annotations

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator


DEFAULT_ARGS = {{
    "owner": {spec.owner!r},
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=10),
}}


with DAG(
    dag_id={dag_id!r},
    default_args=DEFAULT_ARGS,
    description={spec.description!r},
    schedule={spec.schedule!r},
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags={list(spec.tags or [])!r},
) as dag:

    run_spark_job = BashOperator(
        task_id="run_spark_job",
        bash_command={cmd!r},
    )
'''
    return {dag_file: code}


# -------------------------------------------------------------------
# Stable public API surface (V1 + V2)
# -------------------------------------------------------------------
def render_airflow_dag(spec: CopilotSpec) -> Dict[str, str]:
    """Build V1 compatibility entrypoint."""
    return generate_airflow_dag(spec)


def render_airflow_dag_v2(spec: CopilotSpec) -> Dict[str, str]:
    """Build V2 compatibility entrypoint."""
    return generate_airflow_dag(spec)
