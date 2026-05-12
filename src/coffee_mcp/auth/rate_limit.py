"""Per-IP rate limiting middleware for unauthenticated OAuth/H5 endpoints.

Prevents trivial DoS / session-id enumeration on the routes that don't
require a bearer token. Authenticated MCP tool calls have their own
per-user limiter in toc_server.py.

Defaults are intentionally generous (60 req/min per IP across guarded
routes). Override via env vars:
  COFFEE_OAUTH_RL_MAX     — max calls per window (default 60)
  COFFEE_OAUTH_RL_WINDOW  — window seconds (default 60)
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


# Path prefixes whose unauthenticated access is gated by this middleware.
GUARDED_PREFIXES: tuple[str, ...] = (
    "/oauth/session/",
    "/oauth/login_start",
    "/oauth/callback",
    "/h5/login",       # covers /h5/login and /h5/login/submit
    "/h5/step_up",
    "/mock-as/",
)


class IPRateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window per-IP limiter.

    Implementation mirrors `toc_server.py:_RateLimit.check()` but keyed by IP
    instead of user_id. State is process-local; for multi-replica deployments
    swap to a shared backend.
    """

    def __init__(self, app, max_calls: int | None = None,
                 window_seconds: int | None = None,
                 guarded_prefixes: tuple[str, ...] = GUARDED_PREFIXES):
        super().__init__(app)
        self.max_calls = max_calls or int(os.environ.get("COFFEE_OAUTH_RL_MAX", "60"))
        self.window = window_seconds or int(os.environ.get("COFFEE_OAUTH_RL_WINDOW", "60"))
        self.prefixes = guarded_prefixes
        self._calls: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._last_cleanup: float = 0.0

    def _is_guarded(self, path: str) -> bool:
        return any(path.startswith(p) for p in self.prefixes)

    def _check(self, ip: str) -> bool:
        now = time.monotonic()
        with self._lock:
            # Periodic full cleanup
            if now - self._last_cleanup > self.window * 5:
                stale = [k for k, ts in self._calls.items()
                         if not ts or now - ts[-1] > self.window]
                for k in stale:
                    del self._calls[k]
                self._last_cleanup = now
            bucket = self._calls[ip]
            self._calls[ip] = [t for t in bucket if now - t < self.window]
            if len(self._calls[ip]) >= self.max_calls:
                return False
            self._calls[ip].append(now)
            return True

    async def dispatch(self, request: Request, call_next):
        if not self._is_guarded(request.url.path):
            return await call_next(request)

        ip = request.headers.get("x-forwarded-for") or \
             (request.client.host if request.client else "0.0.0.0")
        ip = ip.split(",")[0].strip()
        if not self._check(ip):
            return JSONResponse(
                {"error": "rate_limited",
                 "message": "Too many requests from your IP for this endpoint."},
                status_code=429,
                headers={"Retry-After": str(self.window)},
            )
        return await call_next(request)
