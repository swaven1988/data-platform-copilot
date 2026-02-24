import subprocess
from typing import Dict
from .base import ExecutionBackend


class LocalBackend(ExecutionBackend):
    name = "local"

    def submit(self, job_name: str, config: Dict) -> Dict:
        cmd = config.get("command", ["echo", f"Running {job_name}"])
        proc = subprocess.Popen(cmd)
        return {"pid": proc.pid}

    def status(self, job_name: str) -> str:
        return "SUCCEEDED"

    def cancel(self, job_name: str) -> None:
        pass