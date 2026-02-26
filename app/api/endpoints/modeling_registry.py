from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth.rbac import require_role
from app.modeling.registry import register_model, list_models

router = APIRouter(prefix="/modeling", tags=["modeling"])


class RegisterModelRequest(BaseModel):
    name: str
    spec: dict


@router.get("/list")
def modeling_list(_=Depends(require_role("viewer"))):
    return {"models": list_models()}


@router.post("/register")
def modeling_register(payload: RegisterModelRequest, _=Depends(require_role("admin"))):
    register_model(payload.name, payload.spec)
    return {"status": "registered", "model": payload.name, "version": 1}
