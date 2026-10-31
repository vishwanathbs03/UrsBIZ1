"""Monitoring middleware for Atlas AI.

Sprint 8 Part 2 — Monitoring & Observability.

This module installs three middlewares on the FastAPI app:

  * :class:`RequestIdMiddleware` — generates (or propagates) an
    ``X-Request-ID`` for every request and stores it in
    ``request.state`` so downstream handlers can read it.
  * :class:`AccessLogMiddleware` — emits a structured JSON access log
    on every response (success or error) with the request_id, method,
    path, duration, status, and (when available) the authenticated
    user id.
  * :class:`ErrorHandlerMiddleware` — catches uncaught exceptions,
    logs the stack trace, increments the Prometheus exception counter,
    and returns the same ``{"detail": "..."}`` JSON envelope every
    other FastAPI error uses.

The middleware is order-sensitive. ``install_monitoring`` registers
them in the correct order so:
  * request-id is the OUTERMOST (so every other middleware / handler
    sees the populated ``request.state.request_id``),
  * access log is INSIDE the request-id (so the access log has the id),
  * error handler is the INNERMOST (so its exception handler is the
    last stop before the response is built).
"""

from __future__ import annotations

import logging
import time
import traceback
import uuid
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.monitoring.logging import RequestTimer, get_access_logger
from app.monitoring.metrics import (
    EXCEPTION_COUNT,
    REQUEST_ACTIVE,
    REQUEST_DURATION,
    REQUEST_TOTAL,
    STATUS_COUNT,
)


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_ATTR = "request_id"
TIMER_ATTR = "_atlas_timer"

# Per the spec we MUST NOT log secrets. The redaction logic in
# app.monitoring.logging handles structured fields; this list is the
# belt-and-braces blacklist of HTTP request headers whose VALUE we
# never copy into a log line.
_LOG_FORBIDDEN_HEADERS = frozenset({
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
})


# --------------------------------------------------------------------------- #
# Request ID
# --------------------------------------------------------------------------- #


def _ensure_request_id(request: Request) -> str:
    """Return the inbound request id, or mint a new one."""
    inbound = request.headers.get(REQUEST_ID_HEADER)
    if inbound and len(inbound) <= 128:
        # Propagate a caller-supplied id when it is reasonable. We
        # cap at 128 chars to bound log noise / cardinality.
        return inbound
    return uuid.uuid4().hex


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach / propagate ``X-Request-ID`` for every request.

    The id is stored in ``request.state.request_id`` so handlers can
    read it (e.g. to include in business-logic log lines) and echoed
    back in the response header so the client can correlate its own
    logs with ours.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = _ensure_request_id(request)
        request.state.request_id = request_id
        request.state._atlas_timer = RequestTimer()
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


# --------------------------------------------------------------------------- #
# Access log + metrics
# --------------------------------------------------------------------------- #


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Emit a JSON access log + Prometheus request metrics per request.

    Skips the ``/metrics`` endpoint itself so the scraper does not
    create an ever-growing time series of "the scraper is scraping
    us" samples. All other endpoints are recorded.
    """

    def __init__(self, app, *, access_logger: logging.Logger | None = None) -> None:
        super().__init__(app)
        self._logger = access_logger or get_access_logger()

    @staticmethod
    def _endpoint_label(request: Request) -> str:
        """Return the URL path template for the request.

        Using the route template (e.g. ``/api/v1/business/{id}``)
        instead of the raw path keeps label cardinality bounded. If
        the route has not been resolved (e.g. for a 404 to a non-
        existing path), we fall back to the literal path so unknown
        endpoints still show up in the dashboard.
        """
        route = request.scope.get("route")
        path_template = getattr(route, "path", None) if route else None
        return path_template or request.url.path

    @staticmethod
    def _user_id(request: Request) -> int | None:
        """Return the authenticated user id if FastAPI has resolved it.

        ``get_current_user`` populates ``request.state.user`` as a
        side-effect of the dependency. We do NOT call it here (we are
        not on the auth code path) — we just read what the dependency
        already wrote.
        """
        user = getattr(request.state, "user", None)
        if user is None:
            return None
        uid = getattr(user, "id", None)
        return int(uid) if isinstance(uid, (int, str)) else None

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        endpoint = self._endpoint_label(request)
        method = request.method
        timer: RequestTimer | None = getattr(request.state, TIMER_ATTR, None)
        if timer is None:
            timer = RequestTimer()
            setattr(request.state, TIMER_ATTR, timer)

        # Skip metrics + access log for the Prometheus scrape path.
        if endpoint == "/metrics":
            return await call_next(request)

        REQUEST_ACTIVE.labels(method=method, endpoint=endpoint).inc()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = timer.elapsed_ms()
            REQUEST_ACTIVE.labels(method=method, endpoint=endpoint).dec()
            REQUEST_TOTAL.labels(
                method=method, endpoint=endpoint, status=str(status_code),
            ).inc()
            STATUS_COUNT.labels(
                method=method, endpoint=endpoint, status=str(status_code),
            ).inc()
            REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(
                duration / 1000.0,
            )
            service_status = "ok" if status_code < 400 else ("error" if status_code >= 500 else "warning")
            error_cat = None
            if status_code == 429:
                error_cat = "rate_limit"
            elif status_code in {401, 403}:
                error_cat = "auth"
            elif status_code == 422:
                error_cat = "validation"
            elif status_code == 503:
                error_cat = "service_unavailable"
            elif status_code >= 500:
                error_cat = "internal_error"

            self._logger.info(
                "request",
                extra={
                    "request_id": getattr(
                        request.state, REQUEST_ID_ATTR, None
                    ),
                    "method": method,
                    "path": endpoint,
                    "endpoint": endpoint,
                    "duration_ms": round(duration, 3),
                    "execution_duration_ms": round(duration, 3),
                    "status": status_code,
                    "service_status": service_status,
                    "error_category": error_cat,
                    "retry_count": getattr(request.state, "retry_count", 0),
                    "fallback_usage": getattr(request.state, "fallback_usage", False),
                    "user_id": self._user_id(request),
                },
            )


# --------------------------------------------------------------------------- #
# Error handler
# --------------------------------------------------------------------------- #


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Catch uncaught exceptions, log the trace, increment metric.

    FastAPI already turns raised ``HTTPException`` instances into the
    standard ``{"detail": "..."}`` envelope; this middleware handles
    the long tail: a programming error, a third-party library blowing
    up, a database connection drop mid-request. The handler logs the
    full stack trace at ``ERROR`` level so the operator can find it,
    and returns the same envelope so the client gets a predictable
    shape regardless of where the error originated.
    """

    def __init__(self, app, *, access_logger: logging.Logger | None = None) -> None:
        super().__init__(app)
        self._logger = access_logger or logging.getLogger("atlas.errors")

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:  # noqa: BLE001 — top-level catch is the point
            endpoint = AccessLogMiddleware._endpoint_label(request)
            EXCEPTION_COUNT.labels(
                method=request.method,
                endpoint=endpoint,
                exception_type=type(exc).__name__,
            ).inc()
            self._logger.error(
                "uncaught exception in %s %s",
                request.method, endpoint,
                exc_info=True,
                extra={
                    "request_id": getattr(
                        request.state, REQUEST_ID_ATTR, None
                    ),
                    "method": request.method,
                    "path": endpoint,
                    "exception_type": type(exc).__name__,
                },
            )
            request_id = getattr(request.state, REQUEST_ID_ATTR, "") or uuid.uuid4().hex
            return JSONResponse(
                status_code=500,
                content={
                    "error_code": "INTERNAL_SERVER_ERROR",
                    "safe_message": "An unexpected error occurred. Please try again.",
                    "detail": "Internal server error",
                    "request_id": request_id,
                    "retryable": True,
                    "service_name": "fastapi",
                    "hint": "If this persists, check the backend logs.",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                headers={
                    REQUEST_ID_HEADER: request_id,
                },
            )


# --------------------------------------------------------------------------- #
# Public installer
# --------------------------------------------------------------------------- #


def install_monitoring(app: FastAPI) -> None:
    """Attach every monitoring middleware to the FastAPI app.

    The order is significant: request-id outermost (so the access
    log and the error handler can both read it), error handler
    innermost (so it is the last line of defence before a response
    is materialised).
    """
    # ``add_middleware`` appends; the most-recently-added middleware
    # becomes the OUTERMOST. The desired order from outside-in is:
    # request-id -> access-log -> error-handler -> app. So we add
    # them in reverse: error-handler first, access-log second,
    # request-id last (so request-id ends up outermost).
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)


__all__ = [
    "AccessLogMiddleware",
    "ErrorHandlerMiddleware",
    "REQUEST_ID_ATTR",
    "REQUEST_ID_HEADER",
    "RequestIdMiddleware",
    "install_monitoring",
]
