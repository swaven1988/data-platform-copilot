from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.ai.gateway import AIGatewayService
from app.core.ai.memory_store import TenantMemoryStore
from app.core.ai.models import AIGatewayRequest, LLMResponse
from app.core.ai.triage_engine import FailureTriageEngine
from app.core.execution.models import ExecutionState
from app.core.execution.registry import ExecutionRegistry


AUTH_HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


class _GatewayTriageStub(AIGatewayService):
    def __init__(self, payload: dict[str, object]):
        self.payload = payload

    def complete(self, req: AIGatewayRequest, *, tenant: str, month: str | None = None) -> LLMResponse:
        return LLMResponse(
            content=json.dumps(self.payload),
            model=req.model,
            prompt_tokens=8,
            completion_tokens=12,
            cost_usd=0.02,
            task=req.task,
            tenant_id=tenant,
        )


def test_memory_store_tenant_isolation(tmp_path: Path):
    ws = tmp_path / "workspace"
    store = TenantMemoryStore(workspace_root=ws)

    store.add_document(tenant="t1", collection="build_failures", text="OOM on stage 3", metadata={"job": "a"})
    store.add_document(tenant="t2", collection="build_failures", text="network timeout", metadata={"job": "b"})

    h1 = store.search(tenant="t1", collection="build_failures", query="OOM", top_k=5)
    h2 = store.search(tenant="t2", collection="build_failures", query="OOM", top_k=5)

    assert len(h1) == 1
    assert h1[0].metadata["job"] == "a"
    assert h2 == []


def test_triage_engine_uses_rag_and_persists_memory(tmp_path: Path):
    ws = tmp_path / "workspace"
    store = TenantMemoryStore(workspace_root=ws)
    store.add_document(
        tenant="default",
        collection="build_failures",
        text="previous OOM while processing wide join",
        metadata={"build_id": "old1"},
    )

    gateway = _GatewayTriageStub(
        {
            "root_cause_class": "OOM",
            "confidence": 0.93,
            "human_summary": "Executor memory pressure due to skew.",
            "recommended_action": "Increase memory and enable AQE.",
            "recurrence_risk": "high",
        }
    )
    engine = FailureTriageEngine(memory=store, gateway=gateway)

    report = engine.triage(
        tenant="default",
        job_name="job_t1",
        build_id="b1",
        error_text="Job failed with out of memory error",
    )

    assert report.root_cause_class.value == "OOM"
    assert report.recurrence_risk.value == "high"

    persisted = store.search(tenant="default", collection="build_failures", query="out of memory", top_k=10)
    assert len(persisted) >= 1


def test_triage_failure_endpoint_contract(tmp_path: Path, monkeypatch):
    ws_root = tmp_path / "workspace"
    ws_job = ws_root / "triage_job"
    ws_job.mkdir(parents=True, exist_ok=True)

    reg = ExecutionRegistry(workspace_dir=ws_job)
    reg.init_if_missing(
        job_name="triage_job",
        build_id="b_triage",
        tenant="default",
        runtime_profile=None,
        preflight_hash=None,
        cost_estimate=None,
        request_id=None,
        initial_state=ExecutionState.APPLIED,
    )
    reg.transition(job_name="triage_job", dst=ExecutionState.RUNNING, message="running")
    reg.update_fields(job_name="triage_job", fields={"last_error": "OOM in executor"})
    reg.transition(job_name="triage_job", dst=ExecutionState.FAILED, message="failed")

    monkeypatch.setenv("COPILOT_AUTH_ENABLED", "0")

    from app.api.endpoints import triage as triage_ep

    class _SvcFake(AIGatewayService):
        def __init__(self, *args, **kwargs):
            pass

        def complete(self, req: AIGatewayRequest, *, tenant: str, month: str | None = None) -> LLMResponse:
            return LLMResponse(
                content=json.dumps(
                    {
                        "root_cause_class": "OOM",
                        "confidence": 0.9,
                        "human_summary": "Out of memory from skew.",
                        "recommended_action": "Increase memory.",
                        "recurrence_risk": "medium",
                    }
                ),
                model=req.model,
                prompt_tokens=1,
                completion_tokens=1,
                cost_usd=0.001,
                task=req.task,
                tenant_id=tenant,
            )

    monkeypatch.setattr(triage_ep, "AIGatewayService", _SvcFake)

    c = TestClient(app)
    r = c.post(
        "/api/v2/triage/failure",
        json={
            "job_name": "triage_job",
            "build_id": "b_triage",
            "workspace_dir": str(ws_job),
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {"job_name", "build_id", "tenant", "report"}
    assert body["report"]["root_cause_class"] == "OOM"

