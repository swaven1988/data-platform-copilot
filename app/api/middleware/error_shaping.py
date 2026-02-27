from __future__ import annotations

import logging
import traceback
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

log = logging.getLogger("copilot.errors")


class SafeErrorMiddleware(BaseHTTPMiddleware):
    """
    - Never return stack traces to clients
    - Preserve request_id if present
    - Log traceback server-side
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except Exception as e:
            rid = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")
            log.error(
                "Unhandled error: %s rid=%s path=%s\n%s",
                str(e),
                rid,
                request.url.path,
                traceback.format_exc(),
            )
            payload = {"detail": "Internal Server Error"}
            if rid:
                payload["request_id"] = rid
            return JSONResponse(status_code=500, content=payload)