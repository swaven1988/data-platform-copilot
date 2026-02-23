from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
from app.core.compiler.contract_models import DataPipelineContract
from app.core.compiler.contract_engine import ContractEngine

router = APIRouter(prefix="/api/v2/contracts", tags=["contracts"])

WORKSPACE_ROOT = Path("workspace")
engine = ContractEngine(WORKSPACE_ROOT)


@router.post("/create")
def create_contract(contract: DataPipelineContract):
    result = engine.create_contract(contract)
    return result


@router.get("/{job_name}/{contract_hash}")
def get_contract(job_name: str, contract_hash: str):
    contract = engine.load_contract(job_name, contract_hash)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract.model_dump()