"""FastAPI router for Integration Readiness & Connector Framework (Phase 6.27).

Endpoints enforcing strict tenant isolation, RBAC permissions, and secret redaction.
"""

from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.middleware.rbac_deps import require_permission
from app.schemas.integration import (
    ConnectionConfigUpdateReq,
    ConnectionCreateReq,
    ConnectionOut,
    ConnectionTestResultOut,
    ConnectorCatalogueItemOut,
    CredentialRotateReq,
    IntegrationAuditListResponse,
    SyncExecutionListResponse,
    SyncExecutionOut,
    SyncTriggerReq,
)
from app.services.integration_service import IntegrationService
from app.services.rbac_service import BusinessContext, Permission
from app.utils.database import get_db

router = APIRouter(prefix="/integrations", tags=["integrations"])


# =============================================================================
# 1. CONNECTOR CATALOGUE
# =============================================================================

@router.get(
    "/catalogue",
    response_model=list[ConnectorCatalogueItemOut],
    summary="List available connectors in the catalogue",
)
def list_catalogue(
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_VIEW))],
    db: Annotated[Session, Depends(get_db)],
) -> list[ConnectorCatalogueItemOut]:
    service = IntegrationService(db)
    return service.list_catalogue()


# =============================================================================
# 2. CONNECTION MANAGEMENT
# =============================================================================

@router.get(
    "/connections",
    response_model=list[ConnectionOut],
    summary="List configured data source connections for the active business",
)
def list_connections(
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_VIEW))],
    db: Annotated[Session, Depends(get_db)],
) -> list[ConnectionOut]:
    service = IntegrationService(db)
    return service.list_connections(ctx.business.id)


@router.post(
    "/connections",
    response_model=ConnectionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Configure a new external data source connection",
)
def create_connection(
    req: ConnectionCreateReq,
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_WRITE))],
    db: Annotated[Session, Depends(get_db)],
) -> ConnectionOut:
    service = IntegrationService(db)
    return service.create_connection(business=ctx.business, user=ctx.user, req=req)


@router.get(
    "/connections/{connection_id}",
    response_model=ConnectionOut,
    summary="Get details of a specific connection",
)
def get_connection(
    connection_id: int,
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_VIEW))],
    db: Annotated[Session, Depends(get_db)],
) -> ConnectionOut:
    service = IntegrationService(db)
    conn = service.get_connection(ctx.business.id, connection_id)
    return service._to_connection_out(conn)


@router.patch(
    "/connections/{connection_id}/config",
    response_model=ConnectionOut,
    summary="Update non-sensitive configuration for a connection",
)
def update_configuration(
    connection_id: int,
    req: ConnectionConfigUpdateReq,
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_WRITE))],
    db: Annotated[Session, Depends(get_db)],
) -> ConnectionOut:
    service = IntegrationService(db)
    return service.update_configuration(
        business=ctx.business, user=ctx.user, connection_id=connection_id, req=req
    )


@router.put(
    "/connections/{connection_id}/credentials",
    response_model=ConnectionOut,
    summary="Rotate or update encrypted credentials for a connection",
)
def rotate_credentials(
    connection_id: int,
    req: CredentialRotateReq,
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_WRITE))],
    db: Annotated[Session, Depends(get_db)],
) -> ConnectionOut:
    service = IntegrationService(db)
    return service.rotate_credentials(
        business=ctx.business, user=ctx.user, connection_id=connection_id, req=req
    )


@router.post(
    "/connections/{connection_id}/test",
    response_model=ConnectionTestResultOut,
    summary="Test connection reachability and authentication without altering state",
)
def test_connection(
    connection_id: int,
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_WRITE))],
    db: Annotated[Session, Depends(get_db)],
) -> ConnectionTestResultOut:
    service = IntegrationService(db)
    return service.test_connection(
        business=ctx.business, user=ctx.user, connection_id=connection_id
    )


@router.post(
    "/connections/{connection_id}/connect",
    response_model=ConnectionOut,
    summary="Authenticate and activate connection into CONNECTED status",
)
def connect(
    connection_id: int,
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_WRITE))],
    db: Annotated[Session, Depends(get_db)],
) -> ConnectionOut:
    service = IntegrationService(db)
    return service.connect(
        business=ctx.business, user=ctx.user, connection_id=connection_id
    )


@router.post(
    "/connections/{connection_id}/disconnect",
    response_model=ConnectionOut,
    summary="Disconnect an active connection",
)
def disconnect(
    connection_id: int,
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_WRITE))],
    db: Annotated[Session, Depends(get_db)],
) -> ConnectionOut:
    service = IntegrationService(db)
    return service.disconnect(
        business=ctx.business, user=ctx.user, connection_id=connection_id
    )


@router.delete(
    "/connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a connection",
)
def delete_connection(
    connection_id: int,
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_DELETE))],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    service = IntegrationService(db)
    service.delete_connection(
        business=ctx.business, user=ctx.user, connection_id=connection_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =============================================================================
# 3. SYNCHRONIZATION ENGINE
# =============================================================================

@router.post(
    "/connections/{connection_id}/sync",
    response_model=SyncExecutionOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a synchronization run for a connected data source",
)
def trigger_sync(
    connection_id: int,
    req: SyncTriggerReq,
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_WRITE))],
    db: Annotated[Session, Depends(get_db)],
) -> SyncExecutionOut:
    service = IntegrationService(db)
    return service.trigger_sync(
        business=ctx.business,
        user=ctx.user,
        connection_id=connection_id,
        trigger_type=req.trigger_type,
        batch_limit=req.batch_limit,
    )


@router.get(
    "/connections/{connection_id}/syncs",
    response_model=SyncExecutionListResponse,
    summary="Get synchronization history for a specific connection",
)
def get_connection_syncs(
    connection_id: int,
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_VIEW))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> SyncExecutionListResponse:
    service = IntegrationService(db)
    # Validate connection ownership
    service.get_connection(ctx.business.id, connection_id)
    return service.get_sync_executions(
        business_id=ctx.business.id,
        connection_id=connection_id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/syncs",
    response_model=SyncExecutionListResponse,
    summary="Get synchronization history for the active business",
)
def get_all_syncs(
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_VIEW))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> SyncExecutionListResponse:
    service = IntegrationService(db)
    return service.get_sync_executions(
        business_id=ctx.business.id,
        connection_id=None,
        page=page,
        page_size=page_size,
    )


# =============================================================================
# 4. AUDIT LOGS
# =============================================================================

@router.get(
    "/audits",
    response_model=IntegrationAuditListResponse,
    summary="Get immutable audit trail of integration events",
)
def get_audits(
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_VIEW))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> IntegrationAuditListResponse:
    service = IntegrationService(db)
    return service.get_audits(business_id=ctx.business.id, page=page, page_size=page_size)
