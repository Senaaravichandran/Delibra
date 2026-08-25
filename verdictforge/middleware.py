"""Request identity, security headers, API authentication, and local rate limiting."""

import asyncio
import hmac
import logging
import re
from collections import defaultdict, deque
from time import monotonic, perf_counter
from uuid import uuid4

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from verdictforge.config import Settings

logger = logging.getLogger("delibra.http")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,128}$")


class ProductionMiddleware(BaseHTTPMiddleware):
    """Apply lightweight production safeguards without external infrastructure."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._rate_lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = perf_counter()
        supplied_id = request.headers.get("X-Request-ID", "")
        request_id = supplied_id if REQUEST_ID_PATTERN.fullmatch(supplied_id) else str(uuid4())
        request.state.request_id = request_id

        rejection = await self._authorize(request, request_id)
        if rejection is not None:
            return rejection

        response = await call_next(request)
        duration_ms = round((perf_counter() - started) * 1000, 1)
        self._apply_headers(response, request, request_id)
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%s request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response

    async def _authorize(self, request: Request, request_id: str) -> Response | None:
        if request.method != "POST" or not request.url.path.startswith("/api/v1/"):
            return None

        if self.settings.api_key:
            supplied = request.headers.get("X-API-Key", "")
            if not hmac.compare_digest(supplied, self.settings.api_key):
                return self._error(
                    status.HTTP_401_UNAUTHORIZED,
                    "A valid X-API-Key header is required.",
                    request_id,
                )

        client = request.client.host if request.client else "unknown"
        now = monotonic()
        async with self._rate_lock:
            recent = self._requests[client]
            while recent and recent[0] <= now - 60:
                recent.popleft()
            if len(recent) >= self.settings.rate_limit_per_minute:
                return self._error(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "Debate creation rate limit exceeded. Try again shortly.",
                    request_id,
                    retry_after="60",
                )
            recent.append(now)
        return None

    @staticmethod
    def _error(
        status_code: int,
        detail: str,
        request_id: str,
        *,
        retry_after: str | None = None,
    ) -> JSONResponse:
        headers = {"X-Request-ID": request_id}
        if retry_after:
            headers["Retry-After"] = retry_after
        response = JSONResponse({"detail": detail}, status_code=status_code, headers=headers)
        ProductionMiddleware._apply_headers(response, None, request_id)
        return response

    @staticmethod
    def _apply_headers(response: Response, request: Request | None, request_id: str) -> None:
        path = request.url.path if request else ""
        docs_policy = path.startswith(("/api/docs", "/api/redoc"))
        policy = (
            "default-src 'self' https: data:; script-src 'self' 'unsafe-inline' https:; "
            "style-src 'self' 'unsafe-inline' https:; img-src 'self' https: data:"
            if docs_policy
            else "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; base-uri 'self'; frame-ancestors 'none'"
        )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = policy
