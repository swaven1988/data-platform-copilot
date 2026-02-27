from __future__ import annotations

import os

from fastapi import APIRouter
from starlette.responses import JSONResponse

from app.core.observability.metrics import inc_named

router = APIRouter()


# ------------------------------------------------------------
# Unversioned health
# ------------------------------------------------------------
@router.get("/health/live")
async def live():
    inc_named("health_live")
    return {"status": "ok"}


@router.get("/health/ready")
async def ready():
    inc_named("health_ready")
    return {"status": "ready"}


# ------------------------------------------------------------
# Versioned health
# ------------------------------------------------------------
@router.get("/api/v1/health/live")
def liveness():
    inc_named("health_live")
    return {"status": "alive"}


@router.get("/api/v1/health/ready")
def readiness():
    """
    Readiness reflects ability to serve traffic.
    In non-prod environments, skip strict secret validation.
    """
    inc_named("health_ready")

    env = (os.getenv("COPILOT_ENV") or "dev").strip().lower()
    problems: list[str] = []

    # In dev/test, do not enforce file-based secret checks
    if env == "prod":
        for env_key in (
            "COPILOT_STATIC_ADMIN_TOKEN_FILE",
            "COPILOT_STATIC_VIEWER_TOKEN_FILE",
            "COPILOT_SIGNING_KEY_FILE",
        ):
            p = os.getenv(env_key)
            if not p:
                problems.append(f"missing_env:{env_key}")
                continue

            try:
                if not os.path.exists(p):
                    problems.append(f"missing_file:{env_key}={p}")
                    continue

                with open(p, "r", encoding="utf-8") as f:
                    val = (f.read() or "").strip()

                if not val:
                    problems.append(f"empty_file:{env_key}={p}")

            except Exception as e:
                problems.append(f"unreadable_file:{env_key}={p} err={type(e).__name__}")

    # temp file check (always safe)
    try:
        test_path = "/tmp/copilot_ready_check.tmp"
        with open(test_path, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test_path)
    except Exception:
        problems.append("tmp_not_writable")

    if problems:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "problems": problems},
        )

    return {"status": "ready"}