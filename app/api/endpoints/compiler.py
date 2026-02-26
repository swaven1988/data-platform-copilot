from fastapi import APIRouter
from app.core.compiler.contracts import DataPipelineContract
from app.core.compiler.dq_engine import infer_basic_rules
from app.core.compiler.spark_optimizer import recommend_spark_config
from app.core.compiler.simulator import simulate_execution
from app.core.compiler.artifact_registry import ArtifactRegistry
from pathlib import Path

router = APIRouter(prefix="/api/v2/compiler")

registry = ArtifactRegistry(Path("workspace/.artifacts"))


@router.post("/contract/hash")
def hash_contract(contract: DataPipelineContract):
    return {"hash": contract.deterministic_hash()}


@router.post("/dq/infer")
def dq_infer(schema: dict):
    rules = infer_basic_rules(schema)
    return {"rules": [r.model_dump() for r in rules]}


@router.post("/spark/recommend")
def spark_recommend(data_gb: float, joins: int, sla_minutes: int):
    return recommend_spark_config(data_gb, joins, sla_minutes)


@router.post("/simulate")
def simulate(data_gb: float, joins: int, sla_minutes: int):
    return simulate_execution(data_gb, joins, sla_minutes)