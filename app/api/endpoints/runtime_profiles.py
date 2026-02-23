from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.compiler.contract_engine import ContractEngine
from app.core.runtime_profiles.registry import RuntimeProfileRegistry
from app.core.runtime_profiles.compiler import (
    compile_runtime_profile,
    compile_spark_conf_for_contract,
)


router = APIRouter(prefix="/api/v2/runtime-profiles", tags=["runtime_profiles"])

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = Path("workspace")

contract_engine = ContractEngine(WORKSPACE_ROOT)


class ResolveRuntimeProfileRequest(BaseModel):
    job_name: str
    contract_hash: str

    profile_name: Optional[str] = None
    pricing_overrides: Dict[str, Any] = Field(default_factory=dict)

    # If spec is provided, we merge into final spark_conf (spark.app.name, dyn alloc, overrides)
    spec: Optional[Dict[str, Any]] = None


@router.get("/")
def list_profiles():
    reg = RuntimeProfileRegistry(PROJECT_ROOT)
    return {
        "profiles": reg.list_names(),
    }


@router.get("/{name}")
def get_profile(name: str):
    reg = RuntimeProfileRegistry(PROJECT_ROOT)
    rp = reg.get(name)
    if rp is None:
        raise HTTPException(status_code=404, detail="Runtime profile not found")
    return rp.model_dump()


@router.post("/resolve")
def resolve_profile(req: ResolveRuntimeProfileRequest):
    contract = contract_engine.load_contract(req.job_name, req.contract_hash)
    if not contract:
        raise HTTPException(status_code=400, detail="Invalid contract hash")

    if req.spec is None:
        spark_conf_obj, cluster = compile_runtime_profile(
            project_root=PROJECT_ROOT,
            contract=contract,
            profile_name=req.profile_name,
            pricing_overrides=req.pricing_overrides,
            spark_conf_overrides={},
        )
    else:
        # Spec is optional and accepted as dict to keep API stable.
        # We construct CopilotSpec lazily via existing schema.
        from app.core.spec_schema import CopilotSpec

        spec = CopilotSpec(**req.spec)
        spark_conf_obj, cluster = compile_spark_conf_for_contract(
            project_root=PROJECT_ROOT,
            contract=contract,
            spec=spec,
            profile_name=req.profile_name,
            pricing_overrides=req.pricing_overrides,
        )

    return {
        "job_name": req.job_name,
        "contract_hash": req.contract_hash,
        "runtime_profile": spark_conf_obj.get("metadata", {}).get("runtime_profile"),
        "spark_conf": spark_conf_obj,
        "cluster_profile": cluster.model_dump(),
    }