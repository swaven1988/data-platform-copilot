from typing import Dict
from .base import ExecutionBackend


class K8sBackend(ExecutionBackend):
    name = "k8s"

    def submit(self, job_name: str, config: Dict) -> Dict:
        # placeholder — real k8s client later
        return {"k8s_job": job_name}

    def status(self, job_name: str) -> str:
        return "RUNNING"

    def cancel(self, job_name: str) -> None:
        pass