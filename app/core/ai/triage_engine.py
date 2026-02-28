"""RAG-augmented failure triage engine."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from app.core.ai.gateway import AIGatewayService
from app.core.ai.memory_store import TenantMemoryStore
from app.core.ai.models import AIGatewayRequest, AITriageReport, RecurrenceRisk, RootCauseClass


_ALLOWED_ROOT_CAUSES = {v.value for v in RootCauseClass}
_ALLOWED_RISKS = {v.value for v in RecurrenceRisk}


def _fallback_report(error_text: str) -> AITriageReport:
    msg = (error_text or "").lower()
    if "oom" in msg or "out of memory" in msg:
        rc = RootCauseClass.OOM
    elif "timeout" in msg:
        rc = RootCauseClass.NETWORK_TIMEOUT
    elif "policy" in msg:
        rc = RootCauseClass.POLICY_VIOLATION
    elif "quota" in msg or "budget" in msg:
        rc = RootCauseClass.QUOTA_EXCEEDED
    elif "corrupt" in msg:
        rc = RootCauseClass.DATA_CORRUPTION
    else:
        rc = RootCauseClass.UNKNOWN

    return AITriageReport(
        root_cause_class=rc,
        confidence=0.55,
        human_summary="Fallback triage generated from deterministic heuristics.",
        recommended_action="Inspect logs, verify dependencies, and retry with guardrails.",
        recurrence_risk=RecurrenceRisk.MEDIUM,
    )


def _prompt_with_context(error_text: str, hits: List[Dict[str, Any]]) -> str:
    context = "\n".join(
        [
            f"- score={h.get('score')} text={h.get('text')} metadata={json.dumps(h.get('metadata') or {}, sort_keys=True)}"
            for h in hits
        ]
    )
    return (
        "Return strict JSON object with keys: "
        "root_cause_class, confidence, human_summary, recommended_action, recurrence_risk.\n"
        f"Error:\n{error_text}\n\n"
        f"Retrieved context:\n{context}"
    )


class FailureTriageEngine:
    def __init__(
        self,
        *,
        memory: TenantMemoryStore,
        gateway: AIGatewayService,
        collection: str = "build_failures",
    ):
        self.memory = memory
        self.gateway = gateway
        self.collection = collection

    def _normalize(self, obj: Dict[str, Any]) -> AITriageReport:
        rc = str(obj.get("root_cause_class") or "unknown")
        risk = str(obj.get("recurrence_risk") or "medium")

        if rc not in _ALLOWED_ROOT_CAUSES:
            rc = "unknown"
        if risk not in _ALLOWED_RISKS:
            risk = "medium"

        conf = obj.get("confidence")
        try:
            conf_v = float(conf)
        except Exception:
            conf_v = 0.55
        conf_v = max(0.0, min(1.0, conf_v))

        return AITriageReport(
            root_cause_class=RootCauseClass(rc),
            confidence=conf_v,
            human_summary=str(obj.get("human_summary") or "No summary provided."),
            recommended_action=str(obj.get("recommended_action") or "Investigate recent changes and retry."),
            recurrence_risk=RecurrenceRisk(risk),
        )

    def triage(
        self,
        *,
        tenant: str,
        job_name: str,
        build_id: str,
        error_text: str,
        persist_memory: bool = True,
    ) -> AITriageReport:
        hits_raw = self.memory.search(
            tenant=tenant,
            collection=self.collection,
            query=error_text,
            top_k=5,
        )
        hits = [
            {
                "id": h.id,
                "text": h.text,
                "metadata": h.metadata,
                "score": h.score,
            }
            for h in hits_raw
        ]

        req = AIGatewayRequest(
            task="failure_triage",
            system_prompt=(
                "You are a build failure triage assistant. "
                "Respond with strict JSON only."
            ),
            user_content=_prompt_with_context(error_text=error_text, hits=hits),
            json_mode=True,
        )

        try:
            out = self.gateway.complete(req, tenant=tenant)
            parsed = json.loads(out.content)
            if not isinstance(parsed, dict):
                raise ValueError("triage output must be object")
            report = self._normalize(parsed)
        except Exception:
            report = _fallback_report(error_text)

        if persist_memory:
            self.memory.add_document(
                tenant=tenant,
                collection=self.collection,
                text=error_text,
                metadata={
                    "job_name": job_name,
                    "build_id": build_id,
                    "root_cause_class": report.root_cause_class.value,
                    "recurrence_risk": report.recurrence_risk.value,
                    "confidence": report.confidence,
                },
            )

        return report

