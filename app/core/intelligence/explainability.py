from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol


class ExplainableAdvisor(Protocol):
    """
    Optional protocol. Advisors may implement `explain_finding(code, finding)`
    to provide a tailored explanation.
    """

    name: str

    def explain_finding(self, code: str, finding: Dict[str, Any]) -> Optional[str]:
        ...


@dataclass(frozen=True)
class ExplainRequest:
    advisor_name: str
    code: str
    finding: Dict[str, Any]


def default_explanation(req: ExplainRequest) -> str:
    code = req.code or "unknown.code"
    summary = req.finding.get("message") or req.finding.get("summary") or ""
    applies_to = req.finding.get("applies_to") or req.finding.get("path") or req.finding.get("file") or ""
    severity = req.finding.get("severity") or req.finding.get("level") or "info"

    parts = [f"[{severity}] {code}"]
    if summary:
        parts.append(summary)
    if applies_to:
        parts.append(f"Target: {applies_to}")

    # lightweight, safe defaults (no LLM)
    generic_guidance = {
        "plan.no_baseline": "No baseline commit/reference was found. Connect upstream or initialize baseline, then re-run.",
        "plan.no_expected_files": "Planner did not detect expected generated outputs. Check spec/intent and templates.",
        "basic.strict_mode": "Strict mode is enabled; certain warnings are treated as violations. Adjust advisor options if intended.",
    }
    guidance = generic_guidance.get(code)
    if guidance:
        parts.append(f"Guidance: {guidance}")

    return " | ".join([p for p in parts if p])


def explain_with_registry(
    *,
    registry: Any,
    advisor_name: str,
    code: str,
    finding: Dict[str, Any],
) -> Dict[str, Any]:
    """
    registry is your PluginRegistry (or compatible). We do not import it directly
    to avoid tight coupling.
    """
    plugin = None
    if hasattr(registry, "_plugins"):
        plugin = registry._plugins.get(advisor_name)
    if plugin is None and hasattr(registry, "get"):
        plugin = registry.get(advisor_name)

    req = ExplainRequest(advisor_name=advisor_name, code=code, finding=finding)

    explanation: Optional[str] = None
    if plugin is not None and hasattr(plugin, "explain_finding"):
        try:
            explanation = plugin.explain_finding(code, finding)
        except Exception:
            explanation = None

    if not explanation:
        explanation = default_explanation(req)

    return {
        "advisor_name": advisor_name,
        "code": code,
        "explanation": explanation,
        "finding": finding,
    }
