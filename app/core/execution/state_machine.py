# app/core/execution/state_machine.py
from __future__ import annotations

from typing import Dict, Set, Tuple

from .models import ExecutionState


_ALLOWED: Set[Tuple[ExecutionState, ExecutionState]] = {
    (ExecutionState.DRAFT, ExecutionState.PLAN_READY),
    (ExecutionState.PLAN_READY, ExecutionState.PRECHECK_PASSED),
    (ExecutionState.PRECHECK_PASSED, ExecutionState.APPLIED),
    (ExecutionState.APPLIED, ExecutionState.RUNNING),

    # allow cancel from active states
    (ExecutionState.APPLIED, ExecutionState.CANCELED),
    (ExecutionState.RUNNING, ExecutionState.CANCELED),

    (ExecutionState.RUNNING, ExecutionState.SUCCEEDED),
    (ExecutionState.RUNNING, ExecutionState.FAILED),
    (ExecutionState.PRECHECK_PASSED, ExecutionState.BLOCKED),
    (ExecutionState.PLAN_READY, ExecutionState.BLOCKED),
    (ExecutionState.DRAFT, ExecutionState.BLOCKED),
}

_TERMINAL: Set[ExecutionState] = {
    ExecutionState.SUCCEEDED,
    ExecutionState.FAILED,
    ExecutionState.BLOCKED,
    ExecutionState.CANCELED,
}


def is_terminal(state: ExecutionState) -> bool:
    return state in _TERMINAL


def can_transition(src: ExecutionState, dst: ExecutionState) -> bool:
    if src == dst:
        return True
    if src in _TERMINAL:
        return False
    return (src, dst) in _ALLOWED


def ensure_transition(src: ExecutionState, dst: ExecutionState) -> None:
    if not can_transition(src, dst):
        raise ValueError(f"Illegal transition: {src.value} -> {dst.value}")


def allowed_next(src: ExecutionState) -> Dict[str, bool]:
    out: Dict[str, bool] = {}
    for a, b in _ALLOWED:
        if a == src:
            out[b.value] = True
    return out