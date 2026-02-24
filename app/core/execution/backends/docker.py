from __future__ import annotations

import json
import subprocess
from typing import Any, Dict, Optional

from .base import ExecutionBackend


class DockerBackend(ExecutionBackend):
    name = "docker"

    def _ensure_docker(self) -> None:
        # Let subprocess error surface with a clear message.
        return None

    def submit(self, job_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_docker()

        image = config.get("image")
        if not image:
            raise ValueError("docker backend requires config.image")

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
        r = subprocess.run(["docker", "inspect", ref], capture_output=True, text=True)
        if r.returncode != 0:
            # Container might have been removed or never existed.
            return {"state": "FAILED", "reason": "not_found", "detail": (r.stderr or r.stdout).strip()}

        try:
            info = json.loads(r.stdout)[0]
        except Exception:
            return {"state": "FAILED", "reason": "inspect_parse_error"}

        st = (info.get("State") or {}).get("Status")
        exit_code = (info.get("State") or {}).get("ExitCode")

        # docker status strings: created, running, paused, restarting, removing, exited, dead
        if st in {"running", "paused", "restarting", "created"}:
            return {"state": "RUNNING", "docker_status": st}

        if st == "exited":
            if int(exit_code or 0) == 0:
                return {"state": "SUCCEEDED", "docker_status": st, "exit_code": int(exit_code or 0)}
            return {"state": "FAILED", "docker_status": st, "exit_code": int(exit_code or 1)}

        # dead/removing/unknown => failed
        return {"state": "FAILED", "docker_status": st or "unknown", "exit_code": int(exit_code or 1)}

    def cancel(self, job_name: str, *, backend_ref: Optional[str] = None) -> None:
        self._ensure_docker()
        ref = backend_ref or job_name
        subprocess.run(["docker", "rm", "-f", ref], capture_output=True, text=True)