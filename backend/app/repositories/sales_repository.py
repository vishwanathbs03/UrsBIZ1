"""Repository for Sales Ingestion and Transaction Aggregations (Phase 3)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.sales import SalesTransaction, SalesUpload


class SalesRepository:
    """Encapsulates data access and deterministic aggregations for sales transactions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # =========================================================================
    # Upload Lifecycle
    # =========================================================================

    def create_upload(
        self,
        business_id: int,
        filename: str,
        file_format: str,
        file_size_bytes: int,
        row_count: int,
        valid_row_count: int,
        invalid_row_count: int,
        status: str,
        column_mapping: dict[str, Any] | None,
        quality_summary: dict[str, Any] | None,
        error_message: str | None = None,
    ) -> SalesUpload:
        """Create and persist a SalesUpload record."""
        upload = SalesUpload(
            business_id=business_id,
            filename=filename,
            file_format=file_format,
            file_size_bytes=file_size_bytes,
            row_count=row_count,
            valid_row_count=valid_row_count,
            invalid_row_count=invalid_row_count,
            status=status,
            column_mapping=column_mapping,
            quality_summary=quality_summary,
            error_message=error_message,
        )
        self.db.add(upload)
        self.db.commit()
        self.db.refresh(upload)
        return upload

    def bulk_insert_transactions(
        self, upload_id: int, business_id: int, rows: list[dict[str, Any]]
    ) -> int:
        """Insert normalized transactions in bulk for an upload."""
        if not rows:
            return 0

        transactions = [
            SalesTransaction(
                upload_id=upload_id,
                business_id=business_id,
                transaction_date=r["transaction_date"],
                invoice_id=r.get("invoice_id"),
                customer_id=r.get("customer_id"),
                customer_name=r.get("customer_name"),
                product_id=r.get("product_id"),
                product_name=r["product_name"],
                quantity=float(r["quantity"]),
                unit_price=float(r["unit_price"]),
                total_amount=float(r["total_amount"]),
                is_duplicate=bool(r.get("is_duplicate", False)),
            )
            for r in rows
        ]
        self.db.add_all(transactions)
        self.db.commit()
        return len(transactions)

    def get_uploads_for_business(self, business_id: int) -> list[SalesUpload]:
        """Fetch all upload records for a business in reverse chronological order."""
        stmt = (
            select(SalesUpload)
            .where(SalesUpload.business_id == business_id)
            .order_by(desc(SalesUpload.created_at))
        )
        return list(self.db.scalars(stmt).all())

    def get_upload_by_id_for_business(
        self, upload_id: int, business_id: int
    ) -> Optional[SalesUpload]:
        """Fetch a specific upload for a business enforcing tenant isolation."""
        stmt = select(SalesUpload).where(
            SalesUpload.id == upload_id,
            SalesUpload.business_id == business_id,
        )
        return self.db.scalars(stmt).first()

    def delete_upload_for_business(self, upload_id: int, business_id: int) -> bool:
        """Delete an upload and cascade-delete its transactions."""
        upload = self.get_upload_by_id_for_business(upload_id, business_id)
        if not upload:
            return False
        self.db.delete(upload)
        self.db.commit()
        return True

    def get_transaction_fingerprints(self, business_id: int) -> set[tuple]:
        """Fetch existing transaction fingerprints to prevent duplicate inflation across uploads."""
        txns = (
            self.db.query(
                SalesTransaction.transaction_date,
                SalesTransaction.invoice_id,
                SalesTransaction.product_name,
                SalesTransaction.customer_name,
                SalesTransaction.customer_id,
                SalesTransaction.quantity,
                SalesTransaction.total_amount,
            )
            .filter(SalesTransaction.business_id == business_id)
            .all()
        )
        fps: set[tuple] = set()
        for t in txns:
            p_name = (t.product_name or "").strip().lower()
            q_val = round(float(t.quantity), 4)
            tot_val = round(float(t.total_amount), 2)
            if t.invoice_id:
                fps.add(("inv", t.invoice_id.strip().lower(), p_name, q_val, tot_val))
            else:
                date_str = t.transaction_date.strftime("%Y-%m-%d")
                c_name = (t.customer_name or t.customer_id or "").strip().lower()
                fps.add(("date", date_str, c_name, p_name, q_val, tot_val))
        return fps

    # =========================================================================
    # Aggregations & Analytics
    # =========================================================================

    def get_sales_summary(
        self, business_id: int, include_duplicates: bool = False
    ) -> dict[str, Any]:
        """Compute high-level summary metrics from historical sales transactions."""
        query = self.db.query(SalesTransaction).filter(
            SalesTransaction.business_id == business_id
        )
        if not include_duplicates:
            query = query.filter(SalesTransaction.is_duplicate.is_(False))
        txns = query.all()

        duplicate_count = (
            self.db.query(func.count(SalesTransaction.id))
            .filter(
                SalesTransaction.business_id == business_id,
                SalesTransaction.is_duplicate.is_(True),
            )
            .scalar()
            or 0
        )

        if not txns:
            return {
                "has_sales_data": False,
                "total_transactions": 0,
                "total_revenue": 0.0,
                "total_quantity": 0.0,
                "unique_customers": 0,
                "unique_products": 0,
                "first_transaction_date": None,
                "latest_transaction_date": None,
                "date_range_days": 0,
                "latest_upload_id": None,
                "latest_upload_filename": None,
                "duplicate_transactions_excluded": duplicate_count,
            }

        total_rev = sum(t.total_amount for t in txns)
        total_qty = sum(t.quantity for t in txns)
        cust_set = {
            t.customer_name or t.customer_id
            for t in txns
            if (t.customer_name or t.customer_id)
        }
        prod_set = {t.product_name for t in txns}
        dates = [t.transaction_date for t in txns]
        min_date = min(dates)
        max_date = max(dates)
        date_span = (max_date - min_date).days

        latest_upload = (
            self.db.query(SalesUpload)
            .filter(SalesUpload.business_id == business_id)
            .order_by(desc(SalesUpload.created_at))
            .first()
        )

        return {
            "has_sales_data": True,
            "total_transactions": len(txns),
            "total_revenue": round(total_rev, 2),
            "total_quantity": round(total_qty, 2),
            "unique_customers": len(cust_set),
            "unique_products": len(prod_set),
            "first_transaction_date": min_date.strftime("%Y-%m-%d"),
            "latest_transaction_date": max_date.strftime("%Y-%m-%d"),
            "date_range_days": date_span,
            "latest_upload_id": latest_upload.id if latest_upload else None,
            "latest_upload_filename": latest_upload.filename if latest_upload else None,
            "duplicate_transactions_excluded": duplicate_count,
        }

    def get_customer_insights(
        self, business_id: int, include_duplicates: bool = False
    ) -> dict[str, Any]:
        """Compute deterministic customer purchase metrics and retention analysis."""
        query = self.db.query(SalesTransaction).filter(
            SalesTransaction.business_id == business_id
        )
        if not include_duplicates:
            query = query.filter(SalesTransaction.is_duplicate.is_(False))
        txns = query.order_by(SalesTransaction.transaction_date.asc()).all()

        if not txns:
            return {
                "total_customers": 0,
                "new_customers": 0,
                "repeat_customers": 0,
                "repeat_rate_pct": 0.0,
                "average_order_value": 0.0,
                "purchase_frequency": 0.0,
                "top_customers_by_revenue": [],
                "declining_customers": [],
                "history_span_days": 0,
                "declining_threshold_days": 60,
                "dataset_reference_date": None,
            }

        dataset_max_date = max(t.transaction_date for t in txns)
        dataset_min_date = min(t.transaction_date for t in txns)
        history_span = (dataset_max_date - dataset_min_date).days

        # Group transactions by normalized customer key
        by_customer: dict[str, list[SalesTransaction]] = defaultdict(list)
        for t in txns:
            key = t.customer_name or t.customer_id or "Anonymous / Walk-in"
            by_customer[key].append(t)

        customer_metrics = []
        new_cust_count = 0
        repeat_cust_count = 0
        declining_customers = []

        for name, items in by_customer.items():
            tot_rev = sum(i.total_amount for i in items)
            order_count = len(items)
            c_min_date = min(i.transaction_date for i in items)
            c_max_date = max(i.transaction_date for i in items)
            aov = round(tot_rev / order_count, 2) if order_count > 0 else 0.0
            is_repeat = order_count >= 2

            if is_repeat:
                repeat_cust_count += 1
            else:
                new_cust_count += 1

            # Inactivity status determination
            # Customer is Declining if no purchase in >= 60 days relative to dataset_max_date
            # provided the overall business history spans >= 90 days.
            days_since_last = (dataset_max_date - c_max_date).days
            if history_span >= 90 and days_since_last >= 60:
                status = "Declining"
            elif order_count == 1 and (dataset_max_date - c_min_date).days <= 30:
                status = "New"
            else:
                status = "Active"

            metric = {
                "customer_name": name,
                "customer_id": items[0].customer_id,
                "total_revenue": round(tot_rev, 2),
                "total_orders": order_count,
                "first_purchase_date": c_min_date.strftime("%Y-%m-%d"),
                "latest_purchase_date": c_max_date.strftime("%Y-%m-%d"),
                "average_order_value": aov,
                "is_repeat": is_repeat,
                "status": status,
            }
            customer_metrics.append(metric)
            if status == "Declining":
                declining_customers.append(metric)

        total_customers = len(customer_metrics)
        repeat_rate = (
            round((repeat_cust_count / total_customers) * 100, 1)
            if total_customers > 0
            else 0.0
        )
        total_revenue = sum(m["total_revenue"] for m in customer_metrics)
        total_orders = sum(m["total_orders"] for m in customer_metrics)
        overall_aov = (
            round(total_revenue / total_orders, 2) if total_orders > 0 else 0.0
        )
        frequency = (
            round(total_orders / total_customers, 2) if total_customers > 0 else 0.0
        )

        # Sort top customers descending by revenue
        top_by_rev = sorted(
            customer_metrics, key=lambda x: x["total_revenue"], reverse=True
        )[:20]
        # Sort declining descending by lost revenue potential
        declining_sorted = sorted(
            declining_customers, key=lambda x: x["total_revenue"], reverse=True
        )[:20]

        return {
            "total_customers": total_customers,
            "new_customers": new_cust_count,
            "repeat_customers": repeat_cust_count,
            "repeat_rate_pct": repeat_rate,
            "average_order_value": overall_aov,
            "purchase_frequency": frequency,
            "top_customers_by_revenue": top_by_rev,
            "declining_customers": declining_sorted,
            "history_span_days": history_span,
            "declining_threshold_days": 60,
            "dataset_reference_date": dataset_max_date.strftime("%Y-%m-%d"),
        }

    def get_product_insights(
        self, business_id: int, include_duplicates: bool = False
    ) -> dict[str, Any]:
        """Compute product intelligence, separating revenue rankings from volume rankings."""
        query = self.db.query(SalesTransaction).filter(
            SalesTransaction.business_id == business_id
        )
        if not include_duplicates:
            query = query.filter(SalesTransaction.is_duplicate.is_(False))
        txns = query.order_by(SalesTransaction.transaction_date.asc()).all()

        if not txns:
            return {
                "total_products": 0,
                "total_quantity_sold": 0.0,
                "top_products_by_revenue": [],
                "fast_moving_products_by_volume": [],
                "increasing_sales_products": [],
                "decreasing_sales_products": [],
                "insufficient_history_products": [],
            }

        total_quantity_all = sum(t.quantity for t in txns)

        # Group by product_name
        by_product: dict[str, list[SalesTransaction]] = defaultdict(list)
        for t in txns:
            by_product[t.product_name].append(t)

        product_items = []
        increasing = []
        decreasing = []
        insufficient = []

        for name, items in by_product.items():
            tot_rev = sum(i.total_amount for i in items)
            tot_qty = sum(i.quantity for i in items)
            order_count = len(items)
            p_min_date = min(i.transaction_date for i in items)
            p_max_date = max(i.transaction_date for i in items)
            avg_price = round(tot_rev / tot_qty, 2) if tot_qty > 0 else 0.0

            # Trend calculation
            # If fewer than 3 transactions, insufficient history
            if order_count < 3:
                trend = "Insufficient History"
                delta_pct = None
                insufficient.append(name)
            else:
                # Compare first half volume to second half volume
                mid = order_count // 2
                h1_qty = sum(i.quantity for i in items[:mid])
                h2_qty = sum(i.quantity for i in items[mid:])
                if h1_qty > 0:
                    delta_pct = round(((h2_qty - h1_qty) / h1_qty) * 100, 1)
                else:
                    delta_pct = 100.0

                if delta_pct >= 10.0:
                    trend = "Increasing"
                elif delta_pct <= -10.0:
                    trend = "Decreasing"
                else:
                    trend = "Stable"

            item = {
                "product_name": name,
                "product_id": items[0].product_id,
                "total_revenue": round(tot_rev, 2),
                "total_quantity_sold": round(tot_qty, 2),
                "average_unit_price": avg_price,
                "total_transactions": order_count,
                "first_sale_date": p_min_date.strftime("%Y-%m-%d"),
                "latest_sale_date": p_max_date.strftime("%Y-%m-%d"),
                "trend": trend,
                "quantity_delta_pct": delta_pct,
            }
            product_items.append(item)
            if trend == "Increasing":
                increasing.append(item)
            elif trend == "Decreasing":
                decreasing.append(item)

        # Revenue rankings (descending)
        top_by_revenue = sorted(
            product_items, key=lambda x: x["total_revenue"], reverse=True
        )[:20]

        # Volume rankings (descending by total_quantity_sold) - STRICTLY SEPARATE
        fast_moving_by_volume = sorted(
            product_items, key=lambda x: x["total_quantity_sold"], reverse=True
        )[:20]

        insufficient_items = [
            p for p in product_items if p["trend"] == "Insufficient History"
        ]

        return {
            "total_products": len(product_items),
            "total_quantity_sold": round(total_quantity_all, 2),
            "top_products_by_revenue": top_by_revenue,
            "fast_moving_products_by_volume": fast_moving_by_volume,
            "increasing_sales_products": sorted(
                increasing, key=lambda x: x["quantity_delta_pct"] or 0, reverse=True
            ),
            "decreasing_sales_products": sorted(
                decreasing, key=lambda x: x["quantity_delta_pct"] or 0
            ),
            "insufficient_history_products": insufficient_items[:20],
        }

    def get_time_series(
        self, business_id: int, granularity: str = "monthly", include_duplicates: bool = False
    ) -> dict[str, Any]:
        """Aggregate sales into time buckets (monthly, weekly, or daily) without artificial zero-interpolation."""
        query = self.db.query(SalesTransaction).filter(
            SalesTransaction.business_id == business_id
        )
        if not include_duplicates:
            query = query.filter(SalesTransaction.is_duplicate.is_(False))
        txns = query.order_by(SalesTransaction.transaction_date.asc()).all()

        if not txns:
            return {
                "granularity": granularity,
                "points": [],
                "total_periods": 0,
                "active_periods": 0,
                "start_date": None,
                "end_date": None,
            }

        start_date = min(t.transaction_date for t in txns).strftime("%Y-%m-%d")
        end_date = max(t.transaction_date for t in txns).strftime("%Y-%m-%d")

        # Period grouping function
        def format_period(dt: datetime) -> str:
            if granularity == "daily":
                return dt.strftime("%Y-%m-%d")
            elif granularity == "weekly":
                # ISO week format YYYY-Www
                return f"{dt.year}-W{dt.isocalendar().week:02d}"
            else:
                # monthly
                return dt.strftime("%Y-%m")

        buckets: dict[str, list[SalesTransaction]] = defaultdict(list)
        for t in txns:
            p = format_period(t.transaction_date)
            buckets[p].append(t)

        sorted_periods = sorted(buckets.keys())
        points = []

        for p in sorted_periods:
            p_txns = buckets[p]
            p_rev = sum(t.total_amount for t in p_txns)
            p_qty = sum(t.quantity for t in p_txns)
            custs = {
                t.customer_name or t.customer_id
                for t in p_txns
                if (t.customer_name or t.customer_id)
            }
            points.append(
                {
                    "period": p,
                    "revenue": round(p_rev, 2),
                    "quantity": round(p_qty, 2),
                    "transaction_count": len(p_txns),
                    "unique_customers": len(custs),
                    "has_data": True,  # Genuine uploaded sales observations
                }
            )

        return {
            "granularity": granularity,
            "points": points,
            "total_periods": len(points),
            "active_periods": len(points),
            "start_date": start_date,
            "end_date": end_date,
        }
