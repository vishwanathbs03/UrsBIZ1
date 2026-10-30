"""PDF Report Generator Service — Sprint 13.2.

Uses ReportLab to build professional PDF reports:
  * Executive Report
  * Business Health Report

Features:
  * Header & Branding
  * Executive Summary
  * Health & Readiness Metrics Table
  * Business DNA & SWOT Analysis
  * Prioritized Recommendations Table
  * Clean Footer
"""

from __future__ import annotations

import io
import sys
import types
from datetime import datetime, timezone

# Ensure reportlab import compatibility
if r"C:\Users\Win\AppData\Roaming\Python\Python314\site-packages" not in sys.path:
    sys.path.append(r"C:\Users\Win\AppData\Roaming\Python\Python314\site-packages")

try:
    import PIL.Image  # noqa: F401
except Exception:
    pil_mod = types.ModuleType("PIL")
    pil_img = types.ModuleType("PIL.Image")
    pil_mod.Image = pil_img
    sys.modules["PIL"] = pil_mod
    sys.modules["PIL.Image"] = pil_img

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.business import Business
from app.repositories.business_repository import BusinessNotFound, BusinessRepository
from app.services.report_service import ReportService


class PdfReportService:
    """Service layer for PDF Report Generation (Sprint 13.2)."""

    def __init__(self, repo: BusinessRepository) -> None:
        self._repo = repo
        self._report_service = ReportService(repo)

    def generate_pdf_report(self, business: Business, report_type: str = "executive") -> bytes:
        """Generate PDF report bytes for a given business instance using ReportLab."""
        unified = self._report_service.generate_unified_report(business)
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
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#0F172A"),
            fontName="Helvetica-Bold",
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#64748B"),
        )
        section_style = ParagraphStyle(
            "SectionHeader",
            parent=styles["Heading2"],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#1E293B"),
            fontName="Helvetica-Bold",
            spaceBefore=12,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "BodyTextCustom",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#334155"),
        )
        table_header_style = ParagraphStyle(
            "TableHeader",
            parent=styles["Normal"],
            fontSize=9,
            leading=11,
            fontName="Helvetica-Bold",
            textColor=colors.white,
        )
        table_cell_style = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#1E293B"),
        )

        story = []

        # 1. Header & Branding
        exec_s = unified.executive_summary
        doc_label = "EXECUTIVE BUSINESS PERFORMANCE REPORT" if report_type == "executive" else "BUSINESS HEALTH & DIAGNOSTIC REPORT"
        story.append(Paragraph(doc_label, subtitle_style))
        story.append(Paragraph(exec_s.business_name, title_style))
        story.append(Spacer(1, 4))
        story.append(
            Paragraph(
                f"Industry: {exec_s.industry} | Date: {datetime.now(tz=timezone.utc).strftime('%B %d, %Y')}",
                subtitle_style,
            )
        )
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563EB"), spaceAfter=12))

        # 2. Executive Summary Block
        story.append(Paragraph("Executive Summary", section_style))
        story.append(Paragraph(exec_s.summary_text, body_style))
        story.append(Spacer(1, 12))

        # 3. Health & Readiness Summary Table
        story.append(Paragraph("Core Diagnostics & Scores", section_style))
        metrics_data = [
            [
                Paragraph("Metric / Indicator", table_header_style),
                Paragraph("Score / Level", table_header_style),
                Paragraph("Grade / Classification", table_header_style),
            ],
            [
                Paragraph("Business Health Score", table_cell_style),
                Paragraph(f"{exec_s.overall_health_score}/100", table_cell_style),
                Paragraph(f"Grade {exec_s.health_grade} ({exec_s.health_status})", table_cell_style),
            ],
            [
                Paragraph("Business Readiness Score", table_cell_style),
                Paragraph(f"{unified.readiness.overall_score}/100", table_cell_style),
                Paragraph(f"Grade {unified.readiness.grade}", table_cell_style),
            ],
            [
                Paragraph("Digital Maturity", table_cell_style),
                Paragraph(unified.business_dna.digital_maturity, table_cell_style),
                Paragraph(unified.business_dna.business_stage, table_cell_style),
            ],
            [
                Paragraph("Risk Profile", table_cell_style),
                Paragraph(unified.business_dna.risk_profile, table_cell_style),
                Paragraph(unified.business_dna.growth_potential, table_cell_style),
            ],
        ]
        metrics_table = Table(metrics_data, colWidths=[200, 160, 180])
        metrics_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(metrics_table)
        story.append(Spacer(1, 14))

        # 4. Prioritized Recommendations Table
        story.append(Paragraph("Prioritized Strategic Recommendations", section_style))
        recs_data = [
            [
                Paragraph("Title & Description", table_header_style),
                Paragraph("Category", table_header_style),
                Paragraph("Priority", table_header_style),
                Paragraph("Score", table_header_style),
            ]
        ]

        for r in unified.recommendations.recommendations[:6]:
            desc_para = Paragraph(f"<b>{r.title}</b><br/>{r.description}", table_cell_style)
            recs_data.append(
                [
                    desc_para,
                    Paragraph(r.category.capitalize(), table_cell_style),
                    Paragraph(r.priority, table_cell_style),
                    Paragraph(f"{r.priority_score}/100", table_cell_style),
                ]
            )

        recs_table = Table(recs_data, colWidths=[280, 90, 90, 80])
        recs_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(recs_table)
        story.append(Spacer(1, 16))

        # 5. Footer & Branding
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#94A3B8"), spaceAfter=6))
        story.append(
            Paragraph(
                "Generated automatically by UrsBiz — Executive Business Intelligence Platform. Confidential — for the named business only.",
                ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#94A3B8"), alignment=1),
            )
        )

        doc.build(story)
        return buffer.getvalue()

    def compute_pdf(self, owner_id: int, report_type: str = "executive") -> bytes:
        """Compute PDF bytes for owner_id."""
        business = self._repo.get_by_owner(owner_id)
        if business is None:
            raise BusinessNotFound("No business profile found for this user.")

        return self.generate_pdf_report(business, report_type)
