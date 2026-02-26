from pathlib import Path
from typing import Optional
import json
from .contract_models import DataPipelineContract


class ContractEngine:

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root

    def _contract_dir(self, job_name: str) -> Path:
        path = self.workspace_root / job_name / ".copilot" / "contracts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def create_contract(self, contract: DataPipelineContract) -> dict:
        contract_hash = contract.deterministic_hash()
        contract_dir = self._contract_dir(contract.job_name)
        contract_path = contract_dir / f"{contract_hash}.json"

        if not contract_path.exists():
            contract_path.write_text(
                json.dumps(
                    contract.model_dump(),
                    sort_keys=True,
                    indent=2
                )
            )

        return {
            "contract_hash": contract_hash,
            "stored": True,
            "path": str(contract_path)
        }

    def load_contract(
        self,
        job_name: str,
        contract_hash: str
    ) -> Optional[DataPipelineContract]:

        contract_path = (
            self.workspace_root
            / job_name
            / ".copilot"
            / "contracts"
            / f"{contract_hash}.json"
        )

        if not contract_path.exists():
            return None

        data = json.loads(contract_path.read_text())
        return DataPipelineContract(**data)