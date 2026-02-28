from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.ai.gateway import AIGatewayService
from app.core.ai.llm_advisor import LLMExplainableAdvisor, explain_semantic_diff_with_llm
from app.core.ai.models import AIGatewayRequest, LLMResponse


AUTH_HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


class _GatewayExplainStub(AIGatewayService):
    def __init__(self, payload: dict[str, str]):
        self.payload = payload

    def complete(self, req: AIGatewayRequest, *, tenant: str, month: str | None = None) -> LLMResponse:
        return LLMResponse(
            content=json.dumps(self.payload),
            model=req.model,
            prompt_tokens=4,
            completion_tokens=6,
            cost_usd=0.01,
            task=req.task,
            tenant_id=tenant,
        )


def test_llm_advisor_protocol_explain_finding():
    advisor = LLMExplainableAdvisor(gateway=_GatewayExplainStub(
        {
            "summary": "Column rename detected.",
            "impact": "Downstream models may break.",
            "recommendation": "Update dependent transforms.",
        }
    ))

    explanation = advisor.explain_finding(
        "semantic.diff.columns",
        {
            "code": "semantic.diff.columns",
            "message": "column changed",
            "data": {"from": "customer_id", "to": "cust_id"},
        },
    )

    assert explanation is not None
    assert "Column rename detected." in explanation


def test_explain_semantic_diff_with_llm_helper():
    out = explain_semantic_diff_with_llm(
        gateway=_GatewayExplainStub(
            {
                "summary": "Type widened.",
                "impact": "Potential precision drift.",
                "recommendation": "Validate numeric ranges.",
            }
        ),
        finding={"code": "semantic.diff.types", "message": "type changed", "data": {}},
        tenant="default",
    )
    assert out["summary"] == "Type widened."
    assert out["impact"] == "Potential precision drift."
    assert out["recommendation"] == "Validate numeric ranges."


def test_ai_explain_endpoint_contract(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_ENABLED", "0")

    from app.api.endpoints import ai_explain as ep

    class _SvcFake(AIGatewayService):
        def __init__(self, *args, **kwargs):
            pass

        def complete(self, req: AIGatewayRequest, *, tenant: str, month: str | None = None) -> LLMResponse:
            return LLMResponse(
                content=json.dumps(
                    {
                        "summary": "Join key changed.",
                        "impact": "May alter row cardinality.",
                        "recommendation": "Re-run contract and row-count checks.",
                    }
                ),
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
        "/api/v2/ai/explain",
        json={
            "advisor_name": "llm_semantic_diff_explainer",
            "code": "semantic.diff.join_key",
            "finding": {"message": "join key changed", "data": {"old": "id", "new": "customer_id"}},
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {"advisor_name", "code", "explanation", "sections", "finding"}
    assert body["sections"]["summary"] == "Join key changed."

