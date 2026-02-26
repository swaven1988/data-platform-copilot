from fastapi import APIRouter, Depends

from app.core.auth.rbac import require_role
from app.modeling.registry import get_model

router = APIRouter(prefix="/modeling", tags=["modeling"])


@router.get("/{name}")
def modeling_get(name: str, _=Depends(require_role("viewer"))):
    return {"name": name, "spec": get_model(name)}
