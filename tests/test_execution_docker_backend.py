import shutil
import subprocess
import time
from pathlib import Path

import pytest

from app.core.execution.executor import Executor
from app.core.execution.models import ExecutionState
from app.core.execution.registry import ExecutionRegistry


def _docker_daemon_available() -> bool:
    if shutil.which("docker") is None:
        return False
    r = subprocess.run(["docker", "info"], capture_output=True, text=True)
    return r.returncode == 0


def test_docker_backend_run_and_poll(tmp_path: Path):
    if not _docker_daemon_available():
        pytest.skip("docker CLI or daemon not available (docker info failed)")

    ws = tmp_path / "workspace" / "job_docker"
    reg = ExecutionRegistry(workspace_dir=ws)
    reg.init_if_missing(
        job_name="job_docker",
        build_id="b1",
        tenant="default",
        runtime_profile=None,
        preflight_hash=None,
        cost_estimate=None,
        request_id=None,
        initial_state=ExecutionState.APPLIED,
    )

    ex = Executor(registry=reg)
    running = ex.run(
        "job_docker",
        backend_name="docker",
        config={"image": "alpine", "args": ["sh", "-c", "exit 0"]},
    )
    assert running["state"] == ExecutionState.RUNNING.value
    assert running.get("backend") == "docker"
    assert running.get("backend_ref")

    # poll until terminal
    deadline = time.time() + 20
    last = running
    while time.time() < deadline:
        last = ex.refresh_status("job_docker")
        if last["state"] in {ExecutionState.SUCCEEDED.value, ExecutionState.FAILED.value}:
            break
        time.sleep(0.25)

    assert last["state"] == ExecutionState.SUCCEEDED.value

    # cleanup
    subprocess.run(["docker", "rm", "-f", "job_docker"], capture_output=True, text=True)