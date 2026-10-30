"""Performance middleware — Sprint 8 Part 4.

Two responsibilities:

  1. **Response compression.** Attach Starlette's GZipMiddleware so
     JSON / text responses larger than the configured minimum are
     served as ``Content-Encoding: gzip``. nginx is the public
     compressor; this is the in-process backup for direct-to-
     backend traffic (dev, tests, ops runs ``curl`` against
     ``localhost:8001``).

  2. **Cache headers on the health surface.** ``/health`` and
     ``/health/ready`` change on every request, so the middleware
     stamps ``Cache-Control: no-store, max-age=0`` so a CDN /
     browser does not serve a stale readiness verdict. The
     ``/metrics`` endpoint is also marked no-store so a
     Prometheus scraper retry never sees a cached payload.

The middleware is order-sensitive. ``install_performance`` wires
the compressor so it sits INSIDE the security headers (so the
``Content-Encoding: gzip`` header is included in the security
header audit) but OUTSIDE the request handlers (so it can
short-circuit on small payloads).
"""

from __future__ import annotations

from typing import Iterable

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.config.settings import get_settings


# Paths whose responses must NEVER be cached by an intermediary.
# /health/live is the only one the spec explicitly carves out
# (liveness must always reflect the current process state) but
# the readiness + metrics endpoints have the same characteristic
# and an operator who caches a 200 ready verdict will miss a
# subsequent 503 forever.
_NO_CACHE_PATHS: tuple[str, ...] = (
    "/health",
    "/health/live",
    "/health/ready",
    "/metrics",
)


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Stamp ``Cache-Control`` on the always-fresh endpoints.

    The values come from settings so an operator who wants a
    1-second ``max-age`` on /health for a high-traffic dashboard
    can opt-in without touching code. The default is
    ``no-store, max-age=0`` which is the safest.
    """

    def __init__(self, app: ASGIApp, *, no_cache_paths: Iterable[str] = _NO_CACHE_PATHS) -> None:
        super().__init__(app)
        self._settings = get_settings()
        self._no_cache_paths = frozenset(no_cache_paths)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response: Response = await call_next(request)
        if request.url.path in self._no_cache_paths:
            response.headers["Cache-Control"] = (
                self._settings.health_response_cache_control
            )
        return response


def install_performance(app: FastAPI) -> None:
    """Attach the performance middleware to the FastAPI app.

    Starlette ``add_middleware`` appends; the most-recently-added
    middleware becomes the OUTERMOST. The desired order from
    outside-in is:

        CORS  →  security (headers / size / rate)  →  monitoring
              →  performance (gzip + cache-control) → app

    So we add in reverse: performance first, then the other layers
    are added on top. In practice ``install_performance`` is the
    last installer called by ``create_app``, so it ends up at the
    inside of the security stack (which is what we want — the
    413 / 429 error envelopes still flow through GZipMiddleware).
    """
    settings = get_settings()
    if settings.gzip_enabled:
        app.add_middleware(
            GZipMiddleware,
            minimum_size=settings.gzip_minimum_size,
            compresslevel=settings.gzip_compress_level,
        )
    app.add_middleware(CacheControlMiddleware)


__all__ = [
    "CacheControlMiddleware",
    "install_performance",
]
