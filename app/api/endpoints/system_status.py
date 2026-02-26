from fastapi import APIRouter, Depends
from app.core.auth.rbac_ext import require_roles
from app.core.observability.metrics import snapshot
from app.core.supply_chain.verification import verify_artifact_integrity
from pathlib import Path

router = APIRouter()


@router.get(
    "/system/status",
    dependencies=[Depends(require_roles("admin"))],
)
def system_status():
    return {
        "metrics": snapshot(),
        "artifact": verify_artifact_integrity(
            Path("data-platform-copilot-v0.13.3.tar.gz"),
            Path("data-platform-copilot-v0.13.3.tar.gz.sha256"),
        ),
    }