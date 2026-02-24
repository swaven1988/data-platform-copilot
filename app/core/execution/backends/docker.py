import subprocess
from typing import Dict
from .base import ExecutionBackend


class DockerBackend(ExecutionBackend):
    name = "docker"

    def submit(self, job_name: str, config: Dict) -> Dict:
        image = config.get("image")
        cmd = ["docker", "run", "--rm", "--name", job_name, image]
        subprocess.Popen(cmd)
        return {"container": job_name}

    def status(self, job_name: str) -> str:
        return "RUNNING"

    def cancel(self, job_name: str) -> None:
        subprocess.call(["docker", "rm", "-f", job_name])