"""
Regression tests for AI backend bug fixes.
Covers: intent fallback, memory locking, budget timing, tenant isolation,
triage graceful degradation, CopilotSpec validation after LLM merge,
GET triage endpoint contract.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.endpoints import triage as triage_ep
from app.core.ai.gateway import AIBudgetExceededError, AIGatewayNotConfiguredError, AIGatewayService
from app.core.ai.intent_hybrid import parse_intent_hybrid
from app.core.ai.llm_advisor import LLMExplainableAdvisor
from app.core.ai.memory_store import TenantMemoryStore
from app.core.ai.models import AIGatewayRequest, LLMResponse
from app.core.ai.triage_engine import FailureTriageEngine
from app.core.billing.ledger import LedgerStore
from app.core.billing.tenant_budget import set_tenant_limit_usd


AUTH_HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


class _AlwaysRaiseGateway:
    def complete(self, req: AIGatewayRequest, *, tenant: str, month: str | None = None) -> LLMResponse:
        raise AIGatewayNotConfiguredError("gateway unavailable")


class _RecordingClient:
    def __init__(self):
        self.calls = 0

    def complete(
        self,
        *,
        task: str,
        model: str,
        system_prompt: str,
        user_content: str,
        json_mode: bool,
    ) -> tuple[str, int, int]:
        self.calls += 1
        return json.dumps({"ok": True}), 10, 10


class _RecordingGateway:
    def __init__(self):
        self.tenants: list[str] = []

    def complete(self, req: AIGatewayRequest, *, tenant: str, month: str | None = None) -> LLMResponse:
        self.tenants.append(tenant)
        return LLMResponse(
            content=json.dumps(
                {
                    "summary": "s",
                    "impact": "i",
                    "recommendation": "r",
                }
            ),
            model=req.model,
            prompt_tokens=1,
            completion_tokens=1,
            cost_usd=0.001,
            task=req.task,
            tenant_id=tenant,
        )


class _PatchGateway:
    def __init__(self, patch: dict[str, Any]):
        self.patch = patch

    def complete(self, req: AIGatewayRequest, *, tenant: str, month: str | None = None) -> LLMResponse:
        return LLMResponse(
            content=json.dumps(self.patch),
            model=req.model,
            prompt_tokens=2,
            completion_tokens=2,
            cost_usd=0.001,
            task=req.task,
            tenant_id=tenant,
        )


def test_hybrid_llm_exception_returns_deterministic_result():
    result = parse_intent_hybrid(
        requirement="need pipeline",
        job_name_hint="hybrid_fallback_job",
        defaults={},
        tenant="default",
        gateway=_AlwaysRaiseGateway(),  # type: ignore[arg-type]
        confidence_threshold=0.99,
    )

    assert result.augmented is False
    assert isinstance(result.spec, dict)
    assert result.spec.get("job_name") == "hybrid_fallback_job"
    assert result.explain.get("llm_used") is False
    assert isinstance(result.explain.get("llm_fallback_reason"), str)
    assert result.explain.get("llm_fallback_reason")


def test_gateway_budget_gate_fires_before_llm_call(tmp_path: Path):
    ws = tmp_path / "workspace" / "__ai__"
    ws.mkdir(parents=True, exist_ok=True)

    set_tenant_limit_usd(workspace_dir=ws, tenant="default", limit_usd=0.001)

    client = _RecordingClient()
    gateway = AIGatewayService(
        workspace_dir=ws,
        client=client,
        require_api_key=False,
    )

    req = AIGatewayRequest(
        task="triage",
        system_prompt="json",
        user_content="x",
        json_mode=True,
    )

    try:
        gateway.complete(req, tenant="default", month="2026-02")
        assert False, "expected AIBudgetExceededError"
    except AIBudgetExceededError:
        pass

    assert client.calls == 0

    ledger = LedgerStore(workspace_dir=ws)
    assert ledger.entries_count(tenant="default", month="2026-02") == 0


def test_memory_store_concurrent_writes_safe(tmp_path: Path):
    store = TenantMemoryStore(workspace_root=tmp_path / "workspace")

    def _writer(i: int) -> None:
        store.add_document(
            tenant="t1",
            collection="build_failures",
            text=f"error_{i}",
            metadata={"i": i},
        )

    threads = [threading.Thread(target=_writer, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    rows = store._read_all(tenant="t1", collection="build_failures")
    assert len(rows) == 20
    assert all(isinstance(r, dict) for r in rows)


def test_llm_advisor_uses_instance_tenant_for_billing():
    gw = _RecordingGateway()
    advisor = LLMExplainableAdvisor(gateway=gw, tenant="tenant_xyz")  # type: ignore[arg-type]

    out = advisor.explain_finding("some.code", {"message": "test finding"})

    assert out is not None
    assert gw.tenants[-1] == "tenant_xyz"


def test_triage_engine_gateway_error_uses_fallback_report(tmp_path: Path):
    store = TenantMemoryStore(workspace_root=tmp_path / "workspace")
    engine = FailureTriageEngine(memory=store, gateway=_AlwaysRaiseGateway())  # type: ignore[arg-type]

    report = engine.triage(
        tenant="t",
        job_name="j",
        build_id="b",
        error_text="OOM killed",
    )

    assert report.root_cause_class.value == "OOM"
    assert report.confidence < 0.7


def test_hybrid_llm_invalid_table_format_falls_back_to_deterministic():
    result = parse_intent_hybrid(
        requirement="pipeline from raw.orders to curated.orders",
        job_name_hint="job_tables",
        defaults={},
        tenant="default",
        gateway=_PatchGateway({"source_table": "not_a_table_format"}),  # type: ignore[arg-type]
        confidence_threshold=0.99,
    )

    assert result.spec["source_table"] != "not_a_table_format"
    assert "." in str(result.spec["source_table"])


def test_get_triage_endpoint_returns_stored_reports(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_ENABLED", "0")

    ws_root = tmp_path / "workspace"
    ws_root.mkdir(parents=True, exist_ok=True)

    seeded = TenantMemoryStore(workspace_root=ws_root)
    seeded.add_document(
        tenant="default",
        collection="build_failures",
        text="triage_get_job failure due to oom",
        metadata={"job_name": "triage_get_job", "build_id": "b1"},
    )

    class _SeededStore(TenantMemoryStore):
        def __init__(self, *args, **kwargs):
            self.workspace_root = ws_root
            self.root = ws_root / ".copilot" / "ai_memory"
            self.root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(triage_ep, "TenantMemoryStore", _SeededStore)

    client = TestClient(app)
    r = client.get("/api/v2/triage/failure/triage_get_job", headers=AUTH_HEADERS)
    assert r.status_code == 200, r.text

    body = r.json()
    assert set(body.keys()) == {"job_name", "tenant", "reports"}
    assert isinstance(body["reports"], list)
    assert body["job_name"] == "triage_get_job"
