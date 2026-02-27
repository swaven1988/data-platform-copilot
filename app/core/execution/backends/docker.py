from __future__ import annotations

import json
import subprocess
from typing import Any, Dict, Optional

from .base import ExecutionBackend


class DockerBackend(ExecutionBackend):
    name = "docker"

    def _ensure_docker(self) -> None:
        # Best-effort: allow subprocess errors to surface naturally
        return None

    def _image_exists(self, image: str) -> bool:
        r = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            text=True,
        )
        return r.returncode == 0

    def _pull_image(self, image: str) -> None:
        # Pull can take time on first run; we *want* submit() to block here
        # so that later polling isn't stuck in "created"/pulling-related states.
        r = subprocess.run(
            ["docker", "pull", image],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            raise RuntimeError(f"docker pull failed: {r.stderr.strip() or r.stdout.strip()}")

    def submit(self, job_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_docker()

        image = config.get("image")
        if not image:
            raise ValueError("docker backend requires config.image")

        # Ensure image is present before starting container.
        # This avoids tests timing out while the container is stuck before it can actually run.
        if not self._image_exists(image):
            self._pull_image(image)

        # Best-effort cleanup to avoid name collision.
        subprocess.run(["docker", "rm", "-f", job_name], capture_output=True, text=True)

        extra_args = config.get("args") or []
        if not isinstance(extra_args, list):
            raise ValueError("docker backend config.args must be a list")

        cmd = ["docker", "run", "-d", "--name", job_name, image] + extra_args
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"docker run failed: {r.stderr.strip() or r.stdout.strip()}")

        container_id = (r.stdout or "").strip()
        backend_ref = container_id or job_name
        return {"backend_ref": backend_ref, "meta": {"container_id": container_id, "container_name": job_name}}

    def status(self, job_name: str, *, backend_ref: Optional[str] = None) -> Dict[str, Any]:
        self._ensure_docker()

        ref = backend_ref or job_name

        # Use json output to remain stable across platforms
        r = subprocess.run(["docker", "inspect", ref], capture_output=True, text=True)
        if r.returncode != 0:
            return {"state": "FAILED", "reason": "not_found", "detail": (r.stderr or r.stdout).strip()}

        try:
            info = json.loads(r.stdout)[0]
        except Exception:
            return {"state": "FAILED", "reason": "inspect_parse_error"}

        state = info.get("State") or {}
        st = (state.get("Status") or "").strip().lower()
        exit_code = state.get("ExitCode")

        # created/running/etc => RUNNING
        if st in {"created", "running", "paused", "restarting"}:
            return {"state": "RUNNING", "docker_status": st}

        if st == "exited":
            code = int(exit_code or 0)
            if code == 0:
                return {"state": "SUCCEEDED", "docker_status": st, "exit_code": code}
            return {"state": "FAILED", "docker_status": st, "exit_code": code}

        # dead/removing/unknown => failed
        code = int(exit_code or 1) if exit_code is not None else 1
        return {"state": "FAILED", "docker_status": st or "unknown", "exit_code": code}

    def cancel(self, job_name: str, *, backend_ref: Optional[str] = None) -> None:
        self._ensure_docker()
        ref = backend_ref or job_name
        subprocess.run(["docker", "rm", "-f", ref], capture_output=True, text=True)
        