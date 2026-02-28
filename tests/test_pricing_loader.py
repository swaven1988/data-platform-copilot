"""
Phase G — Pricing loader tests.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.cost.pricing_loader import load_pricing_overrides, _parse_override_dict


# ---------------------------------------------------------------------------
# _parse_override_dict
# ---------------------------------------------------------------------------

def test_parse_valid_dict():
    raw = {"aws/us-east-1": 0.03, "gcp/us-central1": "0.04"}
    result = _parse_override_dict(raw)
    assert result[("aws", "us-east-1")] == pytest.approx(0.03)
    assert result[("gcp", "us-central1")] == pytest.approx(0.04)


def test_parse_skips_invalid_key_format(caplog):
    raw = {"invalid-key-no-slash": 0.05, "aws/us-east-1": 0.035}
    result = _parse_override_dict(raw)
    assert ("aws", "us-east-1") in result
    assert len(result) == 1  # invalid key skipped


def test_parse_skips_non_numeric_value(caplog):
    raw = {"aws/us-east-1": "not_a_number"}
    result = _parse_override_dict(raw)
    assert result == {}


# ---------------------------------------------------------------------------
# load_pricing_overrides — file-based tests
# ---------------------------------------------------------------------------

def test_load_returns_empty_when_file_missing(tmp_path):
    path = tmp_path / "nonexistent.yaml"
    result = load_pricing_overrides(path)
    assert result == {}


def test_load_valid_json_file(tmp_path):
    f = tmp_path / "pricing.json"
    f.write_text(json.dumps({"aws/us-east-1": 0.030, "k8s/default": 0.038}), encoding="utf-8")
    result = load_pricing_overrides(f)
    assert result[("aws", "us-east-1")] == pytest.approx(0.030)
    assert result[("k8s", "default")] == pytest.approx(0.038)


def test_load_valid_yaml_file(tmp_path):
    f = tmp_path / "pricing.yaml"
    f.write_text("aws/us-east-1: 0.031\ngcp/us-central1: 0.042\n", encoding="utf-8")
    result = load_pricing_overrides(f)
    assert result[("aws", "us-east-1")] == pytest.approx(0.031)


def test_load_malformed_file_returns_empty(tmp_path, caplog):
    f = tmp_path / "bad.yaml"
    f.write_text("this: is: not: valid: yaml:\n  {{{{", encoding="utf-8")
    result = load_pricing_overrides(f)
    assert result == {}


def test_load_non_mapping_file_returns_empty(tmp_path, caplog):
    f = tmp_path / "list.json"
    f.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    result = load_pricing_overrides(f)
    assert result == {}


def test_load_uses_env_var(tmp_path, monkeypatch):
    f = tmp_path / "env_pricing.json"
    f.write_text(json.dumps({"azure/eastus": 0.040}), encoding="utf-8")
    monkeypatch.setenv("COPILOT_PRICING_FILE", str(f))
    result = load_pricing_overrides()   # no explicit path
    assert result[("azure", "eastus")] == pytest.approx(0.040)
