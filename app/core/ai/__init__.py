"""AI activation package for Data Platform Copilot.

This package contains wrappers and services for LLM-assisted analysis.
It does not execute builds or bypass policy/preflight gates.
"""

from app.core.ai.gateway import AIGatewayService
from app.core.ai.models import (
    AIBudgetExceededError,
    AIGatewayNotConfiguredError,
    AIIntentAugmentation,
    AIOutputValidationError,
    AITriageReport,
    LLMResponse,
)

__all__ = [
    "AIGatewayService",
    "LLMResponse",
    "AIBudgetExceededError",
    "AIGatewayNotConfiguredError",
    "AIOutputValidationError",
    "AITriageReport",
    "AIIntentAugmentation",
]

