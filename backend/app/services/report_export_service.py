"""Report Export Engine Service — Phase 6.25.

Orchestrates evidence aggregation, deterministic metric calculations,
data confidence checks, provenance stamping, and multi-format rendering
(PDF, CSV, XLSX) for the Reports and Evidence Export Centre.
"""

from __future__ import annotations

import csv
import io
import os
import re
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.decision_workbench import BusinessDecision
from app.models.business_goal import BusinessGoal
from app.models.business_report import BusinessReport, BusinessReportAudit
from app.models.business_monitoring import BusinessSignalEvent
from app.models.sales import SalesTransaction, SalesUpload
from app.models.user import User
from app.models.what_if_scenario import WhatIfScenario
from app.schemas.business_report import (
    EvidenceNature,
    ReportCatalogItem,
    ReportCatalogResponse,
    ReportCoverageStatus,
    ReportDetailResponse,
    ReportFormat,
    ReportGenerateRequest,
    ReportHistoryItem,
    ReportHistoryResponse,
    ReportPreviewRequest,
    ReportPreviewResponse,
    ReportProvenance,
    ReportStatus,
    ReportTableData,
    ReportType,
)
from app.services.business_goal_service import BusinessGoalService
from app.services.health_score_service import HealthScoreService
from app.services.kpi_service import KpiService
from app.services.report_storage_service import ReportStorageService

# --- PDF Setup with ReportLab ---
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Bundled and system TrueType font candidates with full Kannada and Latin glyph coverage.
# Non-Kannada fonts (such as Arial or DejaVuSans) are intentionally excluded so they cannot
# silently fallback and produce blank/missing Kannada glyphs in generated PDFs.
_BUNDLED_KANNADA_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "NotoSansKannada-Regular.ttf"

_UNICODE_FONT_NAME = "Helvetica"
_KANNADA_FONT_REGISTERED = False

_FONT_CANDIDATES = [
    ("UrsBizKannada", str(_BUNDLED_KANNADA_FONT), None),
    ("UrsBizKannada", "C:/Windows/Fonts/Nirmala.ttc", 0),
    ("UrsBizKannada", "/usr/share/fonts/truetype/noto/NotoSansKannada-Regular.ttf", None),
    ("UrsBizKannada", "/usr/share/fonts/truetype/lohit-kannada/Lohit-Kannada.ttf", None),
    ("UrsBizKannada", "C:/Windows/Fonts/tunga.ttf", None),
]

for _font_name, _fpath, _sub_idx in _FONT_CANDIDATES:
    if os.path.exists(_fpath):
        try:
            if _sub_idx is not None:
                pdfmetrics.registerFont(TTFont(_font_name, _fpath, subfontIndex=_sub_idx))
            else:
                pdfmetrics.registerFont(TTFont(_font_name, _fpath))
            _UNICODE_FONT_NAME = _font_name
            _KANNADA_FONT_REGISTERED = True
            break
        except Exception:
            pass


def check_kannada_glyph_coverage(
    font_name: str | None = None,
    sample_text: str = "ಶ್ರೀ ಬಸವೇಶ್ವರ ಎಂಟರ್‌ಪ್ರೈಸಸ್",
) -> tuple[bool, list[str]]:
    """Verify that the registered font contains character glyphs for the given text.

    Returns:
        tuple[is_fully_covered, missing_characters]
    """
    target_font = font_name or _UNICODE_FONT_NAME
    try:
        font = pdfmetrics.getFont(target_font)
        if not hasattr(font, "face") or not hasattr(font.face, "charToGlyph"):
            return False, [c for c in sample_text if ord(c) > 127]
        missing = [ch for ch in sample_text if ord(ch) not in font.face.charToGlyph]
        return len(missing) == 0, missing
    except Exception:
        return False, [c for c in sample_text if ord(c) > 127]


def _is_numeric_or_currency(val: Any) -> bool:
    """Return True if val represents a legitimate mathematical number, currency, or percentage."""
    if isinstance(val, (int, float)):
        return True
    if not isinstance(val, str):
        return False
    s = val.strip()
    if not s:
        return False
    clean_s = (
        s.replace("₹", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .replace(",", "")
        .replace("%", "")
        .strip()
    )
    try:
        float(clean_s)
        return True
    except ValueError:
        return False


def _sanitize_formula(val: Any) -> Any:
    """Prevent CSV/XLSX formula injection without damaging legitimate negative numbers.

    Rules:
      1. Legitimate numeric, currency, and percentage values (e.g. -5000, -₹7,500.00, -15.2%)
         are preserved intact so mathematical calculations and financial reports remain accurate.
      2. Non-numeric text strings starting with dangerous execution tokens (=, +, -, @, \\t, \\r)
         are prepended with a single quote (') to force spreadsheets to treat them as plain text.
    """
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str) and val:
        s = val.strip()
        if _is_numeric_or_currency(s):
            return val
        if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
            return f"'{s}"
    return val


def _sanitize_pdf_text(text: str) -> str:
    """Ensure safe characters for PDF rendering without crashes."""
    if not text:
        return ""
    # If font is standard Type 1 (Helvetica), convert non-latin1 characters to ascii equivalents
    if _UNICODE_FONT_NAME == "Helvetica":
        clean = []
        for ch in str(text):
            if ord(ch) < 256:
                clean.append(ch)
            else:
                clean.append(f"\\u{ord(ch):04x}")
        return "".join(clean)
    return str(text)


class ReportExportService:
    """Core domain service for Reports and Evidence Export Centre (Phase 6.25)."""

    STANDARD_DISCLAIMER = (
        "UrsBiz deterministic business intelligence calculation. "
        "Generated based on authoritative ingested records and validated MSME operational heuristics. "
        "Evidence and metrics are strictly reproducible and tenant-isolated. "
        "Intended for decision support, banking, and accounting review."
    )

    CATALOG: list[ReportCatalogItem] = [
        ReportCatalogItem(
            report_type=ReportType.EXECUTIVE_SUMMARY.value,
            category="Executive",
            title="Executive Business Performance Summary",
            description="Comprehensive executive brief featuring business health grade, readiness score, core KPIs, and strategic milestones.",
            supported_formats=["PDF", "CSV", "XLSX"],
            required_data_sources=["Digital Twin", "Business Profile"],
            parameters_schema={"observation_days": "Number of days (default 30)"},
        ),
        ReportCatalogItem(
            report_type=ReportType.SALES_REVENUE_PERFORMANCE.value,
            category="Financial & Sales",
            title="Sales & Revenue Performance Report",
            description="Authoritative revenue aggregates, daily/monthly transaction trajectories, average order value (AOV), and growth rates.",
            supported_formats=["PDF", "CSV", "XLSX"],
            required_data_sources=["Sales Ingestion", "Sales Transactions"],
            parameters_schema={"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"},
        ),
        ReportCatalogItem(
            report_type=ReportType.CUSTOMER_PERFORMANCE.value,
            category="Customer & Market",
            title="Customer Concentration & Retention Assessment",
            description="Customer concentration risk (Top 1, Top 3, Top 5 share), repeat customer rate, and customer activity status.",
            supported_formats=["PDF", "CSV", "XLSX"],
            required_data_sources=["Sales Transactions"],
            parameters_schema={"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"},
        ),
        ReportCatalogItem(
            report_type=ReportType.PRODUCT_PERFORMANCE.value,
            category="Operations & Products",
            title="Product Revenue Velocity & Contribution Analysis",
            description="Product-level sales volumes, revenue contribution percentage, velocity ranking, and inventory movement indicators.",
            supported_formats=["PDF", "CSV", "XLSX"],
            required_data_sources=["Sales Transactions", "Product Catalog"],
            parameters_schema={"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"},
        ),
        ReportCatalogItem(
            report_type=ReportType.DECISIONS_SUMMARY.value,
            category="Governance & Decisions",
            title="Business Decision Log & Evaluated Outcome Summary",
            description="Complete audit log of owner decisions, evaluated financial impacts (gross margin, price changes), and implementation status.",
            supported_formats=["PDF", "CSV", "XLSX"],
            required_data_sources=["Business Decisions", "Decision Workbench"],
            parameters_schema={"status": "Filter by decision status"},
        ),
        ReportCatalogItem(
            report_type=ReportType.ALERTS_SUMMARY.value,
            category="Governance & Risk",
            title="Business Signal Alerts & Risk Event Audit",
            description="Historical log of operational signals, 2-sigma revenue drop anomalies, customer churn alerts, and statistical warnings.",
            supported_formats=["PDF", "CSV", "XLSX"],
            required_data_sources=["Business Signal Events", "Event Centre"],
            parameters_schema={"severity": "CRITICAL, WARNING, INFO"},
        ),
        ReportCatalogItem(
            report_type=ReportType.GOALS_PROGRESS.value,
            category="Strategy & Goals",
            title="Business Objectives & Progress Tracker Report",
            description="Audit-ready snapshot of active and achieved business goals, deterministic measured progress, baselines, and milestone deadlines.",
            supported_formats=["PDF", "CSV", "XLSX"],
            required_data_sources=["Business Goals", "Progress Tracker"],
            parameters_schema={"status": "ACTIVE, COMPLETED, PAUSED"},
        ),
        ReportCatalogItem(
            report_type=ReportType.DATA_QUALITY_AUDIT.value,
            category="Data Governance",
            title="Data Completeness, Anomaly & Freshness Audit",
            description="Transparency report on ingested ledger health, duplicate row percentages, unconfirmed date gaps, and freshness indicators.",
            supported_formats=["PDF", "CSV", "XLSX"],
            required_data_sources=["Sales Uploads", "Data Quality Engine"],
            parameters_schema={"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"},
        ),
        ReportCatalogItem(
            report_type=ReportType.SCENARIO_COMPARISON.value,
            category="Strategy & Forecasting",
            title="What-If Sensitivity & Stress Shock Comparison",
            description="Comparative analysis of simulated business shocks (sales drops, cost increases, collection delays) against baseline runway.",
            supported_formats=["PDF", "CSV", "XLSX"],
            required_data_sources=["What-If Scenarios"],
            parameters_schema={"scenario_id": "Optional specific scenario comparison"},
        ),
    ]

    def __init__(self, db: Session, storage: ReportStorageService | None = None) -> None:
        self.db = db
        self.storage = storage or ReportStorageService()

    # --- Catalog & Parameter Validation ---

    def get_catalog(self) -> ReportCatalogResponse:
        """Return supported report catalogue."""
        return ReportCatalogResponse(
            items=self.CATALOG,
            total_reports=len(self.CATALOG),
        )

    def validate_parameters(
        self,
        report_type: str,
        start_date: date | None = None,
        end_date: date | None = None,
        file_format: str = "PDF",
    ) -> tuple[date, date, str]:
        """Validate report parameters and return canonicalized (start_date, end_date, format)."""
        valid_types = [c.report_type for c in self.CATALOG]
        if report_type not in valid_types:
            raise ValueError(f"Unsupported report type: '{report_type}'. Must be one of {valid_types}.")

        fmt = file_format.upper().strip()
        if fmt not in ("PDF", "CSV", "XLSX"):
            raise ValueError(f"Unsupported export format: '{file_format}'. Must be PDF, CSV, or XLSX.")

        today = date.today()
        if end_date is None:
            end_date = today
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        if start_date > end_date:
            raise ValueError(f"Invalid date range: start_date ({start_date}) cannot be after end_date ({end_date}).")

        return start_date, end_date, fmt

    # --- Report Data Collectors & Aggregators ---

    def _collect_executive_summary_data(
        self, business: Business, start_date: date, end_date: date
    ) -> tuple[list[str], dict[str, Any], list[ReportTableData], ReportProvenance, str]:
        """Aggregate Executive Summary report data."""
        health = HealthScoreService.compute(business)
        kpis = KpiService.compute(business)

        findings = [
            f"Overall Business Health Score evaluated at {health.score}/100 with Grade '{health.grade}' ({health.status}).",
            f"Annual business revenue recorded as INR {business.annual_revenue:,.2f} with {business.employee_count or 0} active employees.",
            f"Industry classification: {business.industry or 'General MSME'} in {business.state_region or 'India'}.",
            f"Operational stage identified as {business.established_year or 'established'} cohort.",
        ]

        summary = {
            "health_score": health.score,
            "health_grade": health.grade,
            "health_status": health.status,
            "annual_revenue": business.annual_revenue,
            "employee_count": business.employee_count or 0,
            "kpi_completeness": kpis.profile_completion,
        }

        tables = [
            ReportTableData(
                title="Business Health Diagnostics",
                headers=["Dimension", "Score / Metric", "Assessment"],
                rows=[
                    ["Overall Health", f"{health.score}/100", health.grade],
                    ["Financial Stability", f"₹{business.annual_revenue:,.2f}", "Annual Reported Revenue"],
                    ["Workforce Size", str(business.employee_count or 0), "Full-time Equivalent"],
                    ["Data Completeness", f"{kpis.profile_completion}%", "Profile Confidence"],
                ],
            )
        ]

        provenance = ReportProvenance(
            metric_name="Executive Business Diagnostic",
            calculation_method="UrsBiz Digital Twin Multidimensional Scoring Model (HealthScoreEngine v2.0)",
            evidence_source="Authoritative Business Digital Twin Profile & Historical Record",
            event_nature=EvidenceNature.CONFIRMED_EVENT.value,
            observation_window=f"{start_date.isoformat()} to {end_date.isoformat()}",
            assumptions=["Business profile inputs are verified by authorized owner."],
            limitations=["Health score reflects profile parameters and connected modules."],
            disclaimer=self.STANDARD_DISCLAIMER,
        )

        return findings, summary, tables, provenance, ReportCoverageStatus.AVAILABLE.value

    def _collect_sales_revenue_data(
        self, business: Business, start_date: date, end_date: date
    ) -> tuple[list[str], dict[str, Any], list[ReportTableData], ReportProvenance, str]:
        """Aggregate Sales & Revenue Performance report data."""
        # Query confirmed sales uploads
        uploads = (
            self.db.query(SalesUpload)
            .filter(
                SalesUpload.business_id == business.id,
                SalesUpload.status.in_(["processed", "partial_success", "completed"]),
            )
            .all()
        )

        # Check transactions within window
        s_dt = datetime.combine(start_date, datetime.min.time())
        e_dt = datetime.combine(end_date, datetime.max.time())

        txns = (
            self.db.query(SalesTransaction)
            .filter(
                SalesTransaction.business_id == business.id,
                SalesTransaction.transaction_date >= s_dt,
                SalesTransaction.transaction_date <= e_dt,
                SalesTransaction.is_duplicate.is_(False),
            )
            .order_by(SalesTransaction.transaction_date.asc())
            .all()
        )

        if not uploads:
            findings = ["No sales uploads have been processed for this business."]
            summary = {"total_revenue": 0.0, "transaction_count": 0, "aov": 0.0}
            tables = [
                ReportTableData(
                    title="Revenue Performance",
                    headers=["Period", "Gross Revenue (INR)", "Transactions", "AOV (INR)"],
                    rows=[],
                    notes="No sales ledger records found. Upload sales CSV to generate performance data.",
                )
            ]
            provenance = ReportProvenance(
                metric_name="Gross Sales Revenue",
                calculation_method="Sum of non-duplicate sales transactions within window",
                evidence_source="Authoritative Sales Ledger (Empty)",
                event_nature=EvidenceNature.WARNING.value,
                observation_window=f"{start_date.isoformat()} to {end_date.isoformat()}",
                assumptions=["No transactions ingested."],
                limitations=["Zero transactions recorded in observation period."],
                disclaimer=self.STANDARD_DISCLAIMER,
            )
            return findings, summary, tables, provenance, ReportCoverageStatus.MISSING_DATA.value

        total_rev = sum(t.total_amount for t in txns)
        txn_count = len(txns)
        aov = (total_rev / txn_count) if txn_count > 0 else 0.0

        # Group by day or month for table
        daily_rev: dict[str, list[float]] = {}
        for t in txns:
            d_str = t.transaction_date.strftime("%Y-%m-%d")
            daily_rev.setdefault(d_str, []).append(t.total_amount)

        table_rows = []
        for d_str, amounts in sorted(daily_rev.items()):
            table_rows.append([
                d_str,
                f"₹{sum(amounts):,.2f}",
                len(amounts),
                f"₹{(sum(amounts) / len(amounts)):,.2f}",
            ])

        findings = [
            f"Total Gross Revenue: INR {total_rev:,.2f} across {txn_count} transactions.",
            f"Average Order Value (AOV): INR {aov:,.2f}.",
            f"Active trading days recorded: {len(daily_rev)} distinct calendar days.",
        ]

        summary = {
            "total_revenue": total_rev,
            "transaction_count": txn_count,
            "aov": round(aov, 2),
            "trading_days": len(daily_rev),
        }

        tables = [
            ReportTableData(
                title="Daily Revenue Breakdown",
                headers=["Date", "Revenue", "Order Count", "Daily AOV"],
                rows=table_rows[:31],  # Max 31 rows preview
                notes=f"Displaying {min(len(table_rows), 31)} of {len(table_rows)} trading days.",
            )
        ]

        provenance = ReportProvenance(
            metric_name="Gross Sales Revenue & AOV",
            calculation_method="SUM(total_amount), COUNT(id), AVG(total_amount) grouped by calendar date",
            evidence_source=f"Authoritative Sales Ledger ({len(uploads)} confirmed uploads, {txn_count} transactions)",
            event_nature=EvidenceNature.CONFIRMED_EVENT.value,
            observation_window=f"{start_date.isoformat()} to {end_date.isoformat()}",
            assumptions=["Transactions represent verified completed sales."],
            limitations=["Duplicate records excluded from calculations."],
            disclaimer=self.STANDARD_DISCLAIMER,
        )

        coverage = ReportCoverageStatus.AVAILABLE.value if txn_count > 0 else ReportCoverageStatus.PARTIAL_DATA.value
        return findings, summary, tables, provenance, coverage

    def _collect_customer_performance_data(
        self, business: Business, start_date: date, end_date: date
    ) -> tuple[list[str], dict[str, Any], list[ReportTableData], ReportProvenance, str]:
        """Aggregate Customer Concentration & Performance data."""
        s_dt = datetime.combine(start_date, datetime.min.time())
        e_dt = datetime.combine(end_date, datetime.max.time())

        txns = (
            self.db.query(SalesTransaction)
            .filter(
                SalesTransaction.business_id == business.id,
                SalesTransaction.transaction_date >= s_dt,
                SalesTransaction.transaction_date <= e_dt,
                SalesTransaction.is_duplicate.is_(False),
            )
            .all()
        )

        if not txns:
            return (
                ["No customer transaction records available for this observation window."],
                {"top1_concentration_pct": 0.0, "total_customers": 0, "repeat_customer_rate": 0.0},
                [ReportTableData(title="Customer Performance", headers=["Customer", "Revenue", "Share"], rows=[])],
                ReportProvenance(
                    calculation_method="Customer concentration and repeat rate math",
                    evidence_source="Authoritative Sales Ledger (0 records)",
                    event_nature=EvidenceNature.WARNING.value,
                    disclaimer=self.STANDARD_DISCLAIMER,
                ),
                ReportCoverageStatus.MISSING_DATA.value,
            )

        cust_rev: dict[str, float] = {}
        cust_orders: dict[str, int] = {}
        for t in txns:
            c = t.customer_name or "Walk-in Customer"
            cust_rev[c] = cust_rev.get(c, 0.0) + t.total_amount
            cust_orders[c] = cust_orders.get(c, 0) + 1

        total_rev = sum(cust_rev.values())
        sorted_cust = sorted(cust_rev.items(), key=lambda x: x[1], reverse=True)
        top1_rev = sorted_cust[0][1] if sorted_cust else 0.0
        top3_rev = sum(v for _, v in sorted_cust[:3])
        top1_share = (top1_rev / total_rev * 100.0) if total_rev > 0 else 0.0
        top3_share = (top3_rev / total_rev * 100.0) if total_rev > 0 else 0.0

        repeat_count = sum(1 for c, o in cust_orders.items() if o > 1)
        repeat_rate = (repeat_count / len(cust_orders) * 100.0) if cust_orders else 0.0

        findings = [
            f"Identified {len(cust_orders)} distinct purchasing customers.",
            f"Top Customer: '{sorted_cust[0][0]}' represents {top1_share:.1f}% of total period revenue.",
            f"Top 3 Customers contribute {top3_share:.1f}% of total sales.",
            f"Repeat Customer Rate is {repeat_rate:.1f}% ({repeat_count} multi-purchase customers).",
        ]

        summary = {
            "total_customers": len(cust_orders),
            "top1_concentration_pct": round(top1_share, 1),
            "top3_concentration_pct": round(top3_share, 1),
            "repeat_customer_rate": round(repeat_rate, 1),
            "top_customer_name": sorted_cust[0][0],
        }

        table_rows = []
        for c_name, c_amt in sorted_cust[:15]:
            c_share = (c_amt / total_rev * 100.0) if total_rev > 0 else 0.0
            table_rows.append([
                c_name,
                f"₹{c_amt:,.2f}",
                cust_orders[c_name],
                f"{c_share:.1f}%",
            ])

        tables = [
            ReportTableData(
                title="Top Customers by Revenue Contribution",
                headers=["Customer Name", "Total Spend (INR)", "Orders", "Revenue Share"],
                rows=table_rows,
            )
        ]

        provenance = ReportProvenance(
            metric_name="Customer Concentration & Retention",
            calculation_method="SUM(total_amount) by customer_name / TOTAL(revenue) * 100",
            evidence_source=f"Authoritative Sales Transactions ({len(txns)} records)",
            event_nature=EvidenceNature.CONFIRMED_EVENT.value,
            observation_window=f"{start_date.isoformat()} to {end_date.isoformat()}",
            assumptions=["Customer identity resolved from ledger customer_name."],
            limitations=["Anonymous walk-in transactions aggregated under generic label."],
            disclaimer=self.STANDARD_DISCLAIMER,
        )

        return findings, summary, tables, provenance, ReportCoverageStatus.AVAILABLE.value

    def _collect_product_performance_data(
        self, business: Business, start_date: date, end_date: date
    ) -> tuple[list[str], dict[str, Any], list[ReportTableData], ReportProvenance, str]:
        """Aggregate Product Performance & Velocity data."""
        s_dt = datetime.combine(start_date, datetime.min.time())
        e_dt = datetime.combine(end_date, datetime.max.time())

        txns = (
            self.db.query(SalesTransaction)
            .filter(
                SalesTransaction.business_id == business.id,
                SalesTransaction.transaction_date >= s_dt,
                SalesTransaction.transaction_date <= e_dt,
                SalesTransaction.is_duplicate.is_(False),
            )
            .all()
        )

        if not txns:
            return (
                ["No product sales records available in observation window."],
                {"total_products_sold": 0, "top_product": "N/A"},
                [ReportTableData(title="Product Performance", headers=["Product", "Qty", "Revenue"], rows=[])],
                ReportProvenance(
                    calculation_method="Product sales aggregation",
                    evidence_source="Authoritative Sales Ledger (0 records)",
                    event_nature=EvidenceNature.WARNING.value,
                    disclaimer=self.STANDARD_DISCLAIMER,
                ),
                ReportCoverageStatus.MISSING_DATA.value,
            )

        prod_rev: dict[str, float] = {}
        prod_qty: dict[str, int] = {}
        for t in txns:
            p = t.product_name or "Unlabeled SKU"
            prod_rev[p] = prod_rev.get(p, 0.0) + t.total_amount
            prod_qty[p] = prod_qty.get(p, 0) + (t.quantity or 1)

        total_rev = sum(prod_rev.values())
        sorted_prod = sorted(prod_rev.items(), key=lambda x: x[1], reverse=True)
        top_prod = sorted_prod[0][0]

        findings = [
            f"Recorded sales across {len(prod_rev)} distinct products / SKUs.",
            f"Top Revenue Generator: '{top_prod}' generated INR {sorted_prod[0][1]:,.2f} ({sorted_prod[0][1]/total_rev*100:.1f}% share).",
            f"Total volume sold: {sum(prod_qty.values()):,} units across window.",
        ]

        summary = {
            "unique_products_sold": len(prod_rev),
            "total_units_sold": sum(prod_qty.values()),
            "top_product": top_prod,
            "top_product_revenue": sorted_prod[0][1],
        }

        table_rows = []
        for p_name, p_amt in sorted_prod[:20]:
            p_share = (p_amt / total_rev * 100.0) if total_rev > 0 else 0.0
            table_rows.append([
                p_name,
                f"{prod_qty[p_name]:,}",
                f"₹{p_amt:,.2f}",
                f"{p_share:.1f}%",
            ])

        tables = [
            ReportTableData(
                title="Product Sales & Velocity Ranking",
                headers=["Product / SKU", "Units Sold", "Total Revenue (INR)", "Revenue Share"],
                rows=table_rows,
            )
        ]

        provenance = ReportProvenance(
            metric_name="Product Sales Velocity & Revenue Share",
            calculation_method="SUM(quantity), SUM(total_amount) grouped by product_name",
            evidence_source=f"Authoritative Sales Transactions ({len(txns)} records)",
            event_nature=EvidenceNature.CONFIRMED_EVENT.value,
            observation_window=f"{start_date.isoformat()} to {end_date.isoformat()}",
            assumptions=["Product names in transactions correspond to active commercial offerings."],
            limitations=["Unit cost data not factored into product gross margin unless COGS available."],
            disclaimer=self.STANDARD_DISCLAIMER,
        )

        return findings, summary, tables, provenance, ReportCoverageStatus.AVAILABLE.value

    def _collect_decisions_summary_data(
        self, business: Business, start_date: date, end_date: date
    ) -> tuple[list[str], dict[str, Any], list[ReportTableData], ReportProvenance, str]:
        """Aggregate Business Decisions & Evaluated Outcomes data."""
        decisions = (
            self.db.query(BusinessDecision)
            .filter(
                BusinessDecision.business_id == business.id,
                BusinessDecision.is_deleted.is_(False),
            )
            .order_by(BusinessDecision.created_at.desc())
            .all()
        )

        status_counts: dict[str, int] = {}
        for d in decisions:
            status_counts[d.status] = status_counts.get(d.status, 0) + 1

        findings = [
            f"Total decisions logged in Decision Workbench: {len(decisions)}.",
            f"Status breakdown: {status_counts.get('ACCEPTED', 0)} Accepted, {status_counts.get('IMPLEMENTED', 0)} Implemented, {status_counts.get('REJECTED', 0)} Rejected, {status_counts.get('EVALUATED', 0)} Evaluated.",
        ]

        summary = {
            "total_decisions": len(decisions),
            "accepted_count": status_counts.get("ACCEPTED", 0),
            "implemented_count": status_counts.get("IMPLEMENTED", 0),
            "rejected_count": status_counts.get("REJECTED", 0),
        }

        table_rows = []
        for d in decisions[:25]:
            table_rows.append([
                d.title,
                d.decision_type,
                d.status,
                d.created_at.strftime("%Y-%m-%d"),
                d.decision_rationale or d.objective or "N/A",
            ])

        tables = [
            ReportTableData(
                title="Strategic Decisions Log",
                headers=["Title", "Type", "Status", "Date", "Justification / Notes"],
                rows=table_rows,
                notes="Displaying up to 25 recent non-archived decisions.",
            )
        ]

        provenance = ReportProvenance(
            metric_name="Strategic Decision Governance Audit",
            calculation_method="Audit trail aggregation of Decision Workbench records",
            evidence_source="Authoritative Business Decision Log & Outcome Evaluations",
            event_nature=EvidenceNature.CONFIRMED_EVENT.value,
            observation_window=f"All active records up to {end_date.isoformat()}",
            assumptions=["Decisions recorded directly by authorized business owner/operators."],
            limitations=["Financial impacts reflect simulated before/after model estimates."],
            disclaimer=self.STANDARD_DISCLAIMER,
        )

        return findings, summary, tables, provenance, ReportCoverageStatus.AVAILABLE.value

    def _collect_alerts_summary_data(
        self, business: Business, start_date: date, end_date: date
    ) -> tuple[list[str], dict[str, Any], list[ReportTableData], ReportProvenance, str]:
        """Aggregate Business Signal Alerts & Operational Events data."""
        alerts = (
            self.db.query(BusinessSignalEvent)
            .filter(
                BusinessSignalEvent.business_id == business.id,
                BusinessSignalEvent.is_archived.is_(False),
            )
            .order_by(BusinessSignalEvent.detected_at.desc())
            .all()
        )

        sev_counts: dict[str, int] = {}
        nature_counts: dict[str, int] = {}
        for a in alerts:
            sev_counts[a.severity] = sev_counts.get(a.severity, 0) + 1
            nature_counts[a.event_nature] = nature_counts.get(a.event_nature, 0) + 1

        findings = [
            f"Total active business signals & alerts: {len(alerts)}.",
            f"Severity breakdown: {sev_counts.get('CRITICAL', 0)} Critical, {sev_counts.get('WARNING', 0)} Warnings, {sev_counts.get('INFO', 0)} Info.",
            f"Event nature classification: {nature_counts.get('CONFIRMED_EVENT', 0)} Confirmed Events, {nature_counts.get('ESTIMATE', 0)} Statistical Estimates, {nature_counts.get('WARNING', 0)} Threshold Warnings, {nature_counts.get('ASSUMPTION', 0)} Assumptions.",
        ]

        summary = {
            "total_alerts": len(alerts),
            "critical_count": sev_counts.get("CRITICAL", 0),
            "warning_count": sev_counts.get("WARNING", 0),
            "info_count": sev_counts.get("INFO", 0),
        }

        table_rows = []
        for a in alerts[:25]:
            det_date = a.detected_at.strftime("%Y-%m-%d") if a.detected_at else "N/A"
            table_rows.append([
                a.title,
                a.severity,
                a.event_nature,
                a.status,
                det_date,
            ])

        tables = [
            ReportTableData(
                title="Business Alerts & Signal Events",
                headers=["Event Title", "Severity", "Nature", "Status", "Detected Date"],
                rows=table_rows,
            )
        ]

        provenance = ReportProvenance(
            metric_name="Operational Signal & Alert Event Center",
            calculation_method="Deterministic heuristic & statistical anomaly detection suite (2-sigma, velocity, staleness)",
            evidence_source="Authoritative Business Signal Events & Ingestion Audits",
            event_nature=EvidenceNature.CONFIRMED_EVENT.value,
            observation_window=f"Active events up to {end_date.isoformat()}",
            assumptions=["Detectors executed against latest confirmed ledger state."],
            limitations=["Minimum history thresholds applied to prevent spurious small-sample alerts."],
            disclaimer=self.STANDARD_DISCLAIMER,
        )

        return findings, summary, tables, provenance, ReportCoverageStatus.AVAILABLE.value

    def _collect_goals_progress_data(
        self, business: Business, start_date: date, end_date: date
    ) -> tuple[list[str], dict[str, Any], list[ReportTableData], ReportProvenance, str]:
        """Aggregate Business Goals & Progress Tracker data."""
        goal_service = BusinessGoalService(self.db)
        goals = (
            self.db.query(BusinessGoal)
            .filter(
                BusinessGoal.business_id == business.id,
                BusinessGoal.is_archived.is_(False),
            )
            .order_by(BusinessGoal.created_at.desc())
            .all()
        )

        achieved_count = 0
        table_rows = []
        for g in goals:
            # Re-evaluate progress deterministically (read-only)
            evaluated = goal_service._populate_and_evaluate_goal(g, persist=False)
            if evaluated.current_value is not None and evaluated.current_value >= evaluated.target_value:
                achieved_count += 1
            
            prog_str = f"{evaluated.progress_pct:.1f}%" if evaluated.progress_pct is not None else "Pending"
            cur_str = f"{evaluated.current_value:,.2f}" if evaluated.current_value is not None else "N/A"
            table_rows.append([
                evaluated.title,
                evaluated.metric_key or "manual",
                f"{evaluated.target_value:,.2f} {evaluated.unit}",
                f"{cur_str} {evaluated.unit}",
                prog_str,
                evaluated.status,
                evaluated.data_availability,
            ])

        findings = [
            f"Total active business goals tracked: {len(goals)}.",
            f"Milestones achieved: {achieved_count} of {len(goals)} goals met.",
            "All metric-linked progress calculations evaluated using deterministic backend formulas.",
        ]

        summary = {
            "total_goals": len(goals),
            "achieved_goals": achieved_count,
            "completion_rate_pct": round((achieved_count / len(goals) * 100.0) if goals else 0.0, 1),
        }

        tables = [
            ReportTableData(
                title="Business Objectives & Milestones",
                headers=["Goal Title", "Metric", "Target", "Current", "Progress", "Status", "Data Availability"],
                rows=table_rows,
            )
        ]

        provenance = ReportProvenance(
            metric_name="Business Goals & Deterministic Progress",
            calculation_method="Goal progress evaluation via BusinessGoalService v1.0",
            evidence_source="Authoritative Business Goals, Sales Ledger, and Twin Health Score",
            event_nature=EvidenceNature.CONFIRMED_EVENT.value,
            observation_window=f"All active goals as of {end_date.isoformat()}",
            assumptions=["Target dates and baselines established by authorized business owner."],
            limitations=["Periods with unconfirmed data coverage flagged as MISSING_DATA without fabrication."],
            disclaimer=self.STANDARD_DISCLAIMER,
        )

        return findings, summary, tables, provenance, ReportCoverageStatus.AVAILABLE.value

    def _collect_data_quality_audit_data(
        self, business: Business, start_date: date, end_date: date
    ) -> tuple[list[str], dict[str, Any], list[ReportTableData], ReportProvenance, str]:
        """Aggregate Data Quality & Provenance Audit data."""
        uploads = (
            self.db.query(SalesUpload)
            .filter(SalesUpload.business_id == business.id)
            .order_by(SalesUpload.created_at.desc())
            .all()
        )

        total_rows = sum(u.row_count for u in uploads)
        valid_rows = sum(u.valid_row_count for u in uploads)
        invalid_rows = sum(u.invalid_row_count for u in uploads)
        completed_count = sum(1 for u in uploads if u.status in ("processed", "completed"))

        valid_pct = (valid_rows / total_rows * 100.0) if total_rows > 0 else 100.0

        findings = [
            f"Total Ingestion Batches: {len(uploads)} upload events recorded.",
            f"Total records processed: {total_rows:,} ({valid_rows:,} valid, {invalid_rows:,} excluded).",
            f"Overall Ledger Ingestion Health: {valid_pct:.1f}% valid row rate.",
            f"Completed & verified uploads: {completed_count} of {len(uploads)}.",
        ]

        summary = {
            "total_uploads": len(uploads),
            "completed_uploads": completed_count,
            "total_rows": total_rows,
            "valid_rows": valid_rows,
            "valid_rate_pct": round(valid_pct, 1),
        }

        table_rows = []
        for u in uploads[:20]:
            table_rows.append([
                u.filename,
                u.file_format.upper(),
                u.status.upper(),
                f"{u.row_count:,}",
                f"{u.valid_row_count:,}",
                f"{u.invalid_row_count:,}",
                u.created_at.strftime("%Y-%m-%d %H:%M"),
            ])

        tables = [
            ReportTableData(
                title="Data Ingestion & Integrity Log",
                headers=["File Name", "Format", "Status", "Total Rows", "Valid Rows", "Excluded Rows", "Ingested At"],
                rows=table_rows,
            )
        ]

        provenance = ReportProvenance(
            metric_name="Data Quality & Confidence Ingestion Audit",
            calculation_method="Audit logging from Ingestion Pipeline and DataFreshnessEngine",
            evidence_source=f"Authoritative SalesUpload Records ({len(uploads)} batches)",
            event_nature=EvidenceNature.CONFIRMED_EVENT.value,
            observation_window=f"Historical ingestion log through {end_date.isoformat()}",
            assumptions=["Upload statuses updated upon verification completion."],
            limitations=["Does not inspect external source systems beyond uploaded files."],
            disclaimer=self.STANDARD_DISCLAIMER,
        )

        return findings, summary, tables, provenance, ReportCoverageStatus.AVAILABLE.value

    def _collect_scenario_comparison_data(
        self, business: Business, start_date: date, end_date: date
    ) -> tuple[list[str], dict[str, Any], list[ReportTableData], ReportProvenance, str]:
        """Aggregate What-If Sensitivity & Stress Shock Comparison data."""
        scenarios = (
            self.db.query(WhatIfScenario)
            .filter(WhatIfScenario.business_id == business.id)
            .order_by(WhatIfScenario.created_at.desc())
            .all()
        )

        findings = [
            f"Total simulation scenarios configured: {len(scenarios)}.",
            "Scenarios stress-test operational resiliency against demand shocks, price elasticity, and cost spikes.",
        ]

        summary = {
            "scenario_count": len(scenarios),
        }

        table_rows = []
        for s in scenarios[:15]:
            bm = s.baseline_metrics or {}
            pr = s.projection_result or {}
            cases = pr.get("cases") or []
            base_case = cases[0] if cases and isinstance(cases, list) else {}

            baseline_gp = float(bm.get("monthly_gross_profit_inr") or bm.get("gross_profit") or 0.0)
            sim_gp = float(base_case.get("projected_gross_profit_inr") or pr.get("simulated_gross_profit") or baseline_gp)
            delta_gp = float(base_case.get("gross_profit_delta_inr") or (sim_gp - baseline_gp))
            runway = base_case.get("cash_runway_days_estimated")
            if runway is None:
                runway = pr.get("cash_runway_days")
            runway_str = f"{runway} days" if runway is not None else "N/A"

            table_rows.append([
                s.title,
                s.scenario_type,
                f"₹{baseline_gp:,.2f}",
                f"₹{sim_gp:,.2f}",
                f"₹{delta_gp:,.2f}",
                runway_str,
            ])

        tables = [
            ReportTableData(
                title="What-If Scenario Stress Testing Matrix",
                headers=["Scenario Title", "Shock Type", "Baseline GP", "Simulated GP", "Delta (INR)", "Runway Impact"],
                rows=table_rows,
            )
        ]

        provenance = ReportProvenance(
            metric_name="What-If Scenario Sensitivity Simulator",
            calculation_method="Deterministic economic shock simulation via WhatIfScenarioService v1.0",
            evidence_source="Authoritative Ingested Ledger & Stress Parameters",
            event_nature=EvidenceNature.ESTIMATE.value,
            observation_window=f"Simulations created up to {end_date.isoformat()}",
            assumptions=["Simulated shock percentages applied uniformly to baseline period."],
            limitations=["Simulations represent projections, not confirmed historical events."],
            disclaimer=self.STANDARD_DISCLAIMER,
        )

        return findings, summary, tables, provenance, ReportCoverageStatus.AVAILABLE.value

    # --- Master Collector Dispatcher ---

    def collect_report_data(
        self, business: Business, report_type: str, start_date: date, end_date: date
    ) -> tuple[str, list[str], dict[str, Any], list[ReportTableData], ReportProvenance, str]:
        """Dispatch to appropriate collector and return standardized report elements."""
        cat_item = next((c for c in self.CATALOG if c.report_type == report_type), None)
        title = cat_item.title if cat_item else report_type.replace("_", " ").title()

        if report_type == ReportType.EXECUTIVE_SUMMARY.value:
            findings, summary, tables, prov, cov = self._collect_executive_summary_data(business, start_date, end_date)
        elif report_type == ReportType.SALES_REVENUE_PERFORMANCE.value:
            findings, summary, tables, prov, cov = self._collect_sales_revenue_data(business, start_date, end_date)
        elif report_type == ReportType.CUSTOMER_PERFORMANCE.value:
            findings, summary, tables, prov, cov = self._collect_customer_performance_data(business, start_date, end_date)
        elif report_type == ReportType.PRODUCT_PERFORMANCE.value:
            findings, summary, tables, prov, cov = self._collect_product_performance_data(business, start_date, end_date)
        elif report_type == ReportType.DECISIONS_SUMMARY.value:
            findings, summary, tables, prov, cov = self._collect_decisions_summary_data(business, start_date, end_date)
        elif report_type == ReportType.ALERTS_SUMMARY.value:
            findings, summary, tables, prov, cov = self._collect_alerts_summary_data(business, start_date, end_date)
        elif report_type == ReportType.GOALS_PROGRESS.value:
            findings, summary, tables, prov, cov = self._collect_goals_progress_data(business, start_date, end_date)
        elif report_type == ReportType.DATA_QUALITY_AUDIT.value:
            findings, summary, tables, prov, cov = self._collect_data_quality_audit_data(business, start_date, end_date)
        elif report_type == ReportType.SCENARIO_COMPARISON.value:
            findings, summary, tables, prov, cov = self._collect_scenario_comparison_data(business, start_date, end_date)
        else:
            raise ValueError(f"Collector for report type '{report_type}' is not implemented.")

        return title, findings, summary, tables, prov, cov

    # --- Live Preview Generation ---

    def preview_report(self, business: Business, req: ReportPreviewRequest) -> ReportPreviewResponse:
        """Generate live structured preview for active business without writing to disk."""
        start_date, end_date, _ = self.validate_parameters(
            req.report_type, req.start_date, req.end_date, req.format
        )

        title, findings, summary, tables, provenance, coverage = self.collect_report_data(
            business, req.report_type, start_date, end_date
        )

        custom_title = req.title.strip() if req.title and req.title.strip() else title
        now_iso = datetime.now(timezone.utc).isoformat()
        period_str = f"{start_date.isoformat()} to {end_date.isoformat()}"

        # Deterministic executive summary text
        ai_explanation = (
            f"Evidence summary for {business.legal_name}: Evaluated {len(findings)} key findings across "
            f"observation period {period_str}. Data coverage evaluated as {coverage}."
        )

        return ReportPreviewResponse(
            report_type=req.report_type,
            title=custom_title,
            business_name=business.legal_name,
            business_id=business.id,
            reporting_period=period_str,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            coverage_status=coverage,
            freshness_warning=None if coverage == "AVAILABLE" else "Incomplete data coverage or missing uploads in requested period.",
            key_findings=findings,
            summary_metrics=summary,
            tables=tables,
            provenance=provenance,
            ai_explanation=ai_explanation,
            generated_at=now_iso,
        )

    # --- Binary File Exporters (PDF, CSV, XLSX) ---

    def render_pdf(
        self,
        business: Business,
        title: str,
        period_str: str,
        findings: list[str],
        summary: dict[str, Any],
        tables: list[ReportTableData],
        provenance: ReportProvenance,
        report_id: str,
    ) -> bytes:
        """Render publication-grade PDF using ReportLab."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0F172A"),
            fontName=_UNICODE_FONT_NAME,
        )
        subtitle_style = ParagraphStyle(
            "ReportSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#475569"),
            fontName=_UNICODE_FONT_NAME,
        )
        h2_style = ParagraphStyle(
            "SectionH2",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#1E3A8A"),
            fontName=_UNICODE_FONT_NAME,
            spaceBefore=10,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "ReportBody",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#1E293B"),
            fontName=_UNICODE_FONT_NAME,
        )
        th_style = ParagraphStyle(
            "TH",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.white,
            fontName=_UNICODE_FONT_NAME,
        )
        tc_style = ParagraphStyle(
            "TC",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#0F172A"),
            fontName=_UNICODE_FONT_NAME,
        )
        disc_style = ParagraphStyle(
            "Disc",
            parent=styles["Normal"],
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#64748B"),
            fontName=_UNICODE_FONT_NAME,
        )

        story = []

        # 1. Header & Branding
        story.append(Paragraph("URSBIZ BUSINESS INTELLIGENCE & EVIDENCE EXPORT", subtitle_style))
        story.append(Paragraph(_sanitize_pdf_text(title), title_style))
        story.append(Spacer(1, 4))
        header_meta = (
            f"Business: <b>{_sanitize_pdf_text(business.legal_name)}</b> | "
            f"Industry: {_sanitize_pdf_text(business.industry or 'MSME')} | "
            f"Period: {period_str} | ID: {report_id}"
        )
        story.append(Paragraph(header_meta, subtitle_style))
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E3A8A"), spaceAfter=10))

        # 2. Executive Key Findings Box
        story.append(Paragraph("Key Findings & Executive Evidence", h2_style))
        finding_paragraphs = [
            Paragraph(f"&bull; {_sanitize_pdf_text(f)}", body_style) for f in findings
        ]
        finding_table = Table([[p] for p in finding_paragraphs], colWidths=["100%"])
        finding_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0F7FF")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#93C5FD")),
                ("PADDING", (0, 0), (-1, -1), 8),
            ])
        )
        story.append(finding_table)
        story.append(Spacer(1, 10))

        # 3. Data Tables
        for t_data in tables:
            story.append(Paragraph(_sanitize_pdf_text(t_data.title), h2_style))
            if not t_data.rows:
                story.append(Paragraph("No records found for this section in the specified period.", body_style))
                story.append(Spacer(1, 8))
                continue

            tbl_data = []
            # Headers
            tbl_data.append([Paragraph(_sanitize_pdf_text(h), th_style) for h in t_data.headers])
            # Rows
            for row in t_data.rows[:25]:  # Safety limit for single page
                tbl_data.append([Paragraph(_sanitize_pdf_text(str(cell)), tc_style) for cell in row])

            r_table = Table(tbl_data, repeatRows=1)
            r_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ])
            )
            story.append(r_table)
            if t_data.notes:
                story.append(Spacer(1, 2))
                story.append(Paragraph(_sanitize_pdf_text(t_data.notes), disc_style))
            story.append(Spacer(1, 10))

        # 4. Evidence Provenance & Disclaimer Box
        story.append(KeepTogether([
            Paragraph("Evidence Provenance & Methodology", h2_style),
            Paragraph(f"<b>Calculation Method:</b> {_sanitize_pdf_text(provenance.calculation_method)}", body_style),
            Paragraph(f"<b>Evidence Source:</b> {_sanitize_pdf_text(provenance.evidence_source)}", body_style),
            Paragraph(f"<b>Classification:</b> {_sanitize_pdf_text(provenance.event_nature)} | <b>Observation Window:</b> {provenance.observation_window or period_str}", body_style),
            Spacer(1, 4),
            Paragraph(f"<b>Legal & Audit Disclaimer:</b> {_sanitize_pdf_text(provenance.disclaimer)}", disc_style),
        ]))

        doc.build(story)
        return buffer.getvalue()

    def render_csv(
        self,
        business: Business,
        title: str,
        period_str: str,
        findings: list[str],
        summary: dict[str, Any],
        tables: list[ReportTableData],
        provenance: ReportProvenance,
        report_id: str,
    ) -> bytes:
        """Render safe, formula-injection-protected CSV string encoded as UTF-8 with BOM."""
        output = io.StringIO()
        writer = csv.writer(output)

        # 1. Metadata Block
        writer.writerow(["=== URSBIZ EVIDENCE REPORT ==="])
        writer.writerow(["Report Title", _sanitize_formula(title)])
        writer.writerow(["Report ID", _sanitize_formula(report_id)])
        writer.writerow(["Business Legal Name", _sanitize_formula(business.legal_name)])
        writer.writerow(["Industry", _sanitize_formula(business.industry or "MSME")])
        writer.writerow(["Observation Period", _sanitize_formula(period_str)])
        writer.writerow(["Generated At", datetime.now(timezone.utc).isoformat()])
        writer.writerow([])

        # 2. Key Findings Block
        writer.writerow(["=== KEY FINDINGS & EXECUTIVE EVIDENCE ==="])
        for idx, f in enumerate(findings, 1):
            writer.writerow([f"Finding {idx}", _sanitize_formula(f)])
        writer.writerow([])

        # 3. Summary Metrics Block
        writer.writerow(["=== SUMMARY METRICS ==="])
        writer.writerow(["Metric", "Value"])
        for k, v in summary.items():
            writer.writerow([_sanitize_formula(k), _sanitize_formula(v)])
        writer.writerow([])

        # 4. Data Tables
        for t_data in tables:
            writer.writerow([f"=== {t_data.title.upper()} ==="])
            writer.writerow([_sanitize_formula(h) for h in t_data.headers])
            for row in t_data.rows:
                writer.writerow([_sanitize_formula(cell) for cell in row])
            if t_data.notes:
                writer.writerow(["Notes", _sanitize_formula(t_data.notes)])
            writer.writerow([])

        # 5. Provenance & Disclaimer Block
        writer.writerow(["=== EVIDENCE PROVENANCE & METHODOLOGY ==="])
        writer.writerow(["Calculation Method", _sanitize_formula(provenance.calculation_method)])
        writer.writerow(["Evidence Source", _sanitize_formula(provenance.evidence_source)])
        writer.writerow(["Classification", _sanitize_formula(provenance.event_nature)])
        writer.writerow(["Observation Window", _sanitize_formula(provenance.observation_window or period_str)])
        writer.writerow(["Disclaimer", _sanitize_formula(provenance.disclaimer)])

        # Return utf-8-sig encoded bytes for seamless Excel/Unicode recognition
        return output.getvalue().encode("utf-8-sig")

    def render_xlsx(
        self,
        business: Business,
        title: str,
        period_str: str,
        findings: list[str],
        summary: dict[str, Any],
        tables: list[ReportTableData],
        provenance: ReportProvenance,
        report_id: str,
    ) -> bytes:
        """Render structured Excel workbook using openpyxl."""
        import openpyxl
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        title_font = Font(name="Calibri", size=16, bold=True, color="0F172A")
        sub_font = Font(name="Calibri", size=10, italic=True, color="475569")
        bold_font = Font(name="Calibri", size=11, bold=True)
        thin_border = Border(
            left=Side(style="thin", color="E2E8F0"),
            right=Side(style="thin", color="E2E8F0"),
            top=Side(style="thin", color="E2E8F0"),
            bottom=Side(style="thin", color="E2E8F0"),
        )

        # Tab 1: Executive Summary
        ws1 = wb.active
        ws1.title = "Summary"

        ws1["A1"] = _sanitize_formula(title)
        ws1["A1"].font = title_font
        ws1["A2"] = f"Business: {business.legal_name} | Period: {period_str} | ID: {report_id}"
        ws1["A2"].font = sub_font

        ws1["A4"] = "KEY FINDINGS"
        ws1["A4"].font = bold_font
        curr_row = 5
        for f in findings:
            ws1.cell(row=curr_row, column=1, value=_sanitize_formula(f"• {f}"))
            curr_row += 1

        curr_row += 1
        ws1.cell(row=curr_row, column=1, value="SUMMARY METRICS").font = bold_font
        curr_row += 1
        ws1.cell(row=curr_row, column=1, value="Metric").font = header_font
        ws1.cell(row=curr_row, column=1).fill = header_fill
        ws1.cell(row=curr_row, column=2, value="Value").font = header_font
        ws1.cell(row=curr_row, column=2).fill = header_fill
        curr_row += 1

        for k, v in summary.items():
            ws1.cell(row=curr_row, column=1, value=_sanitize_formula(k.replace("_", " ").title()))
            ws1.cell(row=curr_row, column=2, value=_sanitize_formula(v))
            curr_row += 1

        # Tab 2: Detailed Data Tables
        ws2 = wb.create_sheet(title="Data Tables")
        r_idx = 1
        for t_data in tables:
            ws2.cell(row=r_idx, column=1, value=_sanitize_formula(t_data.title)).font = bold_font
            r_idx += 1
            for col_idx, h in enumerate(t_data.headers, 1):
                c = ws2.cell(row=r_idx, column=col_idx, value=_sanitize_formula(h))
                c.font = header_font
                c.fill = header_fill
                c.alignment = Alignment(horizontal="center")
            r_idx += 1

            for row in t_data.rows:
                for col_idx, cell in enumerate(row, 1):
                    c = ws2.cell(row=r_idx, column=col_idx, value=_sanitize_formula(cell))
                    c.border = thin_border
                r_idx += 1
            r_idx += 2

        # Tab 3: Provenance & Audit
        ws3 = wb.create_sheet(title="Provenance")
        ws3["A1"] = "EVIDENCE PROVENANCE & AUDIT TRAIL"
        ws3["A1"].font = bold_font
        ws3["A3"] = "Calculation Method"
        ws3["B3"] = _sanitize_formula(provenance.calculation_method)
        ws3["A4"] = "Evidence Source"
        ws3["B4"] = _sanitize_formula(provenance.evidence_source)
        ws3["A5"] = "Classification"
        ws3["B5"] = _sanitize_formula(provenance.event_nature)
        ws3["A6"] = "Observation Window"
        ws3["B6"] = _sanitize_formula(provenance.observation_window or period_str)
        ws3["A7"] = "Disclaimer"
        ws3["B7"] = _sanitize_formula(provenance.disclaimer)

        for col_letter in ["A", "B"]:
            ws3[f"{col_letter}3"].font = bold_font

        # Auto-adjust column widths across sheets
        for sheet in (ws1, ws2, ws3):
            for col in sheet.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                col_letter = get_column_letter(col[0].column)
                sheet.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 60)

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    # --- Generate & Save Report (Full Flow) ---

    def generate_report(
        self,
        business: Business,
        user: User,
        req: ReportGenerateRequest,
        client_ip: str | None = None,
    ) -> BusinessReport:
        """Orchestrate report generation, persistent storage, and audit logging."""
        start_date, end_date, fmt = self.validate_parameters(
            req.report_type, req.start_date, req.end_date, req.format
        )

        title, findings, summary, tables, provenance, coverage = self.collect_report_data(
            business, req.report_type, start_date, end_date
        )

        report_title = req.title.strip() if req.title and req.title.strip() else title
        period_str = f"{start_date.isoformat()} to {end_date.isoformat()}"
        report_uid = f"rep_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"

        # Render format
        if fmt == "PDF":
            file_bytes = self.render_pdf(
                business, report_title, period_str, findings, summary, tables, provenance, report_uid
            )
        elif fmt == "CSV":
            file_bytes = self.render_csv(
                business, report_title, period_str, findings, summary, tables, provenance, report_uid
            )
        elif fmt == "XLSX":
            file_bytes = self.render_xlsx(
                business, report_title, period_str, findings, summary, tables, provenance, report_uid
            )
        else:
            raise ValueError(f"Unsupported format: {fmt}")

        # Save to isolated tenant filesystem
        rel_path, size_bytes, sha256 = self.storage.save_report_file(
            business_id=business.id,
            report_id=report_uid,
            file_format=fmt,
            content=file_bytes,
        )

        mime_type = self.storage.get_mime_type(fmt)

        # Create BusinessReport database record
        report = BusinessReport(
            report_id=report_uid,
            business_id=business.id,
            created_by_user_id=user.id,
            report_type=req.report_type,
            title=report_title,
            reporting_period=period_str,
            start_date=start_date,
            end_date=end_date,
            format=fmt,
            status=ReportStatus.COMPLETED.value,
            file_path=rel_path,
            file_size_bytes=size_bytes,
            mime_type=mime_type,
            checksum_sha256=sha256,
            parameters=req.parameters or {},
            summary_metrics=summary,
            provenance_metadata=provenance.model_dump(),
            download_count=0,
            expires_at=datetime.now(timezone.utc) + timedelta(days=90),
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        # Record immutable audit entry
        audit = BusinessReportAudit(
            report_id=report.id,
            business_id=business.id,
            user_id=user.id,
            action="GENERATED",
            format=fmt,
            status="SUCCESS",
            ip_address=client_ip,
            details={
                "report_type": req.report_type,
                "reporting_period": period_str,
                "file_size": size_bytes,
                "sha256": sha256,
            },
        )
        self.db.add(audit)
        self.db.commit()

        return report

    # --- History & Management ---

    def list_history(
        self,
        business_id: int,
        page: int = 1,
        page_size: int = 50,
        report_type: str | None = None,
    ) -> ReportHistoryResponse:
        """List generated reports history for tenant."""
        q = (
            self.db.query(BusinessReport)
            .filter(
                BusinessReport.business_id == business_id,
                BusinessReport.is_archived.is_(False),
            )
        )
        if report_type:
            q = q.filter(BusinessReport.report_type == report_type)

        total = q.count()
        rows = (
            q.order_by(BusinessReport.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        items = [
            ReportHistoryItem(
                id=r.id,
                report_id=r.report_id,
                business_id=r.business_id,
                report_type=r.report_type,
                title=r.title,
                reporting_period=r.reporting_period,
                format=r.format,
                status=r.status,
                file_size_bytes=r.file_size_bytes,
                download_count=r.download_count,
                created_at=r.created_at.isoformat(),
                summary_metrics=r.summary_metrics,
                coverage_status=(r.provenance_metadata or {}).get("event_nature", "CONFIRMED_EVENT"),
            )
            for r in rows
        ]

        return ReportHistoryResponse(items=items, total=total, page=page, page_size=page_size)

    def get_report_detail(self, business_id: int, report_id_or_code: str | int) -> ReportDetailResponse:
        """Fetch single report detail enforcing strict tenant isolation."""
        q = self.db.query(BusinessReport).filter(BusinessReport.business_id == business_id)
        if isinstance(report_id_or_code, int) or (isinstance(report_id_or_code, str) and report_id_or_code.isdigit()):
            report = q.filter(BusinessReport.id == int(report_id_or_code)).first()
        else:
            report = q.filter(BusinessReport.report_id == str(report_id_or_code)).first()

        if report is None:
            raise ValueError(f"Report '{report_id_or_code}' not found or inaccessible for active business.")

        return ReportDetailResponse(
            id=report.id,
            report_id=report.report_id,
            business_id=report.business_id,
            report_type=report.report_type,
            title=report.title,
            reporting_period=report.reporting_period,
            start_date=report.start_date.isoformat() if report.start_date else None,
            end_date=report.end_date.isoformat() if report.end_date else None,
            format=report.format,
            status=report.status,
            file_size_bytes=report.file_size_bytes,
            mime_type=report.mime_type,
            checksum_sha256=report.checksum_sha256,
            download_count=report.download_count,
            parameters=report.parameters,
            summary_metrics=report.summary_metrics,
            provenance_metadata=report.provenance_metadata,
            error_message=report.error_message,
            is_archived=report.is_archived,
            created_at=report.created_at.isoformat(),
        )

    def download_report(
        self,
        business_id: int,
        user: User,
        report_id_or_code: str | int,
        client_ip: str | None = None,
    ) -> tuple[bytes, str, str]:
        """Download report bytes, increment download count, and record audit log.

        Returns:
            tuple[content_bytes, mime_type, filename]
        """
        q = self.db.query(BusinessReport).filter(
            BusinessReport.business_id == business_id,
            BusinessReport.is_archived.is_(False),
        )
        if isinstance(report_id_or_code, int) or (isinstance(report_id_or_code, str) and report_id_or_code.isdigit()):
            report = q.filter(BusinessReport.id == int(report_id_or_code)).first()
        else:
            report = q.filter(BusinessReport.report_id == str(report_id_or_code)).first()

        if report is None:
            raise ValueError(f"Report '{report_id_or_code}' not found or inaccessible for active business.")

        if not report.file_path:
            raise ValueError("Report file path is missing or report generation failed.")

        # Read binary file from secure storage
        file_bytes = self.storage.read_report_file(business_id, report.file_path)

        # Update download counters
        report.download_count += 1
        report.last_downloaded_at = datetime.now(timezone.utc)
        self.db.commit()

        # Record audit log
        audit = BusinessReportAudit(
            report_id=report.id,
            business_id=business_id,
            user_id=user.id,
            action="DOWNLOADED",
            format=report.format,
            status="SUCCESS",
            ip_address=client_ip,
            details={
                "report_id": report.report_id,
                "file_path": report.file_path,
                "download_count": report.download_count,
            },
        )
        self.db.add(audit)
        self.db.commit()

        clean_title = re.sub(r"[^a-zA-Z0-9_\-]", "_", report.title).strip("_")
        filename = f"{clean_title}_{report.report_id}.{report.format.lower()}"
        return file_bytes, report.mime_type, filename

    def archive_report(
        self,
        business_id: int,
        user: User,
        report_id_or_code: str | int,
        reason: str | None = None,
    ) -> BusinessReport:
        """Soft-delete / archive a report, preventing future downloads."""
        q = self.db.query(BusinessReport).filter(BusinessReport.business_id == business_id)
        if isinstance(report_id_or_code, int) or (isinstance(report_id_or_code, str) and report_id_or_code.isdigit()):
            report = q.filter(BusinessReport.id == int(report_id_or_code)).first()
        else:
            report = q.filter(BusinessReport.report_id == str(report_id_or_code)).first()

        if report is None:
            raise ValueError(f"Report '{report_id_or_code}' not found or inaccessible.")

        report.is_archived = True
        report.archived_at = datetime.now(timezone.utc)
        report.archived_by_user_id = user.id
        self.db.commit()

        audit = BusinessReportAudit(
            report_id=report.id,
            business_id=business_id,
            user_id=user.id,
            action="ARCHIVED",
            format=report.format,
            status="SUCCESS",
            details={"reason": reason or "User requested archival"},
        )
        self.db.add(audit)
        self.db.commit()

        return report
