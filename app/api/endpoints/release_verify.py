from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["release"])


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class TarballVerifyRequest(BaseModel):
    tarball_path: str = Field(..., description="Local filesystem path to .tar.gz")
    expected_sha256: str = Field(..., description="Expected sha256 hex digest")
    require_packaging_manifest: bool = Field(
        default=True,
        description="If true, tarball must contain packaging_manifest.json at repo root",
    )


class TarballVerifyResponse(BaseModel):
    kind: str
    tarball_path: str
    expected_sha256: str
    actual_sha256: str
    sha256_match: bool
    contains_packaging_manifest: Optional[bool] = None


@router.post("/release/verify/tarball", response_model=TarballVerifyResponse)
def verify_release_tarball(payload: TarballVerifyRequest):
    p = Path(payload.tarball_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Tarball not found: {p}")
    if not p.is_file():
        raise HTTPException(status_code=400, detail=f"Not a file: {p}")

    actual = _sha256_file(p)
    match = actual.lower() == payload.expected_sha256.strip().lower()

    contains_manifest: Optional[bool] = None
    if payload.require_packaging_manifest:
        try:
            with tarfile.open(p, mode="r:gz") as tf:
                names = tf.getnames()
            contains_manifest = "packaging_manifest.json" in names
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Unable to read tarball: {e}")

    return {
        "kind": "release_tarball_verify",
        "tarball_path": str(p),
        "expected_sha256": payload.expected_sha256,
        "actual_sha256": actual,
        "sha256_match": match,
        "contains_packaging_manifest": contains_manifest,
    }
