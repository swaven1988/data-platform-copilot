"""LLM-backed semantic diff explainer advisor.

Implements the existing advisor explainability protocol so it can be used as a
drop-in advisor with current plugin registry behavior.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.core.ai.gateway import AIGatewayService
from app.core.ai.models import AIGatewayRequest
from app.core.intelligence.explainability import ExplainableAdvisor


def _build_diff_prompt(finding: Dict[str, Any]) -> str:
    code = finding.get("code")
    msg = finding.get("message")
    data = finding.get("data") or {}
    return (
        "Explain this semantic diff finding for a data platform engineer. "
        "Return JSON object with keys: summary, impact, recommendation.\n"
        f"code={code}\n"
        f"message={msg}\n"
        f"data={json.dumps(data, sort_keys=True)}"
    )


@dataclass
class LLMExplainableAdvisor(ExplainableAdvisor):
    name: str = "llm_semantic_diff_explainer"
    version: str = "0.1.0"
    enabled_by_default: bool = False
    applies_to = ["build", "diff", "review"]

    gateway: Optional[AIGatewayService] = None
    tenant: str = "default"

    def _gateway(self) -> AIGatewayService:
        if self.gateway is None:
            self.gateway = AIGatewayService()
        return self.gateway

    def explain_finding(self, code: str, finding: Dict[str, Any]) -> Optional[str]:
        req = AIGatewayRequest(
            task="semantic_diff_explain",
            system_prompt=(
                "You explain semantic diffs safely. "
                "Never include secrets. Return strict JSON only."
            ),
            user_content=_build_diff_prompt(finding),
            json_mode=True,
        )
        try:
            out = self._gateway().complete(req, tenant=self.tenant)
            obj = json.loads(out.content)
            if not isinstance(obj, dict):
                return None
            summary = str(obj.get("summary") or "").strip()
            impact = str(obj.get("impact") or "").strip()
            recommendation = str(obj.get("recommendation") or "").strip()
            parts = [p for p in [summary, impact, recommendation] if p]
            return " | ".join(parts) if parts else None
        except Exception:
            return None

    def advise(self, plan: Any):
        # Optional light-touch advisor behavior: produce no blocking findings.
        return plan, []


def explain_semantic_diff_with_llm(
    *,
    gateway: AIGatewayService,
    finding: Dict[str, Any],
    tenant: str,
) -> Dict[str, str]:
    req = AIGatewayRequest(
        task="semantic_diff_explain",
        system_prompt="Return strict JSON with keys summary, impact, recommendation.",
        user_content=_build_diff_prompt(finding),
        json_mode=True,
    )
    out = gateway.complete(req, tenant=tenant)
    parsed = json.loads(out.content)
    if not isinstance(parsed, dict):
        return {
            "summary": "Unable to parse explainer output.",
            "impact": "Unknown impact.",
            "recommendation": "Inspect semantic diff payload manually.",
        }
    return {
        "summary": str(parsed.get("summary") or ""),
        "impact": str(parsed.get("impact") or ""),
        "recommendation": str(parsed.get("recommendation") or ""),
    }

