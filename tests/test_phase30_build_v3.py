"""
Phase 30 — Build V3 API integration tests.

Tests POST /api/v3/build/run:
  - Happy path: returns build_id, decision, lineage
  - Policy block: BuildGate raises PermissionError → 403
  - Bad hashes: BuildGate raises ValueError → 400
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)

HEADERS = {"Authorization": "Bearer dev_admin_token", "X-Tenant-ID": "default"}
BASE_PARAMS = {
    "job_name":          "test_job",
    "contract_hash":     "chash_aabbcc",
    "plan_hash":         "phash_112233",
    "intelligence_hash": "ihash_445566",
    "policy_eval_hash":  "pehash_778899",
}


def _mock_verdict(decision: str = "proceed"):
    return {"decision": decision, "policy_profile": "default", "reasons": []}


def _mock_lineage():
    return {"build_id": "ignored", "hashes": BASE_PARAMS}


def test_build_v3_happy_path():
    with (
        patch("app.api.endpoints.build_v3.gate") as mock_gate,
    ):
        mock_gate.validate_inputs.return_value = _mock_verdict("proceed")
        mock_gate.record_lineage.return_value  = _mock_lineage()

        r = client.post("/api/v3/build/run", params=BASE_PARAMS, headers=HEADERS)

    assert r.status_code == 200, r.text
    body = r.json()
    assert "build_id" in body
    assert body["decision"] == "proceed"
    assert "lineage" in body


def test_build_v3_permission_error_returns_403():
    with patch("app.api.endpoints.build_v3.gate") as mock_gate:
        mock_gate.validate_inputs.side_effect = PermissionError("policy blocked")

        r = client.post("/api/v3/build/run", params=BASE_PARAMS, headers=HEADERS)

    assert r.status_code == 403
    assert "policy blocked" in r.json()["detail"]


def test_build_v3_value_error_returns_400():
    with patch("app.api.endpoints.build_v3.gate") as mock_gate:
        mock_gate.validate_inputs.side_effect = ValueError("bad hash")

        r = client.post("/api/v3/build/run", params=BASE_PARAMS, headers=HEADERS)

    assert r.status_code == 400
    assert "bad hash" in r.json()["detail"]


@pytest.mark.parametrize("decision", [" proceed ", "ALLOW", "ApPrOvEd"])
def test_build_v3_runner_invoked_for_normalized_allow_decisions(monkeypatch, tmp_path, decision):
    from app.api.endpoints import build_v3 as build_v3_mod

    monkeypatch.setattr(build_v3_mod, "WORKSPACE_ROOT", tmp_path)

    workspace_job_dir = tmp_path / BASE_PARAMS["job_name"]
    workspace_job_dir.mkdir(parents=True, exist_ok=True)
    (workspace_job_dir / "copilot_spec.yaml").write_text(
        f"job_name: {BASE_PARAMS['job_name']}\n",
        encoding="utf-8",
    )

    with (
        patch("app.api.endpoints.build_v3.gate") as mock_gate,
        patch(
            "app.api.endpoints.build_v2_impl.build_v2_from_spec",
            return_value={"status": "ok"},
        ) as mock_runner,
    ):
        mock_gate.validate_inputs.return_value = _mock_verdict(decision)
        mock_gate.record_lineage.return_value = _mock_lineage()

        r = client.post("/api/v3/build/run", params=BASE_PARAMS, headers=HEADERS)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["build_result"] == {"status": "ok"}
    mock_runner.assert_called_once()

    args, kwargs = mock_runner.call_args
    assert args[0].job_name == BASE_PARAMS["job_name"]
    assert kwargs["write_spec_yaml"] is False
    assert kwargs["contract_hash"] == BASE_PARAMS["contract_hash"]


def test_build_v3_runner_not_invoked_for_non_allow_decision(monkeypatch, tmp_path):
    from app.api.endpoints import build_v3 as build_v3_mod

    monkeypatch.setattr(build_v3_mod, "WORKSPACE_ROOT", tmp_path)

    workspace_job_dir = tmp_path / BASE_PARAMS["job_name"]
    workspace_job_dir.mkdir(parents=True, exist_ok=True)
    (workspace_job_dir / "copilot_spec.yaml").write_text(
        f"job_name: {BASE_PARAMS['job_name']}\n",
        encoding="utf-8",
    )

    with (
        patch("app.api.endpoints.build_v3.gate") as mock_gate,
        patch("app.api.endpoints.build_v2_impl.build_v2_from_spec") as mock_runner,
    ):
        mock_gate.validate_inputs.return_value = _mock_verdict("warn")
        mock_gate.record_lineage.return_value = _mock_lineage()

        r = client.post("/api/v3/build/run", params=BASE_PARAMS, headers=HEADERS)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["build_result"] is None
    mock_runner.assert_not_called()


def test_build_v3_runner_failure_returns_safe_error_payload(monkeypatch, tmp_path):
    from app.api.endpoints import build_v3 as build_v3_mod

    monkeypatch.setattr(build_v3_mod, "WORKSPACE_ROOT", tmp_path)

    workspace_job_dir = tmp_path / BASE_PARAMS["job_name"]
    workspace_job_dir.mkdir(parents=True, exist_ok=True)
    (workspace_job_dir / "copilot_spec.yaml").write_text(
        f"job_name: {BASE_PARAMS['job_name']}\n",
        encoding="utf-8",
    )

    with (
        patch("app.api.endpoints.build_v3.gate") as mock_gate,
        patch(
            "app.api.endpoints.build_v2_impl.build_v2_from_spec",
            side_effect=RuntimeError("internal-path/secret"),
        ),
    ):
        mock_gate.validate_inputs.return_value = _mock_verdict("allow")
        mock_gate.record_lineage.return_value = _mock_lineage()

        r = client.post("/api/v3/build/run", params=BASE_PARAMS, headers=HEADERS)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["build_result"] == {
        "status": "failed",
        "message": "Build execution failed",
    }


def test_build_v3_returns_expected_response_contract(monkeypatch, tmp_path):
    from app.api.endpoints import build_v3 as build_v3_mod

    monkeypatch.setattr(build_v3_mod, "WORKSPACE_ROOT", tmp_path)

    with patch("app.api.endpoints.build_v3.gate") as mock_gate:
        mock_gate.validate_inputs.return_value = {
            "decision": "ALLOW",
            "policy_profile": "default",
            "reasons": ["all checks passed"],
        }
        mock_gate.record_lineage.return_value = {"stored": True, "path": "workspace/test_job/.copilot/build_lineage/abc.json"}

        r = client.post("/api/v3/build/run", params=BASE_PARAMS, headers=HEADERS)

    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {
        "build_id",
        "decision",
        "policy_profile",
        "policy_reasons",
        "risk_score",
        "approval_required",
        "approval",
        "lineage",
        "build_result",
    }
    assert isinstance(body["build_id"], str)
    assert body["decision"] == "ALLOW"
    assert body["policy_profile"] == "default"
    assert body["policy_reasons"] == ["all checks passed"]
    assert body["lineage"] == {"stored": True, "path": "workspace/test_job/.copilot/build_lineage/abc.json"}


def test_build_v3_high_risk_requires_approval(monkeypatch, tmp_path):
    from app.api.endpoints import build_v3 as build_v3_mod

    monkeypatch.setattr(build_v3_mod, "WORKSPACE_ROOT", tmp_path)

    workspace_job_dir = tmp_path / BASE_PARAMS["job_name"]
    intelligence_dir = workspace_job_dir / ".copilot" / "intelligence"
    intelligence_dir.mkdir(parents=True, exist_ok=True)
    (intelligence_dir / f"{BASE_PARAMS['intelligence_hash']}.json").write_text(
        '{"risk_score": 0.95}',
        encoding="utf-8",
    )

    with patch("app.api.endpoints.build_v3.gate") as mock_gate:
        mock_gate.validate_inputs.return_value = _mock_verdict("allow")
        mock_gate.record_lineage.return_value = _mock_lineage()

        r = client.post("/api/v3/build/run", params=BASE_PARAMS, headers=HEADERS)

    assert r.status_code == 409, r.text
    j = r.json()["detail"]
    assert j["code"] == "approval_required"
    assert j["plan_hash"] == BASE_PARAMS["plan_hash"]


def test_build_v3_high_risk_with_approval_succeeds(monkeypatch, tmp_path):
    from app.api.endpoints import build_v3 as build_v3_mod
    from app.api.endpoints import build_approvals as approvals_mod
    from app.core.build_approval import BuildApprovalStore

    monkeypatch.setattr(build_v3_mod, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(approvals_mod, "WORKSPACE_ROOT", tmp_path)

    workspace_job_dir = tmp_path / BASE_PARAMS["job_name"]
    intelligence_dir = workspace_job_dir / ".copilot" / "intelligence"
    intelligence_dir.mkdir(parents=True, exist_ok=True)
    (intelligence_dir / f"{BASE_PARAMS['intelligence_hash']}.json").write_text(
        '{"risk_score": 0.92}',
        encoding="utf-8",
    )

    store = BuildApprovalStore(workspace_root=tmp_path)
    store.save_approval(
        job_name=BASE_PARAMS["job_name"],
        plan_hash=BASE_PARAMS["plan_hash"],
        approver="platform_admin",
        notes="approved for rollout",
    )

    with patch("app.api.endpoints.build_v3.gate") as mock_gate:
        mock_gate.validate_inputs.return_value = _mock_verdict("allow")
        mock_gate.record_lineage.return_value = _mock_lineage()

        r = client.post("/api/v3/build/run", params=BASE_PARAMS, headers=HEADERS)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["approval_required"] is True
    assert isinstance(body["approval"], dict)
    assert body["approval"]["approver"] == "platform_admin"
