"""Health check endpoints."""

from fastapi import APIRouter, Response, status

from app.monitoring.health import health_live, health_ready
from app.schemas.health import HealthResponse
from app.services.continuity_service import (
    ContinuityService,
    ContinuitySimulationRequest,
    SystemContinuityStatus,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    """Liveness probe. Returns {"status": "ok"} when the service is up."""
    return HealthResponse(status="ok")


# H7.1 — the prompt requires ``/api/v1/health/live`` and
# ``/api/v1/health/ready``. The monitoring router only mounted these at the
# root (``/health/live`` / ``/health/ready``), so the ``/api/v1`` variants
# returned 404. Delegate to the SAME probe functions so the readiness
# contract (a dead database must never report ready → 503) is preserved
# identically on both paths rather than duplicated.
@router.get("/health/live", response_model=dict)
def health_live_v1() -> dict:
    """Liveness probe under /api/v1 — the process is responsive."""
    return health_live()


@router.get("/health/ready", response_model=dict)
def health_ready_v1(response: Response) -> dict:
    """Readiness probe under /api/v1 — every downstream is reachable.

    Returns 200 only when database, knowledge, AI and migrations are all OK;
    503 otherwise. Identical semantics to the root ``/health/ready``.
    """
    return health_ready(response)


# --------------------------------------------------------------------------- #
# Phase 6.30 — Business Continuity & Graceful Degradation
# --------------------------------------------------------------------------- #


@router.get(
    "/health/continuity",
    response_model=SystemContinuityStatus,
    summary="Fetch holistic system continuity and graceful degradation status",
)
def get_continuity_status() -> SystemContinuityStatus:
    """Returns the platform-wide continuity posture across database, AI, and knowledge subsystems."""
    return ContinuityService.get_status()


@router.post(
    "/health/continuity/simulate",
    response_model=SystemContinuityStatus,
    summary="Simulate a subsystem outage or disaster drill",
)
def simulate_continuity_drill(req: ContinuitySimulationRequest) -> SystemContinuityStatus:
    """Execute a simulated failure action to verify platform-wide graceful degradation."""
    return ContinuityService.simulate_action(req.action)
