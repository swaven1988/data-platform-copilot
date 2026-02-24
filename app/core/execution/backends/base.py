from abc import ABC, abstractmethod
from typing import Dict


class ExecutionBackend(ABC):
    name: str

    @abstractmethod
    def submit(self, job_name: str, config: Dict) -> Dict:
        ...

    @abstractmethod
    def status(self, job_name: str) -> str:
        ...

    @abstractmethod
    def cancel(self, job_name: str) -> None:
        ...