from pathlib import Path

from app.core.execution.executor import Executor
from app.core.execution.models import ExecutionState
from app.core.execution.registry import ExecutionRegistry


def test_execution_cancel_transitions_to_failed(tmp_path: Path):
    ws = tmp_path / "workspace" / "job_cancel"
    reg = ExecutionRegistry(workspace_dir=ws)

    reg.init_if_missing(
        job_name="job_cancel",
        build_id="b1",
        tenant="default",
        runtime_profile=None,
        preflight_hash=None,
        cost_estimate=None,
        request_id=None,
        initial_state=ExecutionState.APPLIED,
    )

    ex = Executor(registry=reg)
    running = ex.run("job_cancel", backend_name="k8s")
    assert running["state"] == ExecutionState.RUNNING.value

    cancelled = ex.cancel("job_cancel")
    assert cancelled["state"] == ExecutionState.FAILED.value