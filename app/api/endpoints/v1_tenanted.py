from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth.rbac import require_roles
from app.core.federation.federation_manager import (
    FederatedRepoSpec,
    load_federation_config,
    upsert_repo,
    sync_all,
    sync_repo,
)
from app.api.endpoints.workspace_repro import build_repro_manifest
from app.core.signing.signing import canonical_json_bytes, ensure_signing_key_present, sign_bytes, verify_bytes


router = APIRouter(prefix="/v1", tags=["v1"])


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _workspace_root_for_tenant(tenant: str) -> Path:
    # Multi-tenant isolation in workspace/tenants/{tenant}/...
    # Does not break existing workspace/ layout.
    return _project_root() / "workspace" / "tenants" / tenant


@router.get("/tenants/{tenant}/health")
def tenant_health(tenant: str) -> Dict[str, Any]:
    return {"tenant": tenant, "status": "ok", "kind": "tenant_health"}


# -------------------------
# Federation (tenant scoped)
# -------------------------

@router.get("/tenants/{tenant}/federation/config")
def federation_config(tenant: str, job_name: str) -> Dict[str, Any]:
    ws_root = _workspace_root_for_tenant(tenant)
    return load_federation_config(ws_root, job_name)


@router.post("/tenants/{tenant}/federation/connect")
def federation_connect(
    tenant: str,
    payload: Dict[str, Any],
    _principal=Depends(require_roles(["admin"])),
) -> Dict[str, Any]:
    ws_root = _workspace_root_for_tenant(tenant)

    try:
        spec = FederatedRepoSpec(
            name=str(payload["name"]),
            url=str(payload["url"]),
            ref=str(payload.get("ref", "main")),
            subdir=payload.get("subdir"),
            paths=payload.get("paths"),
        )
        job_name = str(payload["job_name"])
        upsert_repo(ws_root, job_name, spec)

        if bool(payload.get("sync", False)):
            res = sync_repo(ws_root, job_name, spec)
            return {"kind": "federation_connect", "job_name": job_name, "repo": res}

        return {"kind": "federation_connect", "job_name": job_name, "repo": {"name": spec.name}}
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing field: {e}")


@router.post("/tenants/{tenant}/federation/sync")
def federation_sync(
    tenant: str,
    job_name: str,
    _principal=Depends(require_roles(["admin"])),
) -> Dict[str, Any]:
    ws_root = _workspace_root_for_tenant(tenant)
    return sync_all(ws_root, job_name)


# -------------------------
# Repro + Signing (tenant scoped)
# -------------------------

@router.get("/tenants/{tenant}/workspace/repro/manifest")
def tenant_repro_manifest(tenant: str, job_name: str) -> Dict[str, Any]:
    ws_root = _workspace_root_for_tenant(tenant)
    m = build_repro_manifest(workspace_root=ws_root, job_name=job_name)
    # return as jsonable (dataclass)
    return {
        "kind": "workspace_repro_manifest",
        "tenant": tenant,
        "manifest": m.__dict__ if hasattr(m, "__dict__") else m,
    }


@router.get("/tenants/{tenant}/workspace/repro/sign")
def tenant_repro_sign(
    tenant: str,
    job_name: str,
    _principal=Depends(require_roles(["admin", "user"])),
) -> Dict[str, Any]:
    ensure_signing_key_present()
    ws_root = _workspace_root_for_tenant(tenant)
    manifest = build_repro_manifest(workspace_root=ws_root, job_name=job_name)
    payload = canonical_json_bytes(manifest)
    sig = sign_bytes(payload)
    return {
        "kind": "workspace_repro_signature",
        "tenant": tenant,
        "job_name": job_name,
        "signature": sig,
    }


@router.post("/tenants/{tenant}/workspace/repro/verify")
def tenant_repro_verify(
    tenant: str,
    body: Dict[str, Any],
    _principal=Depends(require_roles(["admin", "user"])),
) -> Dict[str, Any]:
    ensure_signing_key_present()
    job_name = str(body.get("job_name", "")).strip()
    signature = str(body.get("signature", "")).strip()
    if not job_name or not signature:
        raise HTTPException(status_code=400, detail="job_name and signature are required")

    ws_root = _workspace_root_for_tenant(tenant)
    manifest = build_repro_manifest(workspace_root=ws_root, job_name=job_name)
    payload = canonical_json_bytes(manifest)
    ok = verify_bytes(payload, signature)
    return {
        "kind": "workspace_repro_verification",
        "tenant": tenant,
        "job_name": job_name,
        "verified": bool(ok),
    }
