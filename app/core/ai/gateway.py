"""LLM gateway service with tenant budget enforcement and token-cost ledgering."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core.ai.models import (
    AIBudgetExceededError,
    AIGatewayNotConfiguredError,
    AIGatewayRequest,
    AIOutputValidationError,
    LLMClient,
    LLMResponse,
)
from app.core.billing.ledger import LedgerStore, utc_month_key
from app.core.billing.tenant_budget import get_tenant_monthly_budget


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_WORKSPACE_ROOT = _PROJECT_ROOT / "workspace"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_task_name(task: str) -> str:
    raw = (task or "llm_task").strip() or "llm_task"
    safe = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "_" for ch in raw)
    return safe[:64] or "llm_task"


class _EnvEchoLLMClient:
    """Deterministic placeholder client.

    This does not call external providers. It is intentionally used as a safe
    default until a concrete provider adapter is wired in a later phase.
    """

    def complete(
        self,
        *,
        task: str,
        model: str,
        system_prompt: str,
        user_content: str,
        json_mode: bool,
    ) -> tuple[str, int, int]:
        if json_mode:
            content = json.dumps(
                {
                    "task": task,
                    "model": model,
                    "message": "gateway_placeholder_response",
                },
                sort_keys=True,
            )
        else:
            content = f"[{model}] {user_content.strip()}"

        prompt_tokens = max(1, len(f"{system_prompt}\n{user_content}".split()))
        completion_tokens = max(1, len(content.split()))
        return content, prompt_tokens, completion_tokens


class AIGatewayService:
    def __init__(
        self,
        *,
        workspace_dir: Path | None = None,
        client: LLMClient | None = None,
        require_api_key: bool = True,
        prompt_token_rate_usd: float = 0.000001,
        completion_token_rate_usd: float = 0.000002,
    ):
        self.workspace_dir = workspace_dir or (_DEFAULT_WORKSPACE_ROOT / "__ai__")
        self.client: LLMClient = client or _EnvEchoLLMClient()
        self.require_api_key = bool(require_api_key)
        self.prompt_token_rate_usd = float(prompt_token_rate_usd)
        self.completion_token_rate_usd = float(completion_token_rate_usd)

    def _require_config(self) -> None:
        if not self.require_api_key:
            return
        api_key = (os.getenv("LLM_API_KEY") or "").strip()
        if not api_key:
            raise AIGatewayNotConfiguredError()

    @staticmethod
    def _validate_json_output(content: str) -> None:
        try:
            json.loads(content)
        except Exception as exc:  # pragma: no cover - exercised in caller path
            raise AIOutputValidationError(raw_output=content, validation_error=str(exc)) from exc

    def _spent_and_limit(self, *, tenant: str, month: str) -> tuple[float, float]:
        ledger = LedgerStore(workspace_dir=self.workspace_dir)
        spent_actual_usd = float(ledger.spent_actual_usd(tenant=tenant, month=month))
        budget = get_tenant_monthly_budget(workspace_dir=self.workspace_dir, tenant=tenant, month=month)
        return spent_actual_usd, float(budget.limit_usd)

    def _estimate_cost_usd(self, *, prompt_tokens: int, completion_tokens: int) -> float:
        cost = (float(prompt_tokens) * self.prompt_token_rate_usd) + (
            float(completion_tokens) * self.completion_token_rate_usd
        )
        return round(cost, 6)

    def _record_actual_cost(
        self,
        *,
        tenant: str,
        month: str,
        task: str,
        cost_usd: float,
    ) -> None:
        ledger = LedgerStore(workspace_dir=self.workspace_dir)
        ledger.upsert_actual(
            tenant=tenant,
            month=month,
            job_name=f"ai_{_safe_task_name(task)}",
            build_id=f"ai_{uuid4().hex}",
            actual_cost_usd=float(cost_usd),
            actual_runtime_seconds=None,
            finished_ts=_utc_now_iso(),
        )

    def complete(
        self,
        req: AIGatewayRequest,
        *,
        tenant: str,
        month: str | None = None,
    ) -> LLMResponse:
        self._require_config()
        month_key = month or utc_month_key()

        spent_before, limit_usd = self._spent_and_limit(tenant=tenant, month=month_key)

        # Budget gate: ceiling estimate prevents overspend. TOCTOU risk is documented — see KNOWN_LIMITATIONS.md
        CEILING_TOKENS_ESTIMATE = 2000
        ceiling_cost_estimate = self._estimate_cost_usd(
            prompt_tokens=CEILING_TOKENS_ESTIMATE,
            completion_tokens=CEILING_TOKENS_ESTIMATE,
        )
        if spent_before + ceiling_cost_estimate > limit_usd:
            raise AIBudgetExceededError(
                tenant=tenant,
                month=month_key,
                limit_usd=limit_usd,
                current_usd=spent_before,
            )

        content, prompt_tokens, completion_tokens = self.client.complete(
            task=req.task,
            model=req.model,
            system_prompt=req.system_prompt,
            user_content=req.user_content,
            json_mode=req.json_mode,
        )

        total_prompt_tokens = int(prompt_tokens)
        total_completion_tokens = int(completion_tokens)

        if req.json_mode:
            try:
                self._validate_json_output(content)
            except AIOutputValidationError:
                retry_content, retry_prompt_tokens, retry_completion_tokens = self.client.complete(
                    task=req.task,
                    model=req.model,
                    system_prompt=req.system_prompt,
                    user_content=(
                        f"{req.user_content}\n\n"
                        "Return only valid JSON. Do not include markdown code fences."
                    ),
                    json_mode=True,
                )
                total_prompt_tokens += int(retry_prompt_tokens)
                total_completion_tokens += int(retry_completion_tokens)
                self._validate_json_output(retry_content)
                content = retry_content

        cost_usd = self._estimate_cost_usd(
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
        )
        self._record_actual_cost(
            tenant=tenant,
            month=month_key,
            task=req.task,
            cost_usd=cost_usd,
        )

        return LLMResponse(
            content=content,
            model=req.model,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            cost_usd=cost_usd,
            task=req.task,
            tenant_id=tenant,
        )

