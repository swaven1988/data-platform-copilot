from __future__ import annotations

import os
from fastapi import APIRouter
from starlette.responses import JSONResponse

router = APIRouter()

@router.get("/api/v1/health/live")
def liveness():
    return {"status": "alive"}

@router.get("/api/v1/health/ready")
def readiness():
    """
    Readiness should reflect ability to serve real traffic.
    Keep checks fast + local (no slow downstream calls).
    """
    problems: list[str] = []

    # 1) Secrets present (prod expects file-based)
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
            val = (open(p, "r", encoding="utf-8").read() or "").strip()
            if not val:
                problems.append(f"empty_file:{env_key}={p}")
        except Exception as e:
            problems.append(f"unreadable_file:{env_key}={p} err={type(e).__name__}")

    # 2) Workspace root should be writable for temp work (even if container is read-only)
    # We rely on /tmp tmpfs in compose.
    try:
        test_path = "/tmp/copilot_ready_check.tmp"
        with open(test_path, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test_path)
    except Exception:
        problems.append("tmp_not_writable")

    if problems:
        return JSONResponse(status_code=503, content={"status": "not_ready", "problems": problems})

    return {"status": "ready"}