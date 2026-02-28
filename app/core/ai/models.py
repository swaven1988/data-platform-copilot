"""AI domain models and exceptions.

This module defines typed request/response contracts and AI-specific exceptions.
It does not call external LLM APIs and does not execute any pipeline actions.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Protocol

from pydantic import BaseModel


class RootCauseClass(str, Enum):
    OOM = "OOM"
    NETWORK_TIMEOUT = "network_timeout"
    DATA_CORRUPTION = "data_corruption"
    POLICY_VIOLATION = "policy_violation"
    QUOTA_EXCEEDED = "quota_exceeded"
    UNKNOWN = "unknown"


class RecurrenceRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LLMResponse(BaseModel):
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    task: str
    tenant_id: str


class AIBudgetExceededError(Exception):
    def __init__(self, *, tenant: str, month: str, limit_usd: float, current_usd: float):
        self.tenant = tenant
        self.month = month
        self.limit_usd = float(limit_usd)
        self.current_usd = float(current_usd)
        super().__init__(
            f"AI budget exceeded for tenant={tenant} month={month} "
            f"(limit={limit_usd:.6f}, current={current_usd:.6f})"
        )


class AIGatewayNotConfiguredError(Exception):
    def __init__(self, message: str = "LLM_API_KEY is not configured"):
        super().__init__(message)


class AIOutputValidationError(Exception):
    def __init__(self, *, raw_output: str, validation_error: str):
        self.raw_output = raw_output
        self.validation_error = validation_error
        super().__init__(f"AI output validation failed: {validation_error}")


class AITriageReport(BaseModel):
    root_cause_class: RootCauseClass
    confidence: float
    human_summary: str
    recommended_action: str
    recurrence_risk: RecurrenceRisk


class AIIntentAugmentation(BaseModel):
    fields_filled: list[str]
    confidence_delta: float
    source: Literal["llm"]


class LLMClient(Protocol):
    def complete(
        self,
        *,
        task: str,
        model: str,
        system_prompt: str,
        user_content: str,
        json_mode: bool,
    ) -> tuple[str, int, int]:
        ...


class AIGatewayRequest(BaseModel):
    task: str
    model: str = "gpt-4o-mini"
    system_prompt: str
    user_content: str
    json_mode: bool = False


class AIGatewayResponse(BaseModel):
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    tenant: str
    month: str

