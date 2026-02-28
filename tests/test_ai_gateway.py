from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.ai.gateway import AIBudgetExceededError, AIGatewayService
from app.core.ai.models import AIGatewayRequest
from app.core.billing.tenant_budget import set_tenant_limit_usd


AUTH_HEADERS = {
    "Authorization": "Bearer dev_admin_token",
    "X-Tenant": "default",
}


class _StubClient:
    def __init__(self, responses: list[str], *, prompt_tokens: int = 5, completion_tokens: int = 7):
        self._responses = list(responses)
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
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
        if self._responses:
            content = self._responses.pop(0)
        else:
            content = "{}" if json_mode else "ok"
        return content, self.prompt_tokens, self.completion_tokens


def _make_service(tmp_path: Path, *, responses: list[str], require_api_key: bool = False) -> AIGatewayService:
    return AIGatewayService(
        workspace_dir=tmp_path / "workspace" / "__ai__",
        client=_StubClient(responses),
        require_api_key=require_api_key,
        prompt_token_rate_usd=0.01,
        completion_token_rate_usd=0.01,
    )


def test_gateway_json_retry_and_ledger_record(tmp_path):
    svc = _make_service(tmp_path, responses=["not-json", json.dumps({"ok": True})])

    req = AIGatewayRequest(
        task="intent_parse",
        model="gpt-4o-mini",
        system_prompt="return json",
        user_content="parse this",
        json_mode=True,
    )
    out = svc.complete(req, tenant="default", month="2026-02")

    assert out.content == json.dumps({"ok": True})
    assert out.prompt_tokens == 10
    assert out.completion_tokens == 14
    assert out.cost_usd == 0.24

    ledger_file = tmp_path / "workspace" / ".copilot" / "billing" / "ledger.json"
    assert ledger_file.exists()
    payload = json.loads(ledger_file.read_text(encoding="utf-8"))
    entries = payload.get("entries", [])
    assert len(entries) == 1
    assert entries[0]["tenant"] == "default"
    assert entries[0]["month"] == "2026-02"
    assert entries[0]["actual_cost_usd"] == 0.24


def test_gateway_budget_enforced_before_call(tmp_path):
    ws = tmp_path / "workspace" / "__ai__"
    set_tenant_limit_usd(workspace_dir=ws, tenant="default", limit_usd=0.0)
    svc = _make_service(tmp_path, responses=[json.dumps({"ok": True})])

    req = AIGatewayRequest(
        task="triage",
        model="gpt-4o-mini",
        system_prompt="json",
        user_content="x",
        json_mode=True,
    )

    try:
        svc.complete(req, tenant="default", month="2026-02")
        assert False, "expected budget exception"
    except AIBudgetExceededError as exc:
        assert exc.tenant == "default"
        assert exc.month == "2026-02"


def test_gateway_endpoint_contract_and_status_codes(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_ENABLED", "0")

    from app.api.endpoints import ai_gateway as ai_ep

    class _SvcOk:
        def __init__(self, *args, **kwargs):
            pass

        def complete(self, req: AIGatewayRequest, *, tenant: str, month: str | None = None):
            from app.core.ai.models import LLMResponse

            return LLMResponse(
                content="{}",
                model=req.model,
                prompt_tokens=1,
                completion_tokens=2,
                cost_usd=0.003,
                task=req.task,
                tenant_id=tenant,
            )

    monkeypatch.setattr(ai_ep, "AIGatewayService", _SvcOk)

    c = TestClient(app)
    body = {
        "task": "intent_parse",
        "model": "gpt-4o-mini",
        "system_prompt": "json",
        "user_content": "hello",
        "json_mode": True,
    }
    r = c.post("/api/v2/ai/gateway/complete", json=body, headers=AUTH_HEADERS)
    assert r.status_code == 200, r.text
    j = r.json()
    assert set(j.keys()) == {
        "content",
        "model",
        "prompt_tokens",
        "completion_tokens",
        "cost_usd",
        "tenant",
        "month",
    }


def test_gateway_endpoint_503_when_not_configured(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_ENABLED", "0")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    c = TestClient(app)
    body = {
        "task": "intent_parse",
        "model": "gpt-4o-mini",
        "system_prompt": "json",
        "user_content": "hello",
        "json_mode": False,
    }
    r = c.post("/api/v2/ai/gateway/complete", json=body, headers=AUTH_HEADERS)
    assert r.status_code == 503, r.text

