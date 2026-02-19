# PATCH 3 — app/api/endpoints/workspace_verify.py
# Fixes:
#  - preflight signing key (so missing key returns 400 even if job doesn't exist)
#  - pass workspace_root
#  - canonical_json_bytes can now handle ReproManifest dataclass

# REPLACE entire file with this:

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.signing.signing import (
    SigningError,
    canonical_json_bytes,
    ensure_signing_key_present,
    sign_bytes,
    verify_bytes,
)

from app.api.endpoints.workspace_repro import build_repro_manifest

router = APIRouter(tags=["workspace_repro"])


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3] / "workspace"


class VerifyRequest(BaseModel):
    job_name: str
    signature: str


@router.get("/workspace/repro/sign")
def sign_manifest(job_name: str) -> Dict[str, Any]:
    try:
        # preflight key -> deterministic 400 when missing
        ensure_signing_key_present()

        manifest = build_repro_manifest(
            workspace_root=_workspace_root(),
            job_name=job_name,
        )
        payload = canonical_json_bytes(manifest)
        sig = sign_bytes(payload)
        return {
            "job_name": job_name,
            "signature": sig,
            "kind": "workspace_repro_signature",
        }
    except SigningError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/workspace/repro/verify")
def verify_manifest(req: VerifyRequest) -> Dict[str, Any]:
    try:
        ensure_signing_key_present()

        manifest = build_repro_manifest(
            workspace_root=_workspace_root(),
            job_name=req.job_name,
        )
        payload = canonical_json_bytes(manifest)
        ok = verify_bytes(payload, req.signature)
        return {
            "job_name": req.job_name,
            "verified": bool(ok),
            "kind": "workspace_repro_verification",
        }
    except SigningError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
