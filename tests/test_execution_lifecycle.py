from pathlib import Path

from app.core.execution.models import ExecutionState
from app.core.execution.registry import ExecutionRegistry
from app.core.execution.executor import Executor


def test_execution_apply_run_lifecycle(tmp_path: Path):
    ws = tmp_path / "workspace" / "job1"
    reg = ExecutionRegistry(workspace_dir=ws)

    reg.init_if_missing(
        job_name="job1",
        build_id="b1",
        tenant="default",
        runtime_profile="k8s_spark_default",
        preflight_hash="ph1",
        cost_estimate={"estimated_total_cost_usd": 1.23},
        request_id="r1",
        initial_state=ExecutionState.PRECHECK_PASSED,
    )

    ex = Executor(registry=reg)
    applied = ex.apply("job1")
    assert applied["state"] == ExecutionState.APPLIED.value

    running = ex.run("job1")
    assert running["state"] == ExecutionState.RUNNING.value
    assert running.get("backend") == "local"

    done = ex.refresh_status("job1")
    assert done["state"] == ExecutionState.SUCCEEDED.value

    # idempotent run after terminal
    done2 = ex.run("job1")
    assert done2["state"] == ExecutionState.SUCCEEDED.value