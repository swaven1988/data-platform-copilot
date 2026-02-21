from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth.rbac import require_role
from app.modeling.backfill_engine import generate_backfill_plan
from app.modeling.cdc_engine import build_cdc_merge_sql
from app.modeling.schema_evolution import detect_schema_changes
from app.modeling.late_arrival import late_arrival_strategy

router = APIRouter(prefix="/modeling", tags=["modeling"])


class SchemaEvolutionRequest(BaseModel):
    current_schema: dict
    new_schema: dict


@router.get("/preview-backfill")
def preview_backfill(
    start_dt: str = "2026-02-01",
    end_dt: str = "2026-02-07",
    partition_column: str = "dt",
    _=Depends(require_role("viewer")),
):
    return {
        "backfill_plan": generate_backfill_plan(start_dt, end_dt, partition_column),
    }


@router.get("/preview-cdc-merge")
def preview_cdc_merge(
    target: str = "dim_customer",
    staging: str = "staging_customer_cdc",
    pk: str = "customer_id",
    _=Depends(require_role("viewer")),
):
    return {
        "cdc_merge_sql": build_cdc_merge_sql(target, staging, pk).strip(),
    }


@router.post("/preview-schema-evolution")
def preview_schema_evolution(
    payload: SchemaEvolutionRequest,
    _=Depends(require_role("viewer")),
):
    return detect_schema_changes(payload.current_schema, payload.new_schema)


@router.get("/preview-late-arriving")
def preview_late_arriving(
    scd_type: str = "type2",
    _=Depends(require_role("viewer")),
):
    return late_arrival_strategy(scd_type)
