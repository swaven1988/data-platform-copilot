"""Confidence-gated hybrid intent parser.

Deterministic parser remains source-of-truth. LLM gap-fill is only attempted
when parser confidence is below a configurable threshold.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict

from app.core.ai.gateway import AIGatewayService
from app.core.ai.models import AIGatewayRequest, AIIntentAugmentation
from app.core.project_analyzer.intent_parser import ParseResult, parse_requirement_to_spec


_ALLOWED_PATCH_FIELDS = {
    "job_name",
    "owner",
    "env",
    "schedule",
    "timezone",
    "description",
    "tags",
    "source_table",
    "target_table",
    "partition_column",
    "write_mode",
    "language",
    "spark_dynamic_allocation",
    "spark_conf_overrides",
}

_TABLE_NAME_RE = re.compile(r"^[A-Za-z0-9_]+\.[A-Za-z0-9_]+$")


def _default_model() -> str:
    return os.getenv("AI_MODEL", "gpt-4o-mini")


@dataclass
class HybridIntentResult:
    spec: Dict[str, Any]
    parser_confidence: float
    final_confidence: float
    parser_warning_count: int
    augmented: bool
    augmentation: AIIntentAugmentation | None
    explain: Dict[str, Any]


def _confidence_delta(fields_filled: int) -> float:
    # bounded uplift: 0.03 per field, max 0.20
    return round(min(0.20, max(0.0, fields_filled * 0.03)), 3)


def _build_gapfill_prompt(requirement: str, spec: Dict[str, Any]) -> str:
    return (
        "Fill missing/weak fields for a Copilot build spec. "
        "Return JSON object only with keys to patch. "
        "Allowed keys: "
        + ", ".join(sorted(_ALLOWED_PATCH_FIELDS))
        + "\n"
        + "Requirement:\n"
        + requirement
        + "\n\nCurrent spec:\n"
        + json.dumps(spec, sort_keys=True)
    )


def _coerce_patch_field(key: str, value: Any) -> Any:
    if key in {"source_table", "target_table"}:
        if not isinstance(value, str):
            return None
        v = value.strip()
        if not _TABLE_NAME_RE.match(v):
            return None
        return v

    if key == "tags":
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            return [s.strip() for s in value.split(",") if s.strip()]
        return []

    if key == "spark_dynamic_allocation":
        return bool(value)

    if key == "spark_conf_overrides":
        if not isinstance(value, dict):
            return {}
        return {str(k): str(v) for k, v in value.items()}

    return value


def _merge_patch(base: Dict[str, Any], patch: Dict[str, Any]) -> tuple[Dict[str, Any], list[str]]:
    out = dict(base)
    fields_filled: list[str] = []
    for k, v in patch.items():
        if k not in _ALLOWED_PATCH_FIELDS:
            continue
        vv = _coerce_patch_field(k, v)
        if vv is None:
            continue
        if isinstance(vv, str) and not vv.strip():
            continue
        out[k] = vv
        fields_filled.append(k)
    return out, sorted(dict.fromkeys(fields_filled))


def parse_intent_hybrid(
    *,
    requirement: str,
    job_name_hint: str | None,
    defaults: Dict[str, Any] | None,
    tenant: str,
    gateway: AIGatewayService,
    confidence_threshold: float = 0.75,
) -> HybridIntentResult:
    parser_result: ParseResult = parse_requirement_to_spec(
        requirement=requirement,
        job_name_hint=job_name_hint,
        defaults=defaults or {},
    )

    parser_conf = float(parser_result.confidence)
    explain: Dict[str, Any] = {
        "parser": parser_result.explain,
        "threshold": float(confidence_threshold),
        "llm_used": False,
    }

    if parser_conf >= float(confidence_threshold):
        return HybridIntentResult(
            spec=parser_result.spec,
            parser_confidence=parser_conf,
            final_confidence=parser_conf,
            parser_warning_count=len(parser_result.warnings),
            augmented=False,
            augmentation=None,
            explain=explain,
        )

    req = AIGatewayRequest(
        task="intent_gapfill",
        model=_default_model(),
        system_prompt=(
            "You are assisting with Copilot intent parsing. "
            "Return strict JSON object only. No markdown."
        ),
        user_content=_build_gapfill_prompt(requirement=requirement, spec=parser_result.spec),
        json_mode=True,
    )

    try:
        llm = gateway.complete(req, tenant=tenant)
        patch_raw = json.loads(llm.content)
        if not isinstance(patch_raw, dict):
            patch_raw = {}
    except Exception as exc:
        # Gateway unavailable or budget exceeded — return deterministic result safely
        explain["llm_used"] = False
        explain["llm_fallback_reason"] = str(exc)
        return HybridIntentResult(
            spec=parser_result.spec,
            parser_confidence=parser_conf,
            final_confidence=parser_conf,
            parser_warning_count=len(parser_result.warnings),
            augmented=False,
            augmentation=None,
            explain=explain,
        )

    merged_spec, fields_filled = _merge_patch(parser_result.spec, patch_raw)
    delta = _confidence_delta(len(fields_filled))
    final_conf = round(min(1.0, parser_conf + delta), 2)

    augmentation = AIIntentAugmentation(
        fields_filled=fields_filled,
        confidence_delta=delta,
        source="llm",
    )

    explain.update(
        {
            "llm_used": True,
            "llm_patch_keys": sorted(list(patch_raw.keys())),
            "fields_filled": fields_filled,
            "confidence_delta": delta,
            "llm_tokens": {
                "prompt_tokens": llm.prompt_tokens,
                "completion_tokens": llm.completion_tokens,
            },
            "llm_cost_usd": llm.cost_usd,
        }
    )

    return HybridIntentResult(
        spec=merged_spec,
        parser_confidence=parser_conf,
        final_confidence=final_conf,
        parser_warning_count=len(parser_result.warnings),
        augmented=True,
        augmentation=augmentation,
        explain=explain,
    )

