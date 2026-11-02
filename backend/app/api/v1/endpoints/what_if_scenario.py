"""What-If Scenario Simulator API endpoints (Phase 6.19 Extension).

Routes:
  POST   /api/v1/scenarios/simulate  - Run in-memory multi-case simulation without persisting
  POST   /api/v1/scenarios           - Save a simulated scenario
  GET    /api/v1/scenarios           - List saved scenarios for active business
  GET    /api/v1/scenarios/{id}      - Retrieve a single saved scenario
  PATCH  /api/v1/scenarios/{id}      - Update scenario metadata or parameters
  DELETE /api/v1/scenarios/{id}      - Delete a saved scenario
  POST   /api/v1/scenarios/compare   - Side-by-side comparison of 2-3 saved scenarios
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.middleware.auth_deps import get_current_user
from app.models.user import User
from app.schemas.what_if_scenario import (
    ScenarioCompareRequest,
    ScenarioCompareResponse,
    ScenarioListResponse,
    ScenarioOut,
    ScenarioSaveRequest,
    ScenarioSimulateRequest,
    ScenarioUpdateRequest,
    SimulationResult,
)
from app.services.what_if_scenario_service import WhatIfScenarioService
from app.utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scenarios", tags=["what-if-scenarios"])


def _resolve_business_id(current_user: User) -> int:
    """Resolves active business ID with explicit 404 when user has no business."""
    biz_id = current_user.active_business_id
    if not biz_id and getattr(current_user, "businesses", None):
        biz_id = current_user.businesses[0].id
    if not biz_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active business profile found. Please create a business profile first.",
        )
    return biz_id


@router.post(
    "/simulate",
    response_model=SimulationResult,
    summary="Run deterministic multi-case scenario simulation without persisting",
)
def simulate_scenario(
    request: ScenarioSimulateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SimulationResult:
    business_id = _resolve_business_id(current_user)
    service = WhatIfScenarioService(db)
    try:
        return service.simulate(
            business_id=business_id,
            owner_id=current_user.id,
            title=request.title,
            params=request.parameters,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "",
    response_model=ScenarioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Save a simulated scenario to the active business",
)
def save_scenario(
    request: ScenarioSaveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScenarioOut:
    business_id = _resolve_business_id(current_user)
    service = WhatIfScenarioService(db)
    try:
        scenario = service.save_scenario(
            business_id=business_id,
            owner_id=current_user.id,
            request=request,
        )
        return ScenarioOut.model_validate(scenario)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=ScenarioListResponse,
    summary="List all saved scenarios for the active business",
)
def list_scenarios(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScenarioListResponse:
    business_id = _resolve_business_id(current_user)
    service = WhatIfScenarioService(db)
    items = service.list_scenarios(business_id=business_id, owner_id=current_user.id)
    return ScenarioListResponse(
        items=[ScenarioOut.model_validate(item) for item in items],
        total=len(items),
    )


@router.get(
    "/{scenario_id}",
    response_model=ScenarioOut,
    summary="Retrieve a specific saved scenario",
)
def get_scenario(
    scenario_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScenarioOut:
    business_id = _resolve_business_id(current_user)
    service = WhatIfScenarioService(db)
    scenario = service.get_scenario(
        business_id=business_id,
        owner_id=current_user.id,
        scenario_id=scenario_id,
    )
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario #{scenario_id} not found or access denied.",
        )
    return ScenarioOut.model_validate(scenario)


@router.patch(
    "/{scenario_id}",
    response_model=ScenarioOut,
    summary="Update scenario parameters or metadata and re-run projection",
)
def update_scenario(
    scenario_id: int,
    request: ScenarioUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScenarioOut:
    business_id = _resolve_business_id(current_user)
    service = WhatIfScenarioService(db)
    scenario = service.update_scenario(
        business_id=business_id,
        owner_id=current_user.id,
        scenario_id=scenario_id,
        request=request,
    )
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario #{scenario_id} not found or access denied.",
        )
    return ScenarioOut.model_validate(scenario)


@router.delete(
    "/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a saved scenario",
)
def delete_scenario(
    scenario_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    business_id = _resolve_business_id(current_user)
    service = WhatIfScenarioService(db)
    deleted = service.delete_scenario(
        business_id=business_id,
        owner_id=current_user.id,
        scenario_id=scenario_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario #{scenario_id} not found or access denied.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/compare",
    response_model=ScenarioCompareResponse,
    summary="Compare 2 or 3 saved scenarios side-by-side",
)
def compare_scenarios(
    request: ScenarioCompareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScenarioCompareResponse:
    business_id = _resolve_business_id(current_user)
    service = WhatIfScenarioService(db)
    try:
        return service.compare_scenarios(
            business_id=business_id,
            owner_id=current_user.id,
            scenario_ids=request.scenario_ids,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
