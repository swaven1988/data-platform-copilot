from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional


TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "CANCELED"}
ACTIVE_STATUSES = {"PENDING", "RUNNING", "CANCELING"}
RETRYABLE_STATUSES = {"FAILED", "CANCELED"}


@dataclass
class ExecutionRecord:
    run_id: str
    status: str
    created_ts: float
    updated_ts: float
    cancel_requested: bool = False
    terminal_reason: Optional[str] = None
    retry_count: int = 0


def _shared_store_path() -> Path:
    project_root = Path(__file__).resolve().parents[3]
    workspace_root_env = os.getenv("COPILOT_WORKSPACE_ROOT", "")
    workspace_root = Path(workspace_root_env).resolve() if workspace_root_env else (project_root / "workspace")
    p = workspace_root / ".copilot" / "execution" / "lifecycle_store.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


class ExecutionStore:
    """
    Shared in-memory store with JSON persistence for lifecycle endpoints.
    """

    def __init__(self, *, path: Optional[Path] = None):
        self._path = path
        self._lock = threading.Lock()
        self._runs: Dict[str, ExecutionRecord] = {}
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(raw, dict):
            return
        runs = raw.get("runs")
        if not isinstance(runs, dict):
            return
        parsed: Dict[str, ExecutionRecord] = {}
        for run_id, obj in runs.items():
            if not isinstance(obj, dict):
                continue
            try:
                parsed[str(run_id)] = ExecutionRecord(
                    run_id=str(obj.get("run_id") or run_id),
                    status=str(obj.get("status") or "PENDING"),
                    created_ts=float(obj.get("created_ts") or now_ts()),
                    updated_ts=float(obj.get("updated_ts") or now_ts()),
                    cancel_requested=bool(obj.get("cancel_requested", False)),
                    terminal_reason=obj.get("terminal_reason"),
                    retry_count=int(obj.get("retry_count") or 0),
                )
            except Exception:
                continue
        self._runs = parsed

    def _save(self) -> None:
        if self._path is None:
            return
        obj = {
            "kind": "execution_lifecycle_store",
            "runs": {k: asdict(v) for k, v in self._runs.items()},
        }
        self._path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")

    def get(self, run_id: str) -> Optional[ExecutionRecord]:
        with self._lock:
            return self._runs.get(run_id)

    def put(self, rec: ExecutionRecord) -> None:
        with self._lock:
            self._runs[rec.run_id] = rec
            self._save()

    def list(self) -> Dict[str, ExecutionRecord]:
        with self._lock:
            return dict(self._runs)


_SHARED_STORE: Optional[ExecutionStore] = None
_SHARED_STORE_PATH: Optional[Path] = None
_SHARED_STORE_LOCK = threading.Lock()


def get_shared_store() -> ExecutionStore:
    global _SHARED_STORE, _SHARED_STORE_PATH
    path = _shared_store_path()
    with _SHARED_STORE_LOCK:
        if _SHARED_STORE is None or _SHARED_STORE_PATH != path:
            _SHARED_STORE = ExecutionStore(path=path)
            _SHARED_STORE_PATH = path
        return _SHARED_STORE


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


def request_retry(store: ExecutionStore, run_id: str) -> ExecutionRecord:
    rec = store.get(run_id)
    if rec is None:
        raise KeyError(run_id)

    # Idempotent on active states.
    if rec.status in ACTIVE_STATUSES:
        return rec

    if rec.status not in RETRYABLE_STATUSES:
        raise ValueError(f"run_not_retryable:{rec.status}")

    rec.retry_count = int(rec.retry_count) + 1
    rec.cancel_requested = False
    rec.terminal_reason = None
    rec.status = "PENDING"
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

    for _run_id, rec in store.list().items():
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


def reconcile_shared_store(stale_after_seconds: int) -> int:
    return reconcile_stale_runs(get_shared_store(), stale_after_seconds=stale_after_seconds)

