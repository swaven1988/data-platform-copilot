from typing import Dict
from .base import ExecutionBackend


class AirflowBackend(ExecutionBackend):
    name = "airflow"

    def submit(self, job_name: str, config: Dict) -> Dict:
        # placeholder — REST trigger later
        return {"dag_run": job_name}

    def status(self, job_name: str) -> str:
        return "RUNNING"

    def cancel(self, job_name: str) -> None:
        pass