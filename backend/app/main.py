"""FastAPI application factory.

Creates and configures the UrsBiz backend application. Keeps startup
side-effects isolated so the app is easy to test.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.config.logging import configure_logging, get_logger
from app.config.settings import get_settings, validate_security_settings
from app.middleware.cors import install_cors
from app.middleware.performance import install_performance
from app.middleware.security import install_security
from app.monitoring.health import router as monitoring_router
from app.monitoring.logging import configure_structured_logging
from app.monitoring.middleware import install_monitoring
from app.utils.database import bootstrap_schema

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler — prints a [PASS]/[FAIL] boot summary."""
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_structured_logging(settings.log_level)
    logger.info("Starting %s v%s (env=%s)", settings.app_name, settings.app_version, settings.app_env)

    # ------------------------------------------------------------------ #
    # Startup validation — prints a readable summary so any developer
    # cloning the repo can immediately see what is and is not configured.
    # ------------------------------------------------------------------ #
    checks_passed = True

    def _check(label: str, ok: bool, detail: str = "") -> None:
        nonlocal checks_passed
        status = "[PASS]" if ok else "[FAIL]"
        msg = f"{status} {label}" + (f" — {detail}" if detail else "")
        if ok:
            print(msg, flush=True)
        else:
            print(msg, flush=True)
            checks_passed = False

    # 1. JWT secret
    _check(
        "JWT Loaded",
        settings.jwt_secret_key not in {"", "change-me", "CHANGE_ME"},
        "JWT_SECRET_KEY is a placeholder — safe for dev, change for prod"
        if settings.jwt_secret_key in {"", "change-me", "CHANGE_ME"}
        else f"algorithm={settings.jwt_algorithm}",
    )

    # 2. CORS configured
    _check("CORS OK", bool(settings.cors_origins_list), f"origins={settings.cors_origins}")

    # 3. Database reachable + schema bootstrap
    bootstrap_failed: Exception | None = None
    try:
        from app.utils.database import EXPECTED_HEAD_REVISION, get_current_revision

        before = get_current_revision()
        created = bootstrap_schema()
        after = get_current_revision()
        _check(
            "Database Connected",
            True,
            f"url=...{str(settings.database_url)[-30:]}",
        )
        _check(
            "Migrations Applied",
            after == EXPECTED_HEAD_REVISION,
            (
                f"revision={after or '<none>'} expected={EXPECTED_HEAD_REVISION} "
                f"({'bootstrap upgraded' if created else 'no upgrade needed'})"
            ),
        )
    except Exception as exc:
        bootstrap_failed = exc
        _check("Database Connected", False, str(exc))
        _check("Migrations Applied", False, f"schema bootstrap failed — {type(exc).__name__}: {exc}")

    # 4. Security warnings
    warnings = validate_security_settings(settings)
    for warning in warnings:
        logger.warning("security: %s", warning)
    _check("Security Config", not any("production" in w for w in warnings), "see warnings above" if warnings else "")

    print(f"[PASS] API Ready — http://{settings.app_host}:{settings.app_port}/docs", flush=True)
    print("", flush=True)

    if not checks_passed:
        print("[WARN] One or more startup checks FAILED. Review the output above.", flush=True)

    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Build and return a configured FastAPI app instance."""
    settings = get_settings()
    # Use the structured-JSON formatter in production; the legacy
    # plain-text formatter is still available for local development
    # by setting APP_ENV=development.
    if settings.app_env.lower() == "production":
        configure_structured_logging(settings.log_level)
    else:
        configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.app_debug,
        lifespan=lifespan,
    )

    install_cors(app)
    # Sprint 8 Part 4 — gzip + cache-control headers. Called before
    # security so the security stack sees the compressed body and the
    # /health Cache-Control stamp is added on every code path (including
    # the 413 / 429 envelopes).
    install_performance(app)
    # Security headers / request-size / rate-limit are the OUTERMOST
    # layer (after monitoring). Order is significant — see
    # ``app.middleware.security.install_security``.
    install_security(app)
    install_monitoring(app)
    app.include_router(api_router, prefix="/api/v1")
    # Monitoring routes are mounted at the root (no /api/v1 prefix)
    # so the standard Kubernetes / Docker / Prometheus probe paths
    # (``/health``, ``/health/live``, ``/health/ready``, ``/metrics``)
    # work without a vendor-specific prefix. The existing
    # ``/api/v1/health`` endpoint is preserved for the dashboard
    # contract.
    app.include_router(monitoring_router)

    # Sprint H6.1 / 2026-08-03 — global exception handler that
    # returns a STRUCTURED JSON 500 envelope (with the exception
    # type + message) instead of FastAPI's default
    # `{"detail": "Internal server error"}`. The frontend can then
    # surface a specific message instead of the generic
    # "Failed to fetch" wrapper that masks server errors.
    import logging as _logging
    _bootstrap_logger = _logging.getLogger("atlas.error")
    @app.exception_handler(Exception)
    async def _structured_500_handler(_request, exc: Exception):
        _bootstrap_logger.exception("Unhandled exception in request")
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "type": type(exc).__name__,
                "message": str(exc) if str(exc) else "An unexpected error occurred. Please try again.",
                "hint": "If this persists, check the backend logs.",
            },
        )

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/api/v1/health",
            "health_full": "/health",
            "health_live": "/health/live",
            "health_ready": "/health/ready",
            "metrics": "/metrics",
        }

    return app


app = create_app()
