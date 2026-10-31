"""High-level service coordinating Sales Ingestion and Intelligence (Phase 3 & Phase 5 Resilience)."""

from __future__ import annotations

from typing import Any, Optional
import pandas as pd
from sqlalchemy.orm import Session

from app.repositories.sales_repository import SalesRepository
from app.schemas.sales import (
    ColumnMapping,
    CustomerInsightsResponse,
    DataQualitySummary,
    FilePreviewResponse,
    ProductInsightsResponse,
    SalesSummaryResponse,
    SalesTimeSeriesResponse,
    SalesUploadListItem,
    SalesUploadResponse,
)
from app.services.sales.column_detector import detect_columns
from app.services.sales.parser import (
    generate_file_preview,
    read_sales_dataframe,
    validate_file_metadata,
)
from app.services.sales.quality_engine import validate_and_process_sales_data
from app.services.resilience.idempotency_service import IdempotencyService


class SalesService:
    """Service facade for Sales Ingestion and Descriptive Intelligence."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SalesRepository(db)

    def preview_upload(
        self, filename: str, file_bytes: bytes
    ) -> FilePreviewResponse:
        """Parse file and return preview of headers, candidate mappings, and sample rows."""
        df, preview_meta = generate_file_preview(filename, file_bytes)
        headers = preview_meta["detected_headers"]
        suggested_mapping, confidence_scores = detect_columns(headers)

        return FilePreviewResponse(
            filename=preview_meta["filename"],
            file_format=preview_meta["file_format"],
            file_size_bytes=preview_meta["file_size_bytes"],
            total_rows_estimate=preview_meta["total_rows_estimate"],
            detected_headers=headers,
            suggested_mapping=suggested_mapping,
            sample_rows=preview_meta["sample_rows"],
            confidence_scores=confidence_scores,
        )

    def confirm_and_ingest(
        self,
        business_id: int,
        filename: str,
        file_bytes: bytes,
        mapping: ColumnMapping,
        idempotency_key: Optional[str] = None,
    ) -> SalesUploadResponse:
        """Execute full validation on confirmed mapping, persist transactions, audit quality, with idempotency protection."""
        idempotency_svc = IdempotencyService(self.db)
        if idempotency_key:
            req_hash = idempotency_svc.compute_request_hash(file_bytes, mapping.model_dump())
            is_replay, cached_payload = idempotency_svc.acquire_lock(
                business_id=business_id,
                idempotency_key=idempotency_key,
                operation_type="sales_upload",
                request_hash=req_hash,
            )
            if is_replay and cached_payload:
                return SalesUploadResponse(**cached_payload)

        try:
            file_format = validate_file_metadata(filename, file_bytes)
            df = read_sales_dataframe(file_bytes, file_format)

            # Validate required columns exist in DataFrame
            required_cols = [
                mapping.transaction_date,
                mapping.product_name,
                mapping.quantity,
                mapping.unit_price,
            ]
            missing_in_df = [c for c in required_cols if c not in df.columns]
            if missing_in_df:
                raise ValueError(
                    f"Required column(s) {missing_in_df} not found in uploaded file headers {list(df.columns)}."
                )

            # Fetch existing fingerprints to prevent duplicate inflation across uploads
            existing_fps = self.repo.get_transaction_fingerprints(business_id)

            # Execute row-by-row quality validation & revenue calculations
            valid_rows, quality_summary = validate_and_process_sales_data(
                df, mapping, existing_fingerprints=existing_fps
            )

            # Determine granular status: never claim 100% processed if rows were invalid/skipped
            if len(valid_rows) == 0:
                upload_status = "failed"
            elif quality_summary.invalid_rows > 0:
                upload_status = "partial_success"
            else:
                upload_status = "processed"

            # Record upload event
            upload = self.repo.create_upload(
                business_id=business_id,
                filename=filename,
                file_format=file_format,
                file_size_bytes=len(file_bytes),
                row_count=len(df),
                valid_row_count=len(valid_rows),
                invalid_row_count=quality_summary.invalid_rows,
                status=upload_status,
                column_mapping=mapping.model_dump(),
                quality_summary=quality_summary.model_dump(),
            )

            # Bulk insert valid transactions
            if valid_rows:
                self.repo.bulk_insert_transactions(
                    upload_id=upload.id,
                    business_id=business_id,
                    rows=valid_rows,
                )

            response = SalesUploadResponse(
                upload_id=upload.id,
                business_id=business_id,
                filename=upload.filename,
                file_format=upload.file_format,
                status=upload.status,
                row_count=upload.row_count,
                valid_row_count=upload.valid_row_count,
                invalid_row_count=upload.invalid_row_count,
                quality_summary=quality_summary,
            )

            if idempotency_key:
                idempotency_svc.record_success(business_id, idempotency_key, response)

            return response
        except Exception as exc:
            if idempotency_key:
                idempotency_svc.record_failure(business_id, idempotency_key, str(exc))
            raise

    def get_summary(self, business_id: int) -> SalesSummaryResponse:
        """Fetch sales summary metrics for the business."""
        data = self.repo.get_sales_summary(business_id)
        return SalesSummaryResponse(**data)

    def get_customer_insights(self, business_id: int) -> CustomerInsightsResponse:
        """Fetch customer metrics, retention, and declining account analysis."""
        data = self.repo.get_customer_insights(business_id)
        return CustomerInsightsResponse(**data)

    def get_product_insights(self, business_id: int) -> ProductInsightsResponse:
        """Fetch product intelligence, separating revenue from volume rankings."""
        data = self.repo.get_product_insights(business_id)
        return ProductInsightsResponse(**data)

    def get_time_series(
        self, business_id: int, granularity: str = "monthly"
    ) -> SalesTimeSeriesResponse:
        """Fetch historical time-based sales trends."""
        data = self.repo.get_time_series(business_id, granularity)
        return SalesTimeSeriesResponse(**data)

    def list_uploads(self, business_id: int) -> list[SalesUploadListItem]:
        """List historical uploads for audit trail."""
        uploads = self.repo.get_uploads_for_business(business_id)
        return [
            SalesUploadListItem(
                id=u.id,
                filename=u.filename,
                file_format=u.file_format,
                file_size_bytes=u.file_size_bytes,
                row_count=u.row_count,
                valid_row_count=u.valid_row_count,
                invalid_row_count=u.invalid_row_count,
                status=u.status,
                quality_score=(
                    u.quality_summary.get("quality_score", 0.0)
                    if u.quality_summary
                    else 0.0
                ),
                created_at=u.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            )
            for u in uploads
        ]

    def delete_upload(self, upload_id: int, business_id: int) -> bool:
        """Delete an upload event and its associated transactions."""
        return self.repo.delete_upload_for_business(upload_id, business_id)
