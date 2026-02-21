from fastapi import APIRouter

router = APIRouter()

@router.get("/api/v1/health/live")
def liveness():
    return {"status": "alive"}

@router.get("/api/v1/health/ready")
def readiness():
    # Keep simple for now; add dependency checks later if needed
    return {"status": "ready"}