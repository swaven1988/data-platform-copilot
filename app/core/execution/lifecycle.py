from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Optional


TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "CANCELED"}
ACTIVE_STATUSES = {"PENDING", "RUNNING", "CANCELING"}


@dataclass
class ExecutionRecord:
    run_id: str
    status: str
    created_ts: float
    updated_ts: float
    cancel_requested: bool = False
    terminal_reason: Optional[str] = None


class ExecutionStore:
    """
    Minimal in-memory store used by API + tests.
    Replace with your persistent store later without changing lifecycle semantics.
    """
    def __init__(self):
        self._runs: Dict[str, ExecutionRecord] = {}

    def get(self, run_id: str) -> Optional[ExecutionRecord]:
        return self._runs.get(run_id)

    def put(self, rec: ExecutionRecord) -> None:
        self._runs[rec.run_id] = rec

    def list(self) -> Dict[str, ExecutionRecord]:
        return dict(self._runs)


def now_ts() -> float:
    return time.time()


def request_cancel(store: ExecutionStore, run_id: str) -> ExecutionRecord:
    rec = store.get(run_id)
    if rec is None:
        raise KeyError(run_id)

    # Idempotent: if already terminal, no-op
    if rec.status in TERMINAL_STATUSES:
        return rec

    rec.cancel_requested = True
    # If already canceling, keep it canceling
    rec.status = "CANCELING"
    rec.updated_ts = now_ts()
    store.put(rec)
    return rec


def reconcile_stale_runs(
    store: ExecutionStore,
    stale_after_seconds: int,
) -> int:
    """
    Any RUNNING/CANCELING run not updated within stale_after_seconds becomes FAILED/CANCELED deterministically.
    """
    n = 0
    cutoff = now_ts() - stale_after_seconds

    for run_id, rec in store.list().items():
        if rec.status in TERMINAL_STATUSES:
            continue
        if rec.updated_ts >= cutoff:
            continue

        if rec.cancel_requested:
            rec.status = "CANCELED"
            rec.terminal_reason = "stale_cancel_reconciled"
        else:
            rec.status = "FAILED"
            rec.terminal_reason = "stale_run_reconciled"

        rec.updated_ts = now_ts()
        store.put(rec)
        n += 1

    return n