"""Monitoring health endpoints.

Sprint 8 Part 2 — Monitoring & Observability.

The monitoring surface exposes four routes:

  * ``GET /health``         — full diagnostic. Always returns 200 so
                              external uptime monitors can pin to it.
                              Includes the api, database, ai, knowledge,
                              uptime, version, request count, active
                              requests, average latency, and error rate
                              fields. The metrics are derived from the
                              in-process Prometheus registry so the
                              frontend /admin/system page can read them
                              without opening a second endpoint.
  * ``GET /health/live``    — liveness probe. Returns 200 with
                              ``{"status": "alive"}`` whenever the
                              process is responsive. Kubernetes /
                              Docker use this to decide whether to
                              restart the container.
  * ``GET /health/ready``   — readiness probe. Returns 200 only when
                              every downstream (database, knowledge
                              catalog, AI engine) is reachable.
                              Returns 503 otherwise. Used by the
                              load-balancer / orchestrator to decide
                              whether to send traffic.
  * ``GET /metrics``        — Prometheus exposition format.

The probes are deliberately cheap: each readiness check is bounded
to a single SQL ``SELECT 1`` (or an in-process flag if the service
hasn't been touched yet). They never call the full recommendation /
roadmap / AI engine; that would couple observability to business
load.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Mapping

from fastapi import APIRouter, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.config.settings import get_settings
from app.monitoring.metrics import (
    AI_READY,
    APP_UPTIME,
    BUILD_INFO,
    DB_REACHABLE,
    KNOWLEDGE_LOADED,
    REGISTRY,
)
from app.services.ai import AIDecisionService
from app.services.knowledge.repository import JsonKnowledgeRepository
from app.utils.database import (
    EXPECTED_HEAD_REVISION,
    EXPECTED_TABLES_AT_HEAD,
    SessionLocal,
    get_current_revision,
    get_missing_tables,
)


logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Process start time — used to compute uptime without going through the
# request handler every time. Computed lazily so tests can monkey-patch
# app.monitoring.health._PROCESS_START.
# --------------------------------------------------------------------------- #

_PROCESS_START = time.perf_counter()


def _uptime_seconds() -> float:
    return time.perf_counter() - _PROCESS_START


# --------------------------------------------------------------------------- #
# Service probes
# --------------------------------------------------------------------------- #


def _probe_database() -> tuple[bool, str]:
    """Run a single ``SELECT 1`` against the configured engine.

    Uses a fresh session so the probe is independent of any pooled
    state. A 1-second budget keeps a slow database from holding up
    readiness decisions; failures report the error string for the
    operator dashboard.
    """
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        DB_REACHABLE.set(1)
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        DB_REACHABLE.set(0)
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        session.close()


def _probe_knowledge() -> tuple[bool, str]:
    """Verify the knowledge repository has loaded its catalog.

    The repository is a process singleton; ``count()`` returns the
    number of articles the catalog emitted at startup. We re-read
    the count every probe (cheap — it is an in-process attribute) so
    a hot reload that drops the catalog shows up here.
    """
    try:
        repo = JsonKnowledgeRepository()
        n = repo.count()
        if n <= 0:
            KNOWLEDGE_LOADED.set(0)
            return False, "empty"
        KNOWLEDGE_LOADED.set(1)
        return True, f"{n} articles"
    except Exception as exc:  # noqa: BLE001
        KNOWLEDGE_LOADED.set(0)
        return False, f"{type(exc).__name__}: {exc}"


def _probe_ai() -> tuple[bool, str]:
    """Probe the AI decision service and Gemini circuit breaker status (Phase 5).

    Distinguishes operational AI readiness from transient provider outages.
    """
    try:
        from app.services.ai.resilient_client import get_gemini_circuit_breaker
        cb = get_gemini_circuit_breaker()
        if cb.state == "OPEN":
            AI_READY.set(0)
            return False, "circuit_breaker_open: provider temporarily unreachable"

        AIDecisionService  # noqa: B018 — import check
        AI_READY.set(1)
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        AI_READY.set(0)
        return False, f"{type(exc).__name__}: {exc}"


# --------------------------------------------------------------------------- #
# In-process metrics aggregation (used by /health, never by /metrics).
#
# /metrics is the Prometheus exposition output (unaggregated raw
# counters + histograms). The frontend /admin/system page wants a
# small summary view, so we walk the same registry here and sum it
# into a few flat numbers. Doing this in-process keeps the page
# free of a second network round-trip and keeps the surface
# deterministic (no Prometheus required).
# --------------------------------------------------------------------------- #


def _aggregate_prometheus_metrics() -> dict[str, Any]:
    """Return a flat summary of the request metrics for /health.

    Output shape:

        {
          "request_count":     int,   # total served since process start
          "active_requests":   int,   # in-flight right now
          "avg_latency_ms":    float, # process-wide average
          "error_rate":        float, # 5xx share, 0.0 - 1.0
        }

    Everything is read from the in-process REGISTRY so the readout
    is deterministic to the work this worker has actually seen.
    """
    request_count = 0.0
    active_total = 0.0
    total_duration_seconds = 0.0
    total_duration_count = 0.0
    error_count = 0.0

    for metric in REGISTRY.collect():
        if metric.name != "atlas_http_requests_total":
            continue
        for sample in metric.samples:
            if sample.name.endswith("_count"):
                request_count += float(sample.value)
                status_value = sample.labels.get("status", "")
                if status_value.startswith("5") or status_value == "500":
                    error_count += float(sample.value)

    for metric in REGISTRY.collect():
        if metric.name != "atlas_http_requests_active":
            continue
        for sample in metric.samples:
            if sample.name == "atlas_http_requests_active":
                active_total += float(sample.value)

    for metric in REGISTRY.collect():
        if metric.name != "atlas_http_request_duration_seconds":
            continue
        for sample in metric.samples:
            if sample.name.endswith("_sum"):
                total_duration_seconds += float(sample.value)
            elif sample.name.endswith("_count"):
                total_duration_count += float(sample.value)

    avg_latency_ms = (
        (total_duration_seconds / total_duration_count) * 1000.0
        if total_duration_count > 0
        else 0.0
    )
    error_rate = error_count / request_count if request_count > 0 else 0.0

    return {
        "request_count": int(request_count),
        "active_requests": int(round(active_total)),
        "avg_latency_ms": round(avg_latency_ms, 3),
        "error_rate": round(error_rate, 6),
    }


# --------------------------------------------------------------------------- #
# Response models (loose dicts so the schema mirrors the existing
# /api/v1/health response without coupling to any Pydantic class).
# --------------------------------------------------------------------------- #


def _probe_migrations() -> tuple[bool, str, str, list[str]]:
    """Return (ok, status, current_revision, missing_tables).

    ok=True when the ``alembic_version`` table is present AND the
    recorded revision matches ``EXPECTED_HEAD_REVISION`` AND every
    expected table exists. A None current revision (no
    alembic_version table) is reported as ``pending`` — the
    lifespan handler will then call ``bootstrap_schema()`` to bring
    the database forward.
    """
    try:
        current = get_current_revision()
        missing = get_missing_tables()
    except Exception as exc:  # noqa: BLE001
        return False, f"error: {type(exc).__name__}: {exc}", "", list(EXPECTED_TABLES_AT_HEAD)

    if current is None:
        return False, "pending", "", missing
    if current == EXPECTED_HEAD_REVISION and not missing:
        return True, "up_to_date", current, missing
    detail = f"current={current} expected={EXPECTED_HEAD_REVISION}"
    if missing:
        detail += f" missing_tables={missing}"
    return False, f"out_of_date ({detail})", current, missing


def _build_full_health() -> dict[str, Any]:
    settings = get_settings()
    db_ok, db_detail = _probe_database()
    kn_ok, kn_detail = _probe_knowledge()
    ai_ok, ai_detail = _probe_ai()
    mig_ok, mig_status, mig_revision, mig_missing = _probe_migrations()

    APP_UPTIME.set(_uptime_seconds())
    BUILD_INFO.labels(version=settings.app_version, env=settings.app_env).set(1)

    metrics_summary = _aggregate_prometheus_metrics()

    status_str = "ok" if (db_ok and mig_ok and ai_ok) else ("degraded" if (db_ok and mig_ok) else "down")

    return {
        "status": status_str,
        "api": {"ok": True, "detail": "alive"},
        "database": {"ok": db_ok, "detail": db_detail},
        "ai": {"ok": ai_ok, "detail": ai_detail},
        "knowledge": {"ok": kn_ok, "detail": kn_detail},
        "migrations": {
            "ok": mig_ok,
            "status": mig_status,
            "current_revision": mig_revision or None,
            "expected_head": EXPECTED_HEAD_REVISION,
            "missing_tables": mig_missing,
        },
        "uptime": round(_uptime_seconds(), 3),
        "version": settings.app_version,
        "env": settings.app_env,
        "request_count": metrics_summary["request_count"],
        "active_requests": metrics_summary["active_requests"],
        "avg_latency_ms": metrics_summary["avg_latency_ms"],
        "error_rate": metrics_summary["error_rate"],
        "timestamp": datetime.now(tz=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    }


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #

router = APIRouter(tags=["monitoring"])


@router.get("/health")
def health_full() -> Mapping[str, Any]:
    """Aggregate health. Always returns 200 — the field-level
    ``ok`` flags carry the actual status so a dashboard can render
    the breakdown without having to parse a 5xx body."""
    return _build_full_health()


@router.get("/health/live")
def health_live() -> dict[str, str]:
    """Liveness probe — the process is responsive."""
    return {"status": "alive"}


@router.get("/health/ready")
def health_ready(response: Response) -> dict[str, Any]:
    """Readiness probe — every downstream is reachable."""
    db_ok, db_detail = _probe_database()
    kn_ok, kn_detail = _probe_knowledge()
    ai_ok, ai_detail = _probe_ai()
    mig_ok, mig_status, mig_revision, mig_missing = _probe_migrations()

    # Phase 5 Resilience: Core readiness requires DB, schema, and knowledge.
    # A Gemini outage makes AI degraded but does NOT take down the core application.
    core_ready = db_ok and kn_ok and mig_ok
    response.status_code = (
        status.HTTP_200_OK if core_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return {
        "ready": core_ready,
        "degraded": not ai_ok,
        "database": db_ok,
        "knowledge": kn_ok,
        "ai": ai_ok,
        "migrations": mig_ok,
        "details": {
            "database": db_detail,
            "knowledge": kn_detail,
            "ai": ai_detail,
            "migrations": mig_status,
        },
        "current_revision": mig_revision or None,
        "expected_head": EXPECTED_HEAD_REVISION,
        "missing_tables": mig_missing,
    }


@router.get("/metrics")
def metrics_endpoint() -> Response:
    """Prometheus exposition. Returns the registry contents in the
    text format Prometheus expects (``Content-Type: text/plain;
    version=0.0.4``)."""
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )


__all__ = [
    "router",
    "health_full",
    "health_live",
    "health_ready",
    "metrics_endpoint",
]
