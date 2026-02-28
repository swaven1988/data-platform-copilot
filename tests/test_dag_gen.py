"""
Phase F — Airflow DAG generator unit tests.
"""
from __future__ import annotations

import ast
import pytest

from app.core.generators.dag_gen import (
    generate_airflow_dag,
    render_airflow_dag,
    render_airflow_dag_v2,
)
from app.core.spec_schema import CopilotSpec


def _make_spec(**overrides) -> CopilotSpec:
    defaults = dict(
        job_name="test_job",
        source_table="raw.events",
        target_table="curated.events",
        partition_column="event_date",
        write_mode="overwrite",
        preset="copy",
        language="pyspark",
        owner="data-team",
        description="Test pipeline",
        schedule="0 6 * * *",
        timezone="UTC",
        env="dev",
        tags=["copilot", "test"],
    )
    defaults.update(overrides)
    return CopilotSpec(**defaults)


def test_dag_output_has_one_file():
    files = generate_airflow_dag(_make_spec())
    assert len(files) == 1


def test_dag_file_key_matches_job_name():
    files = generate_airflow_dag(_make_spec(job_name="my_pipeline"))
    assert "dags/my_pipeline_pipeline.py" in files


def test_dag_code_is_valid_python():
    files = generate_airflow_dag(_make_spec())
    code = next(iter(files.values()))
    try:
        ast.parse(code)
    except SyntaxError as exc:
        pytest.fail(f"DAG generator produced invalid Python: {exc}")


def test_dag_code_contains_dag_id():
    files = generate_airflow_dag(_make_spec(job_name="my_job"))
    code = next(iter(files.values()))
    assert "my_job_pipeline" in code


def test_dag_code_contains_owner():
    files = generate_airflow_dag(_make_spec(owner="analytics-team"))
    code = next(iter(files.values()))
    assert "analytics-team" in code


def test_dag_code_contains_schedule():
    files = generate_airflow_dag(_make_spec(schedule="0 2 * * 1"))
    code = next(iter(files.values()))
    assert "0 2 * * 1" in code


def test_dag_code_contains_tags():
    files = generate_airflow_dag(_make_spec(tags=["etl", "nightly"]))
    code = next(iter(files.values()))
    assert "etl" in code
    assert "nightly" in code


def test_dag_code_contains_env():
    files = generate_airflow_dag(_make_spec(env="prod"))
    code = next(iter(files.values()))
    assert "--env prod" in code


def test_v1_v2_entrypoints_produce_same_output():
    spec = _make_spec()
    assert render_airflow_dag(spec) == generate_airflow_dag(spec)
    assert render_airflow_dag_v2(spec) == generate_airflow_dag(spec)
