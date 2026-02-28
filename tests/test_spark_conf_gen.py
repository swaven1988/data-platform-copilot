"""
Phase F — Spark configuration generator unit tests.
"""
from __future__ import annotations

import pytest

from app.core.generators.spark_conf_gen import (
    generate_spark_conf,
    render_spark_conf,
    render_spark_conf_v2,
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
    )
    defaults.update(overrides)
    return CopilotSpec(**defaults)


def test_output_has_conf_tags_metadata_keys():
    result = generate_spark_conf(_make_spec())
    assert "conf" in result
    assert "tags" in result
    assert "metadata" in result


def test_app_name_equals_job_name():
    result = generate_spark_conf(_make_spec(job_name="my_job"))
    assert result["conf"]["spark.app.name"] == "my_job"


def test_dynamic_allocation_enabled_by_default():
    result = generate_spark_conf(_make_spec(spark_dynamic_allocation=True))
    assert result["conf"]["spark.dynamicAllocation.enabled"] == "true"
    assert "spark.dynamicAllocation.minExecutors" in result["conf"]
    assert "spark.dynamicAllocation.maxExecutors" in result["conf"]


def test_dynamic_allocation_disabled():
    result = generate_spark_conf(_make_spec(spark_dynamic_allocation=False))
    assert result["conf"]["spark.dynamicAllocation.enabled"] == "false"


def test_overrides_take_precedence():
    spec = _make_spec(spark_conf_overrides={"spark.executor.memory": "32g"})
    result = generate_spark_conf(spec)
    assert result["conf"]["spark.executor.memory"] == "32g"


def test_tags_match_spec():
    spec = _make_spec(tags=["etl", "batch"])
    result = generate_spark_conf(spec)
    assert "etl" in result["tags"]
    assert "batch" in result["tags"]


def test_metadata_contains_preset_env_owner():
    spec = _make_spec(preset="copy", env="prod", owner="data-team")
    meta = generate_spark_conf(spec)["metadata"]
    assert meta["preset"] == "copy"
    assert meta["env"] == "prod"
    assert meta["owner"] == "data-team"


def test_v1_v2_entrypoints_produce_same_output():
    spec = _make_spec()
    assert render_spark_conf(spec) == generate_spark_conf(spec)
    assert render_spark_conf_v2(spec) == generate_spark_conf(spec)


def test_partition_overwrite_mode_set():
    result = generate_spark_conf(_make_spec())
    assert result["conf"]["spark.sql.sources.partitionOverwriteMode"] == "dynamic"
