"""
Phase F — Spark optimizer heuristic unit tests.
"""
from __future__ import annotations

import pytest

from app.core.compiler.spark_optimizer import recommend_spark_config


def test_returns_required_keys():
    cfg = recommend_spark_config(data_gb=100, joins=2, sla_minutes=60)
    assert "spark.executor.instances" in cfg
    assert "spark.executor.cores" in cfg
    assert "spark.executor.memory" in cfg
    assert "spark.sql.shuffle.partitions" in cfg


def test_executor_count_scales_with_data():
    cfg_small = recommend_spark_config(data_gb=10,  joins=0, sla_minutes=60)
    cfg_large = recommend_spark_config(data_gb=100, joins=0, sla_minutes=60)
    assert cfg_large["spark.executor.instances"] >= cfg_small["spark.executor.instances"]


def test_minimum_executors_is_two():
    cfg = recommend_spark_config(data_gb=0.1, joins=0, sla_minutes=60)
    assert cfg["spark.executor.instances"] >= 2


def test_executor_formula():
    cfg = recommend_spark_config(data_gb=50, joins=0, sla_minutes=60)
    expected = max(2, int(50 / 5))
    assert cfg["spark.executor.instances"] == expected


@pytest.mark.parametrize("joins,expected_cores", [(0, 4), (1, 4), (2, 4), (3, 6), (5, 6)])
def test_cores_depend_on_join_count(joins, expected_cores):
    cfg = recommend_spark_config(data_gb=50, joins=joins, sla_minutes=60)
    assert cfg["spark.executor.cores"] == expected_cores


def test_small_data_uses_8g_memory():
    cfg = recommend_spark_config(data_gb=10, joins=0, sla_minutes=60)
    assert cfg["spark.executor.memory"] == "8g"


def test_large_data_uses_14g_memory():
    cfg = recommend_spark_config(data_gb=100, joins=0, sla_minutes=60)
    assert cfg["spark.executor.memory"] == "14g"


def test_shuffle_partitions_scale_with_data():
    cfg_small = recommend_spark_config(data_gb=10,  joins=0, sla_minutes=60)
    cfg_large = recommend_spark_config(data_gb=200, joins=0, sla_minutes=60)
    assert cfg_large["spark.sql.shuffle.partitions"] > cfg_small["spark.sql.shuffle.partitions"]


def test_shuffle_partitions_minimum_200():
    cfg = recommend_spark_config(data_gb=0.1, joins=0, sla_minutes=60)
    assert cfg["spark.sql.shuffle.partitions"] >= 200


def test_speculation_enabled_for_tight_sla():
    cfg = recommend_spark_config(data_gb=50, joins=0, sla_minutes=20)
    assert cfg.get("spark.speculation") == "true"


def test_no_speculation_for_relaxed_sla():
    cfg = recommend_spark_config(data_gb=50, joins=0, sla_minutes=30)
    assert "spark.speculation" not in cfg


def test_no_speculation_when_sla_none():
    cfg = recommend_spark_config(data_gb=50, joins=0, sla_minutes=None)
    assert "spark.speculation" not in cfg
