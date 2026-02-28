from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.ai.gateway import AIGatewayService
from app.core.ai.intent_hybrid import parse_intent_hybrid
from app.core.ai.models import AIGatewayRequest, LLMResponse


AUTH_HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


class _GatewayStub:
    def __init__(self, patch: dict[str, object]):
        self.patch = patch
        self.calls = 0

    def complete(self, req: AIGatewayRequest, *, tenant: str, month: str | None = None) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            content=json.dumps(self.patch),
            model=req.model,
            prompt_tokens=10,
            completion_tokens=20,
            cost_usd=0.03,
            task=req.task,
            tenant_id=tenant,
        )


def test_hybrid_skips_llm_when_confidence_above_threshold():
    gateway = _GatewayStub({"owner": "should_not_apply"})
    out = parse_intent_hybrid(
        requirement="job name: high_conf; env: dev; language: pyspark; source table: raw.a; target table: curated.b",
        job_name_hint=None,
        defaults={"owner": "data-platform"},
        tenant="default",
        gateway=gateway,  # type: ignore[arg-type]
        confidence_threshold=0.6,
    )

    assert out.augmented is False
    assert gateway.calls == 0
    assert out.final_confidence >= out.parser_confidence


def test_hybrid_uses_llm_below_threshold_and_merges_allowed_fields():
    gateway = _GatewayStub(
        {
            "owner": "ai-owner",
            "tags": ["copilot", "ai"],
            "unknown_field": "ignore-me",
        }
    )
    out = parse_intent_hybrid(
        requirement="need a pipeline",
        job_name_hint="hybrid_job",
        defaults={},
        tenant="default",
        gateway=gateway,  # type: ignore[arg-type]
        confidence_threshold=0.95,
    )

    assert out.augmented is True
    assert gateway.calls == 1
    assert out.spec["owner"] == "ai-owner"
    assert out.spec["tags"] == ["copilot", "ai"]
    assert "unknown_field" not in out.spec
    assert out.augmentation is not None
    assert "owner" in out.augmentation.fields_filled


def test_intent_parse_endpoint_contract(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_ENABLED", "0")

    from app.api.endpoints import intent_parse as ep

    class _SvcFake(AIGatewayService):
        def __init__(self, *args, **kwargs):
            pass

        def complete(self, req: AIGatewayRequest, *, tenant: str, month: str | None = None) -> LLMResponse:
            return LLMResponse(
                content=json.dumps({"owner": "owner-from-ai"}),
                model=req.model,
                prompt_tokens=1,
                completion_tokens=1,
                cost_usd=0.001,
                task=req.task,
                tenant_id=tenant,
            )

    monkeypatch.setattr(ep, "AIGatewayService", _SvcFake)

    c = TestClient(app)
    r = c.post(
        "/api/v2/intent/parse",
        json={
            "requirement": "please build pipeline",
            "job_name_hint": "intent_hybrid_job",
            "defaults": {},
            "confidence_threshold": 0.95,
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {
        "spec",
        "parser_confidence",
        "final_confidence",
        "parser_warning_count",
        "augmented",
        "augmentation",
        "explain",
    }
    assert body["spec"]["owner"] == "owner-from-ai"

