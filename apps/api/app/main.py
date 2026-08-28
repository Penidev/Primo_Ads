"""FastAPI application entry point.

Wires up configuration, middleware (CORS + security headers), and routers.
Importing settings at module load triggers fail-fast env validation (Req 1.5).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.config import settings
from app.services.monitoring_service import capture_exception, init_monitoring
from app.utils.tokens import TokenError, decode_token


MAX_REQUEST_BYTES = 25 * 1024 * 1024  # 25 MB hard ceiling for any request body


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply baseline security headers to every response (SECURITY.md §6)."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized bodies early, before they are buffered."""

    async def dispatch(self, request: Request, call_next):
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_REQUEST_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large."},
            )
        return await call_next(request)


class RequestIdentityMiddleware(BaseHTTPMiddleware):
    """Attach the caller's user id to request.state for per-user rate limiting.

    This is a best-effort read of the access token for throttling only. It is
    never used for authorization; routes still resolve identity through the
    verified `get_current_user` dependency.
    """

    async def dispatch(self, request: Request, call_next):
        token = None
        auth = request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth[7:]
        if token is None:
            token = request.cookies.get("access_token")
        if token:
            try:
                payload = decode_token(token, expected_type="access")
                request.state.user_id = payload.get("sub")
            except TokenError:
                pass
        return await call_next(request)


def create_app() -> FastAPI:
    # Initialise error monitoring before anything can fail.
    init_monitoring()

    app = FastAPI(
        title="Primo API",
        version="0.1.0",
        description="AI Ad Production Platform backend",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
    )

    # Order matters: identity is resolved before handlers run so rate limiting
    # can bucket per user; size limiting runs earliest to shed large bodies.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdentityMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(health_router)
    app.include_router(api_router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Report the failure, but never leak internals to the client."""
        capture_exception(
            exc,
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred."},
        )

    return app


app = create_app()
