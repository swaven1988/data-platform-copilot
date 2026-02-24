from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from app.core.execution.backends.base import ExecutionBackend
from app.core.execution.backends import BACKENDS
from app.core.execution.executor import Executor
from app.core.execution.models import ExecutionState
from app.core.execution.registry import ExecutionRegistry


class DummyBackend(ExecutionBackend):
    name = "dummy"

    def __init__(self):
        self.cancel_calls = []

    def submit(self, job_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        return {"backend_ref": "ref-123", "meta": {"ok": True}}

    def status(self, job_name: str, *, backend_ref: Optional[str] = None) -> Dict[str, Any]:
        return {"state": "RUNNING"}

    def cancel(self, job_name: str, *, backend_ref: Optional[str] = None) -> None:
        self.cancel_calls.append({"job_name": job_name, "backend_ref": backend_ref})


def _mk_registry(tmp_path: Path) -> ExecutionRegistry:
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    return ExecutionRegistry(workspace_dir=ws)


def test_cancel_from_applied_transitions_to_canceled(tmp_path: Path):
    reg = _mk_registry(tmp_path)
    reg.init_if_missing(
        job_name="job1",
        build_id="b1",
        tenant="default",
        runtime_profile=None,
        preflight_hash=None,
        cost_estimate=None,
        request_id=None,
        initial_state=ExecutionState.APPLIED,
    )
    ex = Executor(registry=reg)
    out = ex.cancel(job_name="job1", tenant="default", request_id="req-1")
    assert out["state"] == "CANCELED"
    rec = reg.get("job1")
    assert rec is not None
    assert rec.finished_ts is not None
    assert rec.request_id == "req-1"


def test_cancel_from_running_calls_backend_cancel_with_correct_signature(tmp_path: Path):
    reg = _mk_registry(tmp_path)
    reg.init_if_missing(
        job_name="job2",
        build_id="b2",
        tenant="default",
        runtime_profile=None,
        preflight_hash=None,
        cost_estimate=None,
        request_id=None,
        initial_state=ExecutionState.APPLIED,
    )

    dummy = DummyBackend()
    BACKENDS["dummy"] = dummy
    try:
        # mark record as running with dummy backend
        reg.update_fields(job_name="job2", fields={"backend": "dummy", "backend_ref": "ref-xyz"})
        reg.transition(job_name="job2", dst=ExecutionState.RUNNING, message="running")

        ex = Executor(registry=reg)
        out = ex.cancel(job_name="job2", tenant="default")
        assert out["state"] == "CANCELED"
        assert dummy.cancel_calls == [{"job_name": "job2", "backend_ref": "ref-xyz"}]
    finally:
        BACKENDS.pop("dummy", None)


def test_cancel_idempotent_on_terminal(tmp_path: Path):
    reg = _mk_registry(tmp_path)
    reg.init_if_missing(
        job_name="job3",
        build_id="b3",
        tenant="default",
        runtime_profile=None,
        preflight_hash=None,
        cost_estimate=None,
        request_id=None,
        initial_state=ExecutionState.CANCELED,
    )
    ex = Executor(registry=reg)
    out = ex.cancel(job_name="job3", tenant="default")
    assert out["state"] == "CANCELED"


def test_cancel_rejects_illegal_state(tmp_path: Path):
    reg = _mk_registry(tmp_path)
    reg.init_if_missing(
        job_name="job4",
        build_id="b4",
        tenant="default",
        runtime_profile=None,
        preflight_hash=None,
        cost_estimate=None,
        request_id=None,
        initial_state=ExecutionState.PRECHECK_PASSED,
    )
    ex = Executor(registry=reg)
    with pytest.raises(ValueError) as e:
        ex.cancel(job_name="job4", tenant="default")
    assert "requires state" in str(e.value)
