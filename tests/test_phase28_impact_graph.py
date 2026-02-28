"""
Phase 28 — Impact Graph API integration tests.

Tests GET /advisors/impact-graph:
  - 404 when workspace dir does not exist
  - 404 when plan JSON does not exist
  - 200 with correct {nodes, edges, finding_count} shape when fixture plan present
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _make_plan_json(job_name: str) -> dict:
    """Minimal valid BuildPlan JSON that impact_graph._load_plan() can parse."""
    return {
        "plan_version": "v1",
        "spec_hash":    "abc123",
        "job_name":     job_name,
        "baseline_ref": None,
        "plugin_fingerprint": "core-only",
        "steps": [],
        "expected_files": [],
        "metadata": {},
    }


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------

def test_impact_graph_404_missing_workspace(monkeypatch, tmp_path):
    """Returns 404 when workspace dir does not exist."""
    monkeypatch.setenv("COPILOT_TOKEN", "dev_admin_token")
    r = client.get(
        "/api/v1/advisors/impact-graph",
        params={"job_name": "nonexistent_job_xyz", "plan_id": "someid"},
        headers={"Authorization": "Bearer dev_admin_token", "X-Tenant-ID": "default"},
    )
    assert r.status_code == 404


def test_impact_graph_404_missing_plan(tmp_path, monkeypatch):
    """Returns 404 when workspace exists but plan JSON is absent."""
    # Patch WORKSPACE_ROOT used by the endpoint
    import app.api.endpoints.impact_graph as ig_mod
    monkeypatch.setattr(ig_mod, "WORKSPACE_ROOT", tmp_path)

    job_dir = tmp_path / "test_job"
    job_dir.mkdir()

    r = client.get(
        "/api/v1/advisors/impact-graph",
        params={"job_name": "test_job", "plan_id": "missing_plan_id"},
        headers={"Authorization": "Bearer dev_admin_token", "X-Tenant-ID": "default"},
    )
    assert r.status_code == 404


def test_impact_graph_returns_valid_shape(tmp_path, monkeypatch):
    """Happy path: plan JSON present → {nodes, edges, finding_count} returned."""
    import app.api.endpoints.impact_graph as ig_mod
    monkeypatch.setattr(ig_mod, "WORKSPACE_ROOT", tmp_path)

    job_name = "impact_test_job"
    plan_id  = "plan_aabbcc"
    job_dir  = tmp_path / job_name
    plan_dir = job_dir / ".copilot" / "plans"
    plan_dir.mkdir(parents=True)
    (plan_dir / f"{plan_id}.json").write_text(
        json.dumps(_make_plan_json(job_name)), encoding="utf-8"
    )

    r = client.get(
        "/api/v1/advisors/impact-graph",
        params={"job_name": job_name, "plan_id": plan_id},
        headers={"Authorization": "Bearer dev_admin_token", "X-Tenant-ID": "default"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "nodes" in body
    assert "edges" in body
    assert "finding_count" in body
    assert body["plan_id"] == plan_id
    assert body["job_name"] == job_name
