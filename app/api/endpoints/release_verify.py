from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.release.verify import verify_release_tarball

router = APIRouter(tags=["release"])


class ReleaseVerifyRequest(BaseModel):
    artifact_path: str = Field(..., description="Local filesystem path to release tar.gz")
    sha256: Optional[str] = Field(None, description="Expected sha256 of artifact (optional)")
    strict_no_extras: bool = Field(
        False, description="If true, fail when tar contains extra files not listed in manifest"
    )
    require_packaging_manifest: bool = Field(
        True, description="If false, only sha256 is verified (legacy)"
    )


@router.post("/api/v2/release/verify", operation_id="v2_release_verify")
def verify_release(req: ReleaseVerifyRequest, x_tenant: Optional[str] = Header(default=None)) -> dict:
    # Middleware enforces tenant; keep defensive check.
    if not x_tenant:
        raise HTTPException(status_code=400, detail="Missing X-Tenant header")

    out = verify_release_tarball(
        req.artifact_path,
        expected_sha256=req.sha256,
        strict_no_extras=req.strict_no_extras,
        require_packaging_manifest=req.require_packaging_manifest,
    )
    if out.get("error"):
        err = out["error"]
        if "artifact not found" in err:
            raise HTTPException(status_code=404, detail=err)
        raise HTTPException(status_code=400, detail=err)
    return out


# ---- Legacy endpoint (kept for backwards-compat tests) ----
class LegacyTarballVerifyRequest(BaseModel):
    tarball_path: str = Field(..., description="Local filesystem path to tar.gz")
    expected_sha256: Optional[str] = Field(None, description="Expected sha256")
    require_packaging_manifest: bool = Field(True, description="If false, sha-only verify")


@router.post("/release/verify/tarball", operation_id="legacy_release_verify_tarball")
def verify_release_legacy(req: LegacyTarballVerifyRequest) -> dict:
    out = verify_release_tarball(
        req.tarball_path,
        expected_sha256=req.expected_sha256,
        require_packaging_manifest=req.require_packaging_manifest,
        strict_no_extras=False,
    )
    if out.get("error"):
        err = out["error"]
        if "artifact not found" in err:
            raise HTTPException(status_code=404, detail=err)
        raise HTTPException(status_code=400, detail=err)
    return out
