"""Business Digital Twin endpoints.

Routes
------

    POST   /business            create a new business for the user; becomes active
    POST   /business/minimal    create with only the 6 required fields (panel)
    GET    /business            fetch the user's *active* business + completeness
    GET    /business/me         alias of GET /business
    GET    /business/list       list every business the user owns (panel)
    PUT    /business            partial update of the active business
    DELETE /business/{id}       delete a specific business (404 if not owned,
                                409 if it is the user's last business)

Authentication
--------------

Every route requires a valid session (JWT cookie or
``Authorization: Bearer ***``). The owner is resolved from the JWT
subject; clients cannot pick an owner_id.

Sprint 23 — a user may own many businesses. The ``active_business_id``
on the User row drives the read path; ``POST /business`` and
``POST /business/minimal`` set the new row as active.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.middleware.auth_deps import get_current_user
from app.models.user import User
from app.repositories.business_repository import (
    BusinessAlreadyExists,
    BusinessNotFound,
    BusinessRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.business import (
    BusinessCreate,
    BusinessListResponse,
    BusinessMinimalCreate,
    BusinessUpdate,
    BusinessWithCompleteness,
    DeleteResponse,
)
from app.services.auth_service import AuthService
from app.services.business_service import BusinessLastError, BusinessService
from app.utils.database import get_db


router = APIRouter(prefix="/business", tags=["business"])


def _service(db: Session = Depends(get_db)) -> BusinessService:
    # Sprint 23 — the business service now also flips the user's
    # active_business_id after creating a new row. Both services
    # share the same Session so the User + Business writes commit
    # atomically.
    return BusinessService(
        repo=BusinessRepository(db),
        auth_service=AuthService(
            user_repo=UserRepository(db),
            business_repo=BusinessRepository(db),
        ),
    )


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #


@router.post(
    "",
    response_model=BusinessWithCompleteness,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new business profile for the authenticated user.",
)
def create_business(
    payload: BusinessCreate,
    current_user: User = Depends(get_current_user),
    service: BusinessService = Depends(_service),
) -> BusinessWithCompleteness:
    """Sprint 23 — a user may own many businesses. The new business
    is created and immediately becomes the active one."""
    try:
        return service.create(current_user, payload)
    except BusinessAlreadyExists as exc:  # pragma: no cover — defensive
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.post(
    "/minimal",
    response_model=BusinessWithCompleteness,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new business with the six minimum required fields.",
)
def create_business_minimal(
    payload: BusinessMinimalCreate,
    current_user: User = Depends(get_current_user),
    service: BusinessService = Depends(_service),
) -> BusinessWithCompleteness:
    """Sprint 23 — the inline 'Add a business' form inside the
    profile panel only collects the six required fields. The full
    8-step wizard on ``/business`` continues to be the source of
    truth for the remaining 7 sections; this endpoint just creates
    the row so the wizard can be opened against a real id."""
    return service.create_minimal(current_user, payload)


@router.get(
    "",
    response_model=BusinessWithCompleteness,
    summary="Fetch the authenticated user's *active* business profile.",
)
def get_business(
    current_user: User = Depends(get_current_user),
    service: BusinessService = Depends(_service),
) -> BusinessWithCompleteness:
    """Sprint 23 — returns the business the user has marked as
    active (``user.active_business_id``), falling back to the
    most-recently-created one if no active id is set. Raises
    404 only if the user owns zero businesses."""
    try:
        return service.get_active_for_user(current_user)
    except BusinessNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get(
    "/list",
    response_model=BusinessListResponse,
    summary="List every business the authenticated user owns.",
)
def list_businesses(
    current_user: User = Depends(get_current_user),
    service: BusinessService = Depends(_service),
) -> BusinessListResponse:
    """Sprint 23 — the profile panel's primary data source. Each
    entry is a lightweight projection (no nested collections);
    the active id is surfaced separately so the panel can render
    the active pill without joining on the client."""
    items = service.list_for_owner(current_user)
    return BusinessListResponse(
        items=items,
        active_business_id=current_user.active_business_id,
        count=len(items),
    )


# Alias for clearer wording — same handler.
@router.get(
    "/me",
    response_model=BusinessWithCompleteness,
    summary="Alias of GET /business",
    include_in_schema=False,
)
def get_business_me(
    current_user: User = Depends(get_current_user),
    service: BusinessService = Depends(_service),
) -> BusinessWithCompleteness:
    return get_business(current_user=current_user, service=service)


@router.put(
    "",
    response_model=BusinessWithCompleteness,
    summary="Update the authenticated user's business profile (partial)",
)
def update_business(
    payload: BusinessUpdate,
    current_user: User = Depends(get_current_user),
    service: BusinessService = Depends(_service),
) -> BusinessWithCompleteness:
    try:
        return service.update(current_user.id, payload)
    except BusinessNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.delete(
    "/{business_id}",
    response_model=DeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a specific business the authenticated user owns.",
)
def delete_business(
    business_id: int,
    current_user: User = Depends(get_current_user),
    service: BusinessService = Depends(_service),
) -> DeleteResponse:
    """Sprint 23 — the panel's 'Delete' affordance targets a
    specific business id rather than the active one. 404 if the
    business is not owned by the user, 409 if it is the user's
    last remaining business.

    ``business_id`` is a plain ``int`` (not ``Path(ge=1)``) because
    the file uses ``from __future__ import annotations`` and Pydantic
    cannot resolve ``Annotated[int, Path(...)]`` forward-refs at
    route registration time on Python 3.14. FastAPI still rejects
    non-positive ids via the path-segment type coercion (it 404s
    when the path does not match ``/{int}``).
    """
    try:
        return service.delete(current_user, business_id)
    except BusinessNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except BusinessLastError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc