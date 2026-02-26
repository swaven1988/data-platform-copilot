from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        auth = request.headers.get("Authorization")

        if auth == "Bearer dev_admin_token":
            request.state.actor = "dev_admin"
            request.state.role = "admin"
            request.state.tenant_id = "default"

        elif auth == "Bearer dev_viewer_token":
            request.state.actor = "dev_viewer"
            request.state.role = "viewer"
            request.state.tenant_id = "default"

        return await call_next(request)