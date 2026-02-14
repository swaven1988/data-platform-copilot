from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas.advisors import AdvisorsRunRequest, AdvisorsRunResponse, AdvisorFindingModel
from app.plugins.advisors._internal.config import AdvisorsRunConfig
from app.plugins.advisors._internal.registry import PluginRegistry

router = APIRouter()


def _registry() -> PluginRegistry:
    reg = PluginRegistry("app/plugins/advisors")
    reg.load_all()
    return reg


@router.post("/advisors/run", response_model=AdvisorsRunResponse)
def run_advisors(req: AdvisorsRunRequest):
    reg = _registry()
    cfg = AdvisorsRunConfig(
        enabled=req.advisors.enabled,
        disabled=req.advisors.disabled,
        options=req.advisors.options,
    )
    findings = reg.run(context=req.context, cfg=cfg)
    return AdvisorsRunResponse(
        plugin_fingerprint=reg.fingerprint,
        findings=[AdvisorFindingModel(**f.__dict__) for f in findings],
    )
