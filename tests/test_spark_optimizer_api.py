"""
Phase H — Spark Optimizer API endpoint tests.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)
HEADERS = {"Authorization": "Bearer dev_admin_token", "X-Tenant-ID": "default"}
URL = "/advisors/spark-config"


def test_spark_config_happy_path():
    r = client.get(URL, params={"data_gb": 100, "joins": 2, "sla_minutes": 60}, headers=HEADERS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "config" in body
    assert body["data_gb"] == 100
    assert body["joins"] == 2
    assert body["sla_minutes"] == 60


def test_spark_config_contains_required_keys():
    r = client.get(URL, params={"data_gb": 50, "joins": 1}, headers=HEADERS)
    assert r.status_code == 200
    cfg = r.json()["config"]
    assert "spark.executor.instances" in cfg
    assert "spark.executor.cores" in cfg
    assert "spark.executor.memory" in cfg
    assert "spark.sql.shuffle.partitions" in cfg


def test_speculation_enabled_for_tight_sla():
    r = client.get(URL, params={"data_gb": 50, "joins": 0, "sla_minutes": 15}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["config"].get("spark.speculation") == "true"


def test_no_speculation_for_relaxed_sla():
    r = client.get(URL, params={"data_gb": 50, "joins": 0, "sla_minutes": 60}, headers=HEADERS)
    assert r.status_code == 200
    assert "spark.speculation" not in r.json()["config"]


def test_sla_optional_defaults_to_none():
    r = client.get(URL, params={"data_gb": 20, "joins": 0}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["sla_minutes"] is None


def test_missing_data_gb_returns_422():
    r = client.get(URL, params={"joins": 1}, headers=HEADERS)
    assert r.status_code == 422


def test_negative_data_gb_returns_422():
    r = client.get(URL, params={"data_gb": -10, "joins": 0}, headers=HEADERS)
    assert r.status_code == 422


def test_negative_joins_returns_422():
    r = client.get(URL, params={"data_gb": 50, "joins": -1}, headers=HEADERS)
    assert r.status_code == 422
