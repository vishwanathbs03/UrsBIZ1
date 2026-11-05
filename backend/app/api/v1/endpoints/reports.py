"""Reports & Evidence Export Centre API Endpoints — Phase 6.25 & Phase 6.26 RBAC.

Provides evidence-backed, reproducible, tenant-isolated report catalogue,
live preview, multi-format generation (PDF, CSV, XLSX), secure downloads,
and historical audit accountability.

Enforces role-based permissions:
  - Viewers can view history and download generated reports, but cannot generate or delete.
  - Analysts and Managers can preview, generate, and download reports.
  - Only Administrators and Owners can delete / archive reports.
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
from app.services.rbac_service import BusinessContext, Permission, RBACService
from app.services.report_export_service import ReportExportService
from app.services.report_service import ReportService
from app.services.report_storage_service import ReportNotFoundError, StorageSecurityError
from app.utils.database import get_db

router = APIRouter(prefix="/reports", tags=["reports-export-centre"])


def _get_business_context(user: User, db: Session) -> BusinessContext:
    """Resolve active business and user role enforcing tenant isolation and RBAC."""
    return RBACService.resolve_active_business(user=user, db=db)


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
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.DATA_VIEW)
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
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.DATA_VIEW)
    service = ReportExportService(db)
    try:
        return service.preview_report(ctx.business, req)
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
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.REPORTS_GENERATE)
    service = ReportExportService(db)
    client_ip = request.client.host if request.client else None
    try:
        report = service.generate_report(ctx.business, current_user, req, client_ip=client_ip)
        return service.get_report_detail(ctx.business.id, report.report_id)
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
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.DATA_VIEW)
    service = ReportExportService(db)
    return service.list_history(ctx.business.id, page=page, page_size=page_size, report_type=report_type)


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
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.DATA_VIEW)
    service = ReportService(BusinessRepository(db))
    report = service.generate_unified_report(ctx.business)
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
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.REPORTS_DOWNLOAD)
    service = PdfReportService(BusinessRepository(db))
    pdf_bytes = service.generate_pdf_report(ctx.business, report_type=report_type)
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
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.REPORTS_DOWNLOAD)
    service = CsvExportService(BusinessRepository(db))
    csv_str = service.generate_csv_export(ctx.business)
    filename = "Business_Dashboard_Export.csv"
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Parameterized Single Report Endpoints (Must be registered after static paths) ---

@router.get(
    "/{report_id}",
    response_model=ReportDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve report metadata by ID",
)
def get_report_detail(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportDetailResponse:
    """Get metadata for a single report verifying tenant isolation."""
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.DATA_VIEW)
    service = ReportExportService(db)
    try:
        return service.get_report_detail(ctx.business.id, report_id)
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
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.REPORTS_DOWNLOAD)
    service = ReportExportService(db)
    client_ip = request.client.host if request.client else None
    try:
        content_bytes, mime_type, filename = service.download_report(
            ctx.business.id, current_user, report_id, client_ip=client_ip
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
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.DATA_DELETE)
    service = ReportExportService(db)
    try:
        report = service.archive_report(ctx.business.id, current_user, report_id, reason=reason)
        return service.get_report_detail(ctx.business.id, report.report_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
