"""Health check endpoints."""

from fastapi import APIRouter, Response

from app.monitoring.health import health_live, health_ready
from app.schemas.health import HealthResponse

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
