from fastapi import APIRouter
from pathlib import Path
from app.core.supply_chain.verification import verify_artifact_integrity

router = APIRouter()


@router.get("/supply-chain/verify-artifact")
def verify_artifact():
    artifact = Path("data-platform-copilot-v0.10.8.tar.gz")
    sha_file = Path("data-platform-copilot-v0.10.8.tar.gz.sha256")
    return verify_artifact_integrity(artifact, sha_file)