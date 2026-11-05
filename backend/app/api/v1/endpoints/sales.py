"""API router for Sales Ingestion and Sales Intelligence (Phase 3 & Phase 6.26 RBAC)."""

from __future__ import annotations

import json
from typing import Optional
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.middleware.auth_deps import get_current_user
from app.models.user import User
from app.schemas.sales import (
    ColumnMapping,
    CustomerInsightsResponse,
    FilePreviewResponse,
    ProductInsightsResponse,
    SalesSummaryResponse,
    SalesTimeSeriesResponse,
    SalesUploadListItem,
    SalesUploadResponse,
)
from app.services.rbac_service import BusinessContext, Permission, RBACService
from app.services.sales.parser import (
    EmptyFileError,
    MalformedFileError,
    OversizedFileError,
    RowLimitExceededError,
    UnsupportedFormatError,
)
from app.services.sales_service import SalesService
from app.utils.database import get_db

router = APIRouter(prefix="/sales", tags=["sales-intelligence"])


def _get_business_context(user: User, db: Session) -> BusinessContext:
    """Resolve active business and user role enforcing tenant isolation and RBAC."""
    return RBACService.resolve_active_business(user=user, db=db)


@router.post(
    "/upload/preview",
    response_model=FilePreviewResponse,
    summary="Preview uploaded sales file and detect column mappings",
)
async def preview_sales_file(
    file: UploadFile = File(..., description="Sales CSV or Excel file (max 10MB)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Inspects file headers and sample rows without modifying the database."""
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.DATA_WRITE)

    try:
        content = await file.read()
        svc = SalesService(db)
        return svc.preview_upload(file.filename or "unknown", content)
    except EmptyFileError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except OversizedFileError as e:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e))
    except UnsupportedFormatError as e:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(e))
    except RowLimitExceededError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except MalformedFileError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Failed to inspect file: {e}")


@router.post(
    "/upload/confirm",
    response_model=SalesUploadResponse,
    summary="Confirm column mapping and ingest sales transactions",
)
async def confirm_and_ingest_sales(
    file: UploadFile = File(..., description="Sales CSV or Excel file"),
    mapping: str = Form(..., description="JSON string of ColumnMapping"),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Validates rows against mapping, audits data quality, and commits sales records with idempotency."""
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.DATA_WRITE)

    try:
        mapping_dict = json.loads(mapping)
        col_mapping = ColumnMapping(**mapping_dict)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid column mapping payload: {e}",
        )

    try:
        content = await file.read()
        svc = SalesService(db)
        return svc.confirm_and_ingest(
            business_id=ctx.business.id,
            filename=file.filename or "uploaded_sales",
            file_bytes=content,
            mapping=col_mapping,
            idempotency_key=idempotency_key,
        )
    except EmptyFileError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except OversizedFileError as e:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e))
    except UnsupportedFormatError as e:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(e))
    except RowLimitExceededError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except (MalformedFileError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ingestion failed: {e}")


@router.get(
    "/summary",
    response_model=SalesSummaryResponse,
    summary="Get overall sales transaction summary for the active business",
)
def get_sales_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns high-level transaction metrics and date range."""
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.DATA_VIEW)
    svc = SalesService(db)
    return svc.get_summary(ctx.business.id)


@router.get(
    "/customer-insights",
    response_model=CustomerInsightsResponse,
    summary="Get customer purchase patterns, repeat rates, and declining accounts",
)
def get_customer_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Calculates customer metrics and flags accounts with declining activity."""
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.DATA_VIEW)
    svc = SalesService(db)
    return svc.get_customer_insights(ctx.business.id)


@router.get(
    "/product-insights",
    response_model=ProductInsightsResponse,
    summary="Get product intelligence with separate revenue and volume rankings",
)
def get_product_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Calculates product sales volumes, revenue rankings, and velocity trends."""
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.DATA_VIEW)
    svc = SalesService(db)
    return svc.get_product_insights(ctx.business.id)


@router.get(
    "/time-series",
    response_model=SalesTimeSeriesResponse,
    summary="Get historical sales aggregated by monthly, weekly, or daily periods",
)
def get_sales_time_series(
    granularity: str = Query("monthly", pattern="^(monthly|weekly|daily)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregates sales over time without inventing missing dates or synthetic interpolation."""
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.DATA_VIEW)
    svc = SalesService(db)
    return svc.get_time_series(ctx.business.id, granularity)


@router.get(
    "/uploads",
    response_model=list[SalesUploadListItem],
    summary="List all historical sales uploads and quality audits for the active business",
)
def list_sales_uploads(
    limit: int = Query(50, ge=1, le=200, description="Maximum number of upload records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns historical upload log and data quality scores with pagination."""
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.DATA_VIEW)
    svc = SalesService(db)
    uploads = svc.list_uploads(ctx.business.id)
    return uploads[offset : offset + limit]


@router.delete(
    "/uploads/{upload_id}",
    summary="Delete a sales upload and all associated transaction records",
)
def delete_sales_upload(
    upload_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enforces active business ownership and cascades deletion."""
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.DATA_DELETE)
    svc = SalesService(db)
    deleted = svc.delete_upload(upload_id, ctx.business.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found or does not belong to active business.",
        )
    return {"status": "deleted", "upload_id": upload_id}
