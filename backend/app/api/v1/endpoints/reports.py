"""Reports & Evidence Export Centre API Endpoints — Phase 6.25.

Provides evidence-backed, reproducible, tenant-isolated report catalogue,
live preview, multi-format generation (PDF, CSV, XLSX), secure downloads,
and historical audit accountability.
"""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.middleware.auth_deps import get_current_user
from app.models.business import Business
from app.models.user import User
from app.repositories.business_repository import BusinessNotFound, BusinessRepository
from app.schemas.business_report import (
    ReportCatalogResponse,
    ReportDetailResponse,
    ReportGenerateRequest,
    ReportHistoryResponse,
    ReportPreviewRequest,
    ReportPreviewResponse,
)
from app.schemas.reports import UnifiedReportResponse
from app.services.csv_export_service import CsvExportService
from app.services.pdf_report_service import PdfReportService
from app.services.report_export_service import ReportExportService
from app.services.report_service import ReportService
from app.services.report_storage_service import ReportNotFoundError, StorageSecurityError
from app.utils.database import get_db

router = APIRouter(prefix="/reports", tags=["reports-export-centre"])


def _get_active_business(user: User, db: Session) -> Business:
    """Resolve active business for authenticated user enforcing strict tenant isolation.

    If user.active_business_id is explicitly set:
        Must resolve to an accessible business owned by the user. If not found or
        unauthorized, raises 404 immediately to prevent silent business switching.
    If user.active_business_id is None (unselected):
        Falls back to the user's most recently created business.
    """
    repo = BusinessRepository(db)
    if user.active_business_id is not None:
        direct = repo.get_by_id_for_owner(
            business_id=user.active_business_id, owner_id=user.id
        )
        if direct is not None:
            return direct
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active business profile {user.active_business_id} not found or inaccessible for current user.",
        )

    # Initial onboarding fallback when active_business_id was never set
    rows = repo.list_for_owner(user.id)
    if rows:
        return rows[-1]
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No business profile registered for the current user. Complete onboarding first.",
    )


# --- Phase 6.25 Reports / Evidence Export Centre Endpoints ---

@router.get(
    "/catalog",
    response_model=ReportCatalogResponse,
    status_code=status.HTTP_200_OK,
    summary="List available evidence report catalogue",
)
def get_report_catalog(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportCatalogResponse:
    """Return catalogue of all supported business intelligence reports."""
    # Ensure user has access
    _get_active_business(current_user, db)
    service = ReportExportService(db)
    return service.get_catalog()


@router.post(
    "/preview",
    response_model=ReportPreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Preview evidence report with live calculations and provenance",
)
def preview_report(
    req: ReportPreviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportPreviewResponse:
    """Generate structured live preview without writing file to disk."""
    biz = _get_active_business(current_user, db)
    service = ReportExportService(db)
    try:
        return service.preview_report(biz, req)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post(
    "/generate",
    response_model=ReportDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate and store evidence report artifact (PDF, CSV, XLSX)",
)
def generate_report(
    req: ReportGenerateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportDetailResponse:
    """Generate binary report file, store securely in tenant directory, and record audit."""
    biz = _get_active_business(current_user, db)
    service = ReportExportService(db)
    client_ip = request.client.host if request.client else None
    try:
        report = service.generate_report(biz, current_user, req, client_ip=client_ip)
        return service.get_report_detail(biz.id, report.report_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except StorageSecurityError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc


@router.get(
    "/history",
    response_model=ReportHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="List generated reports history for active business",
)
def list_report_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    report_type: str | None = Query(None, description="Filter by report type"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportHistoryResponse:
    """List historical reports generated for active business."""
    biz = _get_active_business(current_user, db)
    service = ReportExportService(db)
    return service.list_history(biz.id, page=page, page_size=page_size, report_type=report_type)


@router.get(
    "/{report_id}",
    response_model=ReportDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get single report details and metadata",
)
def get_report_detail(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportDetailResponse:
    """Get metadata for a generated report."""
    biz = _get_active_business(current_user, db)
    service = ReportExportService(db)
    try:
        return service.get_report_detail(biz.id, report_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get(
    "/{report_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download generated report file (PDF, CSV, XLSX)",
)
def download_report_file(
    report_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Securely download report file verifying tenant isolation and file integrity."""
    biz = _get_active_business(current_user, db)
    service = ReportExportService(db)
    client_ip = request.client.host if request.client else None
    try:
        content_bytes, mime_type, filename = service.download_report(
            biz.id, current_user, report_id, client_ip=client_ip
        )
        return Response(
            content=content_bytes,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "X-Content-Type-Options": "nosniff",
            },
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ReportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except StorageSecurityError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc


@router.delete(
    "/{report_id}",
    response_model=ReportDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Soft-delete / archive a report",
)
def archive_report(
    report_id: str,
    reason: str | None = Query(None, description="Reason for archiving"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportDetailResponse:
    """Soft-delete report, preventing future downloads while preserving audit trail."""
    biz = _get_active_business(current_user, db)
    service = ReportExportService(db)
    try:
        report = service.archive_report(biz.id, current_user, report_id, reason=reason)
        return service.get_report_detail(biz.id, report.report_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


# --- Preserved Sprint 13 Endpoints (Enriched with active_business_id tenant isolation) ---

@router.get(
    "/unified",
    response_model=UnifiedReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate unified business intelligence report model",
)
def get_unified_report(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UnifiedReportResponse:
    biz = _get_active_business(current_user, db)
    service = ReportService(BusinessRepository(db))
    report = service.generate_unified_report(biz)
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    return UnifiedReportResponse(generated_at=now_iso, report=report)


@router.get(
    "/pdf",
    status_code=status.HTTP_200_OK,
    summary="Download PDF Business Report (Executive / Health)",
)
def download_pdf_report(
    report_type: str = Query("executive", description="Report type: executive or health"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    biz = _get_active_business(current_user, db)
    service = PdfReportService(BusinessRepository(db))
    pdf_bytes = service.generate_pdf_report(biz, report_type=report_type)
    filename = f"Business_{report_type.capitalize()}_Report.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/csv",
    status_code=status.HTTP_200_OK,
    summary="Download CSV Business Data Export (KPIs, Recommendations, DNA, SWOT)",
)
def download_csv_export(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    biz = _get_active_business(current_user, db)
    service = CsvExportService(BusinessRepository(db))
    csv_str = service.generate_csv_export(biz)
    filename = "Business_Dashboard_Export.csv"
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
