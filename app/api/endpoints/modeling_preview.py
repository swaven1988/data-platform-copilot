from fastapi import APIRouter

from app.intelligence.model_planner import ModelPlanner
from app.modeling.model_spec import (
    ModelSpec,
    PartitionSpec,
    ChangeDetectionSpec,
    SCDSpec,
)

router = APIRouter(prefix="/modeling", tags=["modeling"])


@router.get("/preview-scd2")
def preview_scd2():
    model_spec = ModelSpec(
        table_name="dim_customer",
        model_type="scd2",
        columns=["customer_id", "name", "email", "city", "updated_at"],
        partition=PartitionSpec(strategy="none"),
        scd=SCDSpec(
            type="scd2",
            natural_keys=["customer_id"],
            surrogate_key="customer_sk",
            change_detection=ChangeDetectionSpec(
                strategy="hash",
                columns=["name", "email", "city"],
            ),
        ),
    )

    return ModelPlanner.plan(model_spec)
