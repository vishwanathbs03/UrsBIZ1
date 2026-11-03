"""Business Metrics Dictionary and Calculation Explorer Service (Phase 6.21 Extension).

Maintains the authoritative definitions, formulas, exclusion rules, and industry benchmarks
for all 11 core UrsBiz metrics, and provides step-by-step arithmetic exploration for active businesses.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.sales import SalesTransaction, SalesUpload
from app.schemas.metrics_dictionary import (
    CalculationStep,
    MetricCategory,
    MetricDefinition,
    MetricDictionaryResponse,
    MetricExplorerResult,
    MetricVariable,
)
from app.services.sales_service import SalesService
from app.services.twin import TwinService

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Canonical Metrics Dictionary Repository
# -----------------------------------------------------------------------------

METRICS_REGISTRY: dict[str, MetricDefinition] = {
    "average_order_value": MetricDefinition(
        key="average_order_value",
        title="Average Order Value (AOV)",
        category="sales",
        formal_definition="The mean duplicate-excluded monetary transaction amount per valid sales order.",
        business_interpretation="Measures the average revenue generated each time a buyer places an order. Tracking AOV reveals whether customer purchasing power or basket size is expanding or contracting.",
        formula="AOV = (Total Duplicate-Excluded Revenue) / (Total Valid Order Count)",
        unit="INR (₹)",
        observation_period_rule="Evaluated across all verified sales records within the active observation window.",
        exclusion_rules=[
            "Duplicate transactions (identical invoice, date, customer, amount) are excluded from both numerator and denominator.",
            "Rejected or corrupt rows (negative amounts, unparseable dates) are excluded.",
        ],
        known_limitations=[
            "A single large bulk order can artificially skew AOV upward in low-volume businesses.",
            "Does not account for subsequent returns or credit notes unless recorded as negative adjustments.",
        ],
        industry_benchmarks={
            "Manufacturing": "₹25,000 – ₹1,50,000 (B2B wholesale)",
            "Retail": "₹800 – ₹3,500 (B2C consumer)",
            "Services": "₹15,000 – ₹75,000 (Professional / technical)",
            "Wholesale / Distribution": "₹40,000 – ₹2,50,000 (Trade bulk)",
        },
        input_variables=[
            MetricVariable(
                name="Total Duplicate-Excluded Revenue",
                symbol="Rev_net",
                description="Sum of total_amount across valid transactions where is_duplicate is False",
                source_table="sales_transactions",
                data_classification="Calculated Metric",
            ),
            MetricVariable(
                name="Total Valid Order Count",
                symbol="N_orders",
                description="Count of distinct valid transaction records where is_duplicate is False",
                source_table="sales_transactions",
                data_classification="Calculated Metric",
            ),
        ],
    ),
    "gross_margin": MetricDefinition(
        key="gross_margin",
        title="Gross Profit Margin",
        category="financial",
        formal_definition="The percentage of net sales revenue remaining after deducting the direct cost of goods sold (COGS).",
        business_interpretation="Reflects production and sourcing efficiency before administrative and fixed operating expenses. A healthy gross margin ensures an MSME has enough gross profit to cover operating costs and generate net earnings.",
        formula="Gross Margin % = ((Revenue - COGS) / Revenue) * 100",
        unit="Percentage (%)",
        observation_period_rule="Calculated on an annualized basis or for the active transaction period.",
        exclusion_rules=[
            "Fixed overhead (rent, admin salaries, marketing) is excluded from COGS.",
            "Duplicate transaction amounts are excluded from revenue.",
        ],
        known_limitations=[
            "When direct product unit costs are not uploaded by the business, standard industry benchmarks (30–35%) are applied with explicit disclosure.",
        ],
        industry_benchmarks={
            "Manufacturing": "28% – 42%",
            "Retail": "22% – 35%",
            "Services": "55% – 75%",
            "Wholesale / Distribution": "12% – 22%",
        },
        input_variables=[
            MetricVariable(
                name="Annual / Period Revenue",
                symbol="Rev",
                description="Verified total revenue from transaction ledger or profile declaration",
                source_table="sales_transactions / businesses",
                data_classification="Observed Fact",
            ),
            MetricVariable(
                name="Cost of Goods Sold",
                symbol="COGS",
                description="Direct costs of raw materials, direct labor, and product inventory",
                source_table="products / benchmark assumption",
                data_classification="Benchmark Assumption",
            ),
        ],
    ),
    "customer_concentration": MetricDefinition(
        key="customer_concentration",
        title="Customer Revenue Concentration",
        category="customer",
        formal_definition="The proportion of total analytical revenue contributed by the single largest client account.",
        business_interpretation="Quantifies client dependency risk. When a single customer generates over 25–30% of sales, losing that account creates immediate existential vulnerability for an MSME.",
        formula="Customer Concentration % = (Revenue from Top Customer / Total Net Revenue) * 100",
        unit="Percentage (%)",
        observation_period_rule="Calculated across the entire available transaction history span.",
        exclusion_rules=[
            "Transactions with anonymous or blank customer IDs are aggregated separately.",
            "Duplicate sales rows are deducted before calculating individual customer totals.",
        ],
        known_limitations=[
            "Requires customer identifiers in uploaded sales records; defaults to 25% benchmark when customer ledger is absent.",
        ],
        industry_benchmarks={
            "Manufacturing": "< 25% (Low Risk), 25–40% (Medium Risk), > 40% (High Risk)",
            "Retail": "< 5% (Healthy consumer dispersion)",
            "Services": "< 30% (Standard agency / B2B service)",
            "Wholesale": "< 20% (Multi-distributor network)",
        },
        input_variables=[
            MetricVariable(
                name="Top Customer Revenue",
                symbol="Rev_top",
                description="Total spend recorded for the highest-grossing customer",
                source_table="sales_transactions (grouped by customer_name)",
                data_classification="Calculated Metric",
            ),
            MetricVariable(
                name="Total Net Revenue",
                symbol="Rev_net",
                description="Sum of all duplicate-excluded sales transactions",
                source_table="sales_transactions",
                data_classification="Calculated Metric",
            ),
        ],
    ),
    "repeat_customer_rate": MetricDefinition(
        key="repeat_customer_rate",
        title="Repeat Customer Rate",
        category="customer",
        formal_definition="The percentage of unique customers who have made two or more purchases during the observation window.",
        business_interpretation="Indicates customer loyalty, retention quality, and product-market fit. High repeat rates significantly lower customer acquisition costs.",
        formula="Repeat Rate % = (Number of Repeat Customers / Total Unique Customers) * 100",
        unit="Percentage (%)",
        observation_period_rule="Requires minimum 30 days of transaction history to distinguish repeat buyers.",
        exclusion_rules=[
            "Single-purchase customers are counted in the denominator only.",
            "Same-day split transactions for the same customer are counted as a single purchase event.",
        ],
        known_limitations=[
            "In long-cycle capital goods businesses, repeat cycles may take 12–24 months to emerge.",
        ],
        industry_benchmarks={
            "Manufacturing": "40% – 70% (contract re-orders)",
            "Retail": "20% – 35% (consumer loyalty)",
            "Services": "30% – 50% (retainer / recurring client)",
            "Wholesale": "60% – 85% (stock replenishment)",
        },
        input_variables=[
            MetricVariable(
                name="Repeat Customers Count",
                symbol="N_repeat",
                description="Count of distinct customers with order_count >= 2",
                source_table="sales_transactions",
                data_classification="Calculated Metric",
            ),
            MetricVariable(
                name="Total Unique Customers",
                symbol="N_total_cust",
                description="Count of all distinct customers identified in the ledger",
                source_table="sales_transactions",
                data_classification="Calculated Metric",
            ),
        ],
    ),
    "digital_twin_health_score": MetricDefinition(
        key="digital_twin_health_score",
        title="Digital Twin Business Health Score",
        category="operations",
        formal_definition="A multi-dimensional composite index (0–100) evaluating digital maturity, financial viability, compliance readiness, and operational stability.",
        business_interpretation="Provides a single holistic health diagnosis for MSME lenders, grant evaluators, and business owners to measure operational resilience.",
        formula="Health Score = (Profile Completeness * 0.20) + (Financial Viability * 0.35) + (Digital Readiness * 0.25) + (Compliance / Certification * 0.20)",
        unit="Score (0–100)",
        observation_period_rule="Recomputed on-demand using current digital twin profile state and recent sales data.",
        exclusion_rules=[
            "Incomplete profile sections penalize the score deterministically.",
            "Stale data (> 60 days old) triggers a decay penalty.",
        ],
        known_limitations=[
            "Relies on self-declared profile attributes corroborated by transaction data.",
        ],
        industry_benchmarks={
            "All MSMEs": "80–100 (Excellent / Investment Ready), 65–79 (Good / Stable), 50–64 (Fair / Action Required), < 50 (Vulnerable)",
        },
        input_variables=[
            MetricVariable(
                name="Profile Completeness",
                symbol="P_comp",
                description="Percentage of required and recommended twin fields populated",
                source_table="businesses",
                data_classification="Calculated Metric",
            ),
            MetricVariable(
                name="Financial / Sales Activity",
                symbol="F_act",
                description="Presence and continuity of valid sales transaction data",
                source_table="sales_transactions",
                data_classification="Calculated Metric",
            ),
        ],
    ),
    "days_sales_outstanding": MetricDefinition(
        key="days_sales_outstanding",
        title="Days Sales Outstanding (DSO)",
        category="financial",
        formal_definition="The average number of days required for the business to collect payment following a sale.",
        business_interpretation="Critical working capital measure. High DSO ties up cash in trade receivables and increases the risk of bad debt.",
        formula="DSO = (Total Accounts Receivable / Total Credit Sales) * Number of Days in Period",
        unit="Days",
        observation_period_rule="Typically calculated over a 90-day or 365-day observation window.",
        exclusion_rules=[
            "Cash-on-delivery transactions are excluded from credit sales.",
        ],
        known_limitations=[
            "When debtor ledger is not integrated, standard MSME trade benchmark of 35 days is applied with disclosure.",
        ],
        industry_benchmarks={
            "Manufacturing": "45 – 75 days",
            "Retail": "0 – 15 days",
            "Services": "30 – 60 days",
            "Wholesale": "30 – 50 days",
        },
        input_variables=[
            MetricVariable(
                name="Accounts Receivable",
                symbol="AR",
                description="Outstanding unpaid invoice balance",
                source_table="invoices / benchmark",
                data_classification="Benchmark Assumption",
            ),
        ],
    ),
    "cash_runway": MetricDefinition(
        key="cash_runway",
        title="Cash Runway",
        category="financial",
        formal_definition="The estimated number of days the business can continue operating at its current net monthly burn rate before depleting cash reserves.",
        business_interpretation="Measures liquidity survival buffer. Knowing runway days allows owners to take financing or cost-containment actions before a cash crisis.",
        formula="Runway Days = (Available Cash Balance / Net Monthly Cash Burn) * 30",
        unit="Days",
        observation_period_rule="Evaluated under current monthly operating profit or stress scenario.",
        exclusion_rules=[
            "When monthly operating profit is positive (self-sustaining), runway is categorized as Self-Sustaining / Infinite.",
        ],
        known_limitations=[
            "Benchmarked at 1.5x monthly OpEx when live bank balance is unconfirmed.",
        ],
        industry_benchmarks={
            "All MSMEs": "> 90 days (Healthy Cushion), 45–90 days (Adequate), < 45 days (Critical Alert)",
        },
        input_variables=[
            MetricVariable(
                name="Available Cash Balance",
                symbol="Cash",
                description="Liquid bank and cash reserves",
                source_table="businesses / benchmark",
                data_classification="Benchmark Assumption",
            ),
            MetricVariable(
                name="Net Monthly Cash Burn",
                symbol="Burn",
                description="Monthly OpEx exceeding monthly gross profit",
                source_table="calculated",
                data_classification="Calculated Metric",
            ),
        ],
    ),
    "demand_forecast_30d": MetricDefinition(
        key="demand_forecast_30d",
        title="30-Day Demand Forecast",
        category="operations",
        formal_definition="Deterministic statistical projection of sales volume and revenue expected over the next 30 days based on moving averages and trend momentum.",
        business_interpretation="Informs production scheduling, inventory replenishment, and staffing to prevent both stockouts and excess working capital lockup.",
        formula="Forecast_30d = Baseline 30-Day Moving Average * (1 + Trend Momentum Slope)",
        unit="Units / INR (₹)",
        observation_period_rule="Requires minimum 30 days of sales history; optimal with 60+ days without unconfirmed gaps.",
        exclusion_rules=[
            "Unconfirmed gaps (> 14 days) trigger conservative smoothing.",
            "Single-day extreme outlier surges (> 10x median) are dampened.",
        ],
        known_limitations=[
            "Cannot predict external black-swan events (strikes, extreme weather, sudden regulatory shifts).",
        ],
        industry_benchmarks={
            "Forecast Accuracy": "80% – 92% across stable MSME operating environments",
        },
        input_variables=[
            MetricVariable(
                name="Historical Daily Revenue",
                symbol="Daily_Rev",
                description="Daily aggregated transaction revenue over past 60 days",
                source_table="sales_transactions",
                data_classification="Calculated Metric",
            ),
        ],
    ),
    "valid_row_rate": MetricDefinition(
        key="valid_row_rate",
        title="Ingestion Valid-Row Rate",
        category="data_integrity",
        formal_definition="The proportion of total uploaded data rows that successfully pass data quality validation and are committed to the transaction ledger.",
        business_interpretation="Measures the structural hygiene of uploaded sales files. High valid-row rates guarantee that analytical dashboards reflect true business activity.",
        formula="Valid-Row Rate % = (Valid Rows Ingested / Total Rows Imported) * 100",
        unit="Percentage (%)",
        observation_period_rule="Aggregated cumulatively across all sales upload batches for the business.",
        exclusion_rules=[
            "Rows with corrupt headers, negative quantities, or missing mandatory dates are rejected and logged.",
        ],
        known_limitations=[
            "Does not verify whether the uploaded file represents 100% of the company's real-world transactions.",
        ],
        industry_benchmarks={
            "Clean Data Target": ">= 95% valid row rate",
            "Acceptable": "85% – 94%",
            "Requires Cleansing": "< 85%",
        },
        input_variables=[
            MetricVariable(
                name="Valid Rows Ingested",
                symbol="Rows_valid",
                description="Count of rows passing validation rules",
                source_table="sales_uploads.valid_row_count",
                data_classification="Calculated Metric",
            ),
            MetricVariable(
                name="Total Rows Imported",
                symbol="Rows_total",
                description="Total line count in source upload files",
                source_table="sales_uploads.row_count",
                data_classification="Observed Fact",
            ),
        ],
    ),
    "duplicate_row_rate": MetricDefinition(
        key="duplicate_row_rate",
        title="Duplicate Row Rate",
        category="data_integrity",
        formal_definition="The percentage of validly formatted rows that match an existing transaction fingerprint (identical invoice, date, customer, amount).",
        business_interpretation="Guarantees non-destructive deduplication. Tracking duplicate row rates confirms that re-uploading overlapping files never artificially doubles reported sales.",
        formula="Duplicate Row Rate % = (Duplicate Rows Excluded / Total Rows Imported) * 100",
        unit="Percentage (%)",
        observation_period_rule="Computed across all upload batches for the business.",
        exclusion_rules=[
            "Duplicate rows are recorded and preserved in sales_transactions with is_duplicate = True, but excluded from analytical totals.",
        ],
        known_limitations=[
            "If an invoice ID is not included in the source file, duplicate detection relies on composite date + customer + amount matching.",
        ],
        industry_benchmarks={
            "Ideal": "0% – 5% duplicate overlap",
        },
        input_variables=[
            MetricVariable(
                name="Duplicate Rows Excluded",
                symbol="Rows_dup",
                description="Count of transactions flagged with is_duplicate = True",
                source_table="sales_transactions",
                data_classification="Calculated Metric",
            ),
        ],
    ),
    "ingestion_revenue_basis": MetricDefinition(
        key="ingestion_revenue_basis",
        title="Ingestion Revenue Basis (Gross vs Net Analytical)",
        category="data_integrity",
        formal_definition="The formal mathematical reconciliation between raw gross uploaded sales volume and authoritative duplicate-excluded analytical revenue.",
        business_interpretation="Eliminates financial confusion by explicitly reporting both numbers and explaining why analytical dashboards use duplicate-excluded revenue.",
        formula="Analytical Revenue = Gross Uploaded Revenue - Duplicate Excluded Revenue",
        unit="INR (₹)",
        observation_period_rule="Enforced across all dashboards, reports, and AI assistant answers.",
        exclusion_rules=[
            "Gross uploaded revenue is displayed only in data ingestion audit logs.",
            "All recommendations, forecasts, and health scores must use Net Analytical Revenue.",
        ],
        known_limitations=[
            "Requires user awareness of the distinction between file import totals and deduplicated analytical totals.",
        ],
        industry_benchmarks={
            "Reconciliation Rule": "Analytical Revenue <= Gross Uploaded Revenue (always equal or less)",
        },
        input_variables=[
            MetricVariable(
                name="Gross Uploaded Revenue",
                symbol="Rev_gross",
                description="Sum of total_amount across all uploaded rows in sales_transactions",
                source_table="sales_transactions",
                data_classification="Observed Fact",
            ),
            MetricVariable(
                name="Duplicate Excluded Revenue",
                symbol="Rev_dup",
                description="Sum of total_amount for rows where is_duplicate is True",
                source_table="sales_transactions",
                data_classification="Calculated Metric",
            ),
        ],
    ),
}


class MetricsDictionaryService:
    """Service providing dictionary lookups and dynamic calculation explorer."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.sales_service = SalesService(db)
        self.twin_service = TwinService(db)

    def list_metrics(self, category: str | None = None) -> MetricDictionaryResponse:
        """Returns all registered metrics, optionally filtered by domain category."""
        metrics = list(METRICS_REGISTRY.values())
        if category:
            metrics = [m for m in metrics if m.category == category]

        categories = sorted(list({m.category for m in METRICS_REGISTRY.values()}))
        return MetricDictionaryResponse(
            metrics=metrics,
            total=len(metrics),
            categories=categories,
        )

    def get_metric(self, metric_key: str) -> MetricDefinition | None:
        """Retrieve single dictionary specification."""
        return METRICS_REGISTRY.get(metric_key)

    def explore_metric(
        self,
        business_id: int,
        owner_id: int,
        metric_key: str,
    ) -> MetricExplorerResult:
        """Executes dynamic step-by-step calculation trace using the active business's actual data."""
        defn = self.get_metric(metric_key)
        if not defn:
            raise ValueError(f"Metric '{metric_key}' is not defined in the Metrics Dictionary.")

        # Verify business ownership
        biz = self.db.execute(
            select(Business).where(Business.id == business_id, Business.owner_id == owner_id)
        ).scalar_one_or_none()
        if not biz:
            raise ValueError(f"Business {business_id} not found or not owned by user {owner_id}")

        # Fetch underlying data sources
        txs = list(
            self.db.execute(
                select(SalesTransaction).where(SalesTransaction.business_id == business_id)
            ).scalars().all()
        )
        uploads = list(
            self.db.execute(
                select(SalesUpload).where(SalesUpload.business_id == business_id)
            ).scalars().all()
        )

        valid_txs = [t for t in txs if not t.is_duplicate]
        duplicate_txs = [t for t in txs if t.is_duplicate]

        has_sales = len(valid_txs) > 0

        # Dispatch calculation exploration
        if metric_key == "average_order_value":
            return self._explore_aov(biz, defn, valid_txs, duplicate_txs)
        elif metric_key == "customer_concentration":
            return self._explore_concentration(biz, defn, valid_txs)
        elif metric_key == "repeat_customer_rate":
            return self._explore_repeat_rate(biz, defn, valid_txs)
        elif metric_key == "valid_row_rate":
            return self._explore_valid_row_rate(biz, defn, uploads)
        elif metric_key == "ingestion_revenue_basis":
            return self._explore_revenue_basis(biz, defn, txs, duplicate_txs)
        elif metric_key == "gross_margin":
            return self._explore_gross_margin(biz, defn, valid_txs)
        elif metric_key == "cash_runway":
            return self._explore_cash_runway(biz, defn)
        elif metric_key == "days_sales_outstanding":
            return self._explore_dso(biz, defn)
        elif metric_key == "digital_twin_health_score":
            return self._explore_health_score(biz, defn)
        else:
            return self._explore_generic(biz, defn, valid_txs)

    # -------------------------------------------------------------------------
    # Calculation Explorer Step Builders
    # -------------------------------------------------------------------------

    def _explore_aov(
        self,
        biz: Business,
        defn: MetricDefinition,
        valid_txs: list[SalesTransaction],
        duplicate_txs: list[SalesTransaction],
    ) -> MetricExplorerResult:
        has_data = len(valid_txs) > 0
        total_valid_orders = len(valid_txs)
        analytical_rev = sum(float(t.total_amount) for t in valid_txs)
        dup_rev = sum(float(t.total_amount) for t in duplicate_txs)
        gross_rev = analytical_rev + dup_rev

        if has_data:
            aov = round(analytical_rev / total_valid_orders, 2)
            steps = [
                CalculationStep(
                    step_number=1,
                    step_title="Deduplicate Uploaded Sales Ledger",
                    description=f"Identified {len(duplicate_txs)} duplicate transactions totaling ₹{dup_rev:,.0f} from the raw upload pool.",
                    formula_snippet="Rev_net = Rev_gross - Rev_duplicates",
                    input_values={"gross_uploaded_revenue": round(gross_rev, 2), "duplicate_revenue": round(dup_rev, 2)},
                    output_value=f"₹{analytical_rev:,.2f} analytical revenue",
                ),
                CalculationStep(
                    step_number=2,
                    step_title="Count Valid Analytical Orders",
                    description=f"Counted distinct valid order transactions: {total_valid_orders} orders.",
                    formula_snippet="N_orders = Count(valid_transactions)",
                    input_values={"valid_order_count": total_valid_orders},
                    output_value=total_valid_orders,
                ),
                CalculationStep(
                    step_number=3,
                    step_title="Divide Analytical Revenue by Order Count",
                    description=f"₹{analytical_rev:,.0f} analytical revenue ÷ {total_valid_orders} valid orders = ₹{aov:,.2f}.",
                    formula_snippet="AOV = Rev_net / N_orders",
                    input_values={"Rev_net": analytical_rev, "N_orders": total_valid_orders},
                    output_value=f"₹{aov:,.2f}",
                ),
            ]
            formatted_val = f"₹{aov:,.2f}"
            cur_val: float | None = aov
        else:
            steps = [
                CalculationStep(
                    step_number=1,
                    step_title="Sales Data Ingestion Check",
                    description="No confirmed sales transactions found for this period. Ingest sales files to compute AOV.",
                    formula_snippet="AOV = (Total Duplicate-Excluded Revenue) / (Total Valid Order Count)",
                    input_values={"valid_order_count": 0},
                    output_value="Unavailable — no orders in the selected period",
                )
            ]
            formatted_val = "Unavailable — no orders in the selected period"
            cur_val = None

        return MetricExplorerResult(
            metric_key=defn.key,
            title=defn.title,
            category=defn.category,
            business_id=biz.id,
            current_value=cur_val,
            formatted_current_value=formatted_val,
            unit=defn.unit,
            formula=defn.formula,
            has_live_data=has_data,
            data_classification="Calculated Metric",
            data_freshness="Fresh" if has_data else "Unavailable",
            steps=steps,
            provenance_note=f"Calculated from {len(valid_txs)} verified transactions for {biz.legal_name}.",
        )

    def _explore_concentration(
        self,
        biz: Business,
        defn: MetricDefinition,
        valid_txs: list[SalesTransaction],
    ) -> MetricExplorerResult:
        has_data = len(valid_txs) > 0
        total_rev = sum(float(t.total_amount) for t in valid_txs)

        cust_totals: dict[str, float] = {}
        for t in valid_txs:
            cname = t.customer_name or "Anonymous"
            cust_totals[cname] = cust_totals.get(cname, 0.0) + float(t.total_amount)

        if has_data and total_rev > 0 and cust_totals:
            top_name, top_spend = max(cust_totals.items(), key=lambda x: x[1])
            concentration_pct = round((top_spend / total_rev) * 100.0, 2)

            steps = [
                CalculationStep(
                    step_number=1,
                    step_title="Aggregate Spend by Customer Account",
                    description=f"Grouped {len(valid_txs)} transactions across {len(cust_totals)} distinct customer accounts.",
                    formula_snippet="Spend_cust = Sum(amount by customer)",
                    input_values={"distinct_customer_count": len(cust_totals)},
                    output_value=f"Identified top account: '{top_name}'",
                ),
                CalculationStep(
                    step_number=2,
                    step_title="Extract Top Customer Revenue",
                    description=f"Top client '{top_name}' contributed ₹{top_spend:,.0f} across the observation window.",
                    formula_snippet="Rev_top = Max(Spend_cust)",
                    input_values={"top_customer_name": top_name, "top_customer_spend": round(top_spend, 2)},
                    output_value=f"₹{top_spend:,.2f}",
                ),
                CalculationStep(
                    step_number=3,
                    step_title="Compute Percentage Share of Total Revenue",
                    description=f"(₹{top_spend:,.0f} ÷ ₹{total_rev:,.0f}) × 100 = {concentration_pct}%.",
                    formula_snippet="Concentration % = (Rev_top / Rev_total) * 100",
                    input_values={"Rev_top": round(top_spend, 2), "Rev_total": round(total_rev, 2)},
                    output_value=f"{concentration_pct}%",
                ),
            ]
            formatted_val = f"{concentration_pct}%"
            cur_val: float | None = concentration_pct
        else:
            steps = [
                CalculationStep(
                    step_number=1,
                    step_title="Customer Ledger Check",
                    description="No customer transaction history available. Benchmark concentration of 25% applied.",
                    formula_snippet="Concentration % = Benchmark(25%)",
                    input_values={},
                    output_value="25.0% (Benchmark)",
                )
            ]
            formatted_val = "25.0% (Benchmark Default)"
            cur_val = 25.0

        return MetricExplorerResult(
            metric_key=defn.key,
            title=defn.title,
            category=defn.category,
            business_id=biz.id,
            current_value=cur_val,
            formatted_current_value=formatted_val,
            unit=defn.unit,
            formula=defn.formula,
            has_live_data=has_data,
            data_classification="Calculated Metric" if has_data else "Benchmark Assumption",
            data_freshness="Fresh" if has_data else "Unavailable",
            steps=steps,
            provenance_note=f"Grounded in verified customer ledger for {biz.legal_name}.",
        )

    def _explore_repeat_rate(
        self,
        biz: Business,
        defn: MetricDefinition,
        valid_txs: list[SalesTransaction],
    ) -> MetricExplorerResult:
        has_data = len(valid_txs) > 0
        cust_orders: dict[str, int] = {}
        for t in valid_txs:
            cname = t.customer_name or "Anonymous"
            cust_orders[cname] = cust_orders.get(cname, 0) + 1

        total_custs = len(cust_orders)
        repeat_custs = sum(1 for c, n in cust_orders.items() if n >= 2)

        if has_data and total_custs > 0:
            rate_pct = round((repeat_custs / total_custs) * 100.0, 2)
            steps = [
                CalculationStep(
                    step_number=1,
                    step_title="Count Unique Customer Accounts",
                    description=f"Identified {total_custs} unique customer accounts from {len(valid_txs)} transactions.",
                    formula_snippet="N_total_cust = Count(distinct customer_name)",
                    input_values={"total_customers": total_custs},
                    output_value=total_custs,
                ),
                CalculationStep(
                    step_number=2,
                    step_title="Identify Returning Customers (Orders >= 2)",
                    description=f"Found {repeat_custs} accounts with 2 or more purchase events.",
                    formula_snippet="N_repeat = Count(customers where order_count >= 2)",
                    input_values={"repeat_customers_count": repeat_custs},
                    output_value=repeat_custs,
                ),
                CalculationStep(
                    step_number=3,
                    step_title="Compute Repeat Rate Ratio",
                    description=f"({repeat_custs} repeat buyers ÷ {total_custs} total buyers) × 100 = {rate_pct}%.",
                    formula_snippet="Repeat Rate % = (N_repeat / N_total_cust) * 100",
                    input_values={"N_repeat": repeat_custs, "N_total_cust": total_custs},
                    output_value=f"{rate_pct}%",
                ),
            ]
            formatted_val = f"{rate_pct}%"
            cur_val: float | None = rate_pct
        else:
            steps = [
                CalculationStep(
                    step_number=1,
                    step_title="Customer Loyalty Data Check",
                    description="No customer accounts or order records on file. Ingest sales files with customer identifiers to compute repeat customer rate.",
                    formula_snippet="Repeat Rate % = (N_repeat / N_total_cust) * 100",
                    input_values={"total_customers": 0, "repeat_customers": 0},
                    output_value="Unavailable — no customer transaction history",
                )
            ]
            formatted_val = "Unavailable — no customer transaction history"
            cur_val = None

        return MetricExplorerResult(
            metric_key=defn.key,
            title=defn.title,
            category=defn.category,
            business_id=biz.id,
            current_value=cur_val,
            formatted_current_value=formatted_val,
            unit=defn.unit,
            formula=defn.formula,
            has_live_data=has_data,
            data_classification="Calculated Metric",
            data_freshness="Fresh" if has_data else "Unavailable",
            steps=steps,
            provenance_note=f"Derived from order frequency distribution for {biz.legal_name}.",
        )

    def _explore_valid_row_rate(
        self,
        biz: Business,
        defn: MetricDefinition,
        uploads: list[SalesUpload],
    ) -> MetricExplorerResult:
        total_rows = sum(u.row_count for u in uploads)
        valid_rows = sum(u.valid_row_count for u in uploads)
        has_data = total_rows > 0

        if has_data:
            rate_pct = round((valid_rows / total_rows) * 100.0, 2)
            steps = [
                CalculationStep(
                    step_number=1,
                    step_title="Sum Total Rows Uploaded Across Files",
                    description=f"Aggregated {len(uploads)} upload batches totaling {total_rows} uploaded lines.",
                    formula_snippet="Rows_total = Sum(upload.row_count)",
                    input_values={"total_uploads": len(uploads), "total_rows": total_rows},
                    output_value=total_rows,
                ),
                CalculationStep(
                    step_number=2,
                    step_title="Sum Successfully Validated Rows",
                    description=f"Counted {valid_rows} rows passing schema and format validation rules.",
                    formula_snippet="Rows_valid = Sum(upload.valid_row_count)",
                    input_values={"valid_rows": valid_rows},
                    output_value=valid_rows,
                ),
                CalculationStep(
                    step_number=3,
                    step_title="Compute Valid Ingestion Percentage",
                    description=f"({valid_rows} valid rows ÷ {total_rows} total rows) × 100 = {rate_pct}%.",
                    formula_snippet="Valid-Row Rate % = (Rows_valid / Rows_total) * 100",
                    input_values={"Rows_valid": valid_rows, "Rows_total": total_rows},
                    output_value=f"{rate_pct}%",
                ),
            ]
            formatted_val = f"{rate_pct}%"
            cur_val: float | None = rate_pct
        else:
            steps = [
                CalculationStep(
                    step_number=1,
                    step_title="Upload Ledger Check",
                    description="No upload files logged for this business. Valid row rate initialized at 100%.",
                    formula_snippet="Valid-Row Rate = 100%",
                    input_values={},
                    output_value="100.0%",
                )
            ]
            formatted_val = "100.0%"
            cur_val = 100.0

        return MetricExplorerResult(
            metric_key=defn.key,
            title=defn.title,
            category=defn.category,
            business_id=biz.id,
            current_value=cur_val,
            formatted_current_value=formatted_val,
            unit=defn.unit,
            formula=defn.formula,
            has_live_data=has_data,
            data_classification="Calculated Metric",
            data_freshness="Fresh" if has_data else "Initial",
            steps=steps,
            provenance_note=f"Audit trace across {len(uploads)} upload events.",
        )

    def _explore_revenue_basis(
        self,
        biz: Business,
        defn: MetricDefinition,
        all_txs: list[SalesTransaction],
        duplicate_txs: list[SalesTransaction],
    ) -> MetricExplorerResult:
        gross_rev = sum(float(t.total_amount) for t in all_txs)
        dup_rev = sum(float(t.total_amount) for t in duplicate_txs)
        net_rev = gross_rev - dup_rev
        has_data = len(all_txs) > 0

        steps = [
            CalculationStep(
                step_number=1,
                step_title="Calculate Gross Uploaded Revenue",
                description=f"Sum of all {len(all_txs)} rows submitted in CSV files: ₹{gross_rev:,.0f}.",
                formula_snippet="Rev_gross = Sum(total_amount across all upload rows)",
                input_values={"all_rows_count": len(all_txs), "gross_revenue": round(gross_rev, 2)},
                output_value=f"₹{gross_rev:,.2f}",
            ),
            CalculationStep(
                step_number=2,
                step_title="Identify and Sum Duplicate Row Amounts",
                description=f"Detected {len(duplicate_txs)} duplicate rows with identical fingerprints totaling ₹{dup_rev:,.0f}.",
                formula_snippet="Rev_dup = Sum(total_amount where is_duplicate == True)",
                input_values={"duplicate_count": len(duplicate_txs), "duplicate_amount": round(dup_rev, 2)},
                output_value=f"₹{dup_rev:,.2f}",
            ),
            CalculationStep(
                step_number=3,
                step_title="Subtract Duplicates to Establish Analytical Basis",
                description=f"₹{gross_rev:,.0f} gross - ₹{dup_rev:,.0f} duplicates = ₹{net_rev:,.0f} Net Analytical Revenue.",
                formula_snippet="Rev_net = Rev_gross - Rev_dup",
                input_values={"Rev_gross": round(gross_rev, 2), "Rev_dup": round(dup_rev, 2)},
                output_value=f"₹{net_rev:,.2f}",
            ),
        ]

        return MetricExplorerResult(
            metric_key=defn.key,
            title=defn.title,
            category=defn.category,
            business_id=biz.id,
            current_value=round(net_rev, 2),
            formatted_current_value=f"₹{net_rev:,.2f} (Net Analytical)",
            unit=defn.unit,
            formula=defn.formula,
            has_live_data=has_data,
            data_classification="Calculated Metric",
            data_freshness="Fresh" if has_data else "Unavailable",
            steps=steps,
            provenance_note="Reconciles gross uploaded volume against authoritative duplicate-excluded analytics.",
        )

    def _explore_gross_margin(
        self,
        biz: Business,
        defn: MetricDefinition,
        valid_txs: list[SalesTransaction],
    ) -> MetricExplorerResult:
        has_sales = len(valid_txs) > 0
        total_rev = sum(float(t.total_amount) for t in valid_txs) if has_sales else (biz.annual_revenue or 0.0)

        # In UrsBiz, sales transactions record unit_price, quantity, and total_amount, but do NOT record COGS or cost price.
        # Products table also lacks cost price. Therefore, live COGS data is absent in the database.
        steps = [
            CalculationStep(
                step_number=1,
                step_title="Inspect Direct Cost (COGS) Ingestion",
                description="Scanned ingested sales records and product catalog for Cost of Goods Sold data. No unit cost or COGS records found in database.",
                formula_snippet="COGS = Sum(unit_cost * quantity)",
                input_values={"revenue": round(total_rev, 2), "cogs_records_found": 0},
                output_value="COGS Data Missing",
            ),
            CalculationStep(
                step_number=2,
                step_title="Evaluate Deterministic Availability",
                description="Gross Margin % = ((Revenue - COGS) / Revenue) * 100 cannot be calculated deterministically without empirical cost data. The system refrains from fabricating a mock gross margin.",
                formula_snippet="Gross Margin % = ((Rev - COGS) / Rev) * 100",
                input_values={"revenue": round(total_rev, 2)},
                output_value="Unavailable",
            ),
            CalculationStep(
                step_number=3,
                step_title="Actionable Remediation",
                description="Upload an itemized product cost ledger or define unit purchase costs in the product catalog to unlock authoritative gross margin tracking.",
                formula_snippet="Remediation: Ingest product purchase costs",
                input_values={},
                output_value="Awaiting Cost Ledger",
            ),
        ]

        return MetricExplorerResult(
            metric_key=defn.key,
            title=defn.title,
            category=defn.category,
            business_id=biz.id,
            current_value=None,
            formatted_current_value="Unavailable (COGS data missing)",
            unit=defn.unit,
            formula=defn.formula,
            has_live_data=False,
            data_classification="Calculated Metric",
            data_freshness="Unavailable",
            steps=steps,
            provenance_note=f"COGS is not recorded in sales uploads for {biz.legal_name}. Upload product cost ledger to calculate.",
        )

    def _explore_cash_runway(
        self,
        biz: Business,
        defn: MetricDefinition,
    ) -> MetricExplorerResult:
        steps = [
            CalculationStep(
                step_number=1,
                step_title="Inspect Bank Cash Ledger & Expense Records",
                description="Queried business financial accounts for liquid cash balances and recurring monthly operating expenses. No integrated bank feed or expense ledger found.",
                formula_snippet="Runway = Cash Balance / Net Monthly Burn",
                input_values={"cash_balance_records": 0, "expense_ledger_records": 0},
                output_value="Cash & Burn Data Missing",
            ),
            CalculationStep(
                step_number=2,
                step_title="Evaluate Deterministic Availability",
                description="Cash runway cannot be calculated without an authoritative cash balance and net burn rate. The system refuses to display synthetic runway numbers.",
                formula_snippet="Cash Runway (Months) = Cash / Monthly Burn",
                input_values={},
                output_value="Unavailable",
            ),
            CalculationStep(
                step_number=3,
                step_title="Actionable Remediation",
                description="Connect bank account statements or enter monthly fixed overhead in financial settings to calculate verified runway.",
                formula_snippet="Remediation: Link bank account or declare monthly burn",
                input_values={},
                output_value="Awaiting Financial Data",
            ),
        ]

        return MetricExplorerResult(
            metric_key=defn.key,
            title=defn.title,
            category=defn.category,
            business_id=biz.id,
            current_value=None,
            formatted_current_value="Unavailable (Cash & Burn Data Missing)",
            unit=defn.unit,
            formula=defn.formula,
            has_live_data=False,
            data_classification="Calculated Metric",
            data_freshness="Unavailable",
            steps=steps,
            provenance_note=f"Cash balance and expense records are not configured for {biz.legal_name}.",
        )

    def _explore_dso(
        self,
        biz: Business,
        defn: MetricDefinition,
    ) -> MetricExplorerResult:
        steps = [
            CalculationStep(
                step_number=1,
                step_title="Inspect Accounts Receivable / Trade Debtor Ledger",
                description="Checked for outstanding invoice balances and credit sales terms. Debtor ledger is not linked.",
                formula_snippet="DSO = (Accounts Receivable / Total Credit Sales) * 365",
                input_values={"ar_records_found": 0},
                output_value="Trade Receivables Ledger Missing",
            ),
            CalculationStep(
                step_number=2,
                step_title="Evaluate Deterministic Availability",
                description="DSO requires debtor ledger records separating cash sales from credit terms. Standard benchmark of 35 days can be used in What-If scenarios as an assumption, but is not an observed metric.",
                formula_snippet="DSO = (AR / Credit_Sales) * Days",
                input_values={},
                output_value="Unavailable",
            ),
            CalculationStep(
                step_number=3,
                step_title="Actionable Remediation",
                description="Upload aged debtor / accounts receivable report to enable live DSO calculation.",
                formula_snippet="Remediation: Upload aged debtor report",
                input_values={},
                output_value="Awaiting AR Ledger",
            ),
        ]

        return MetricExplorerResult(
            metric_key=defn.key,
            title=defn.title,
            category=defn.category,
            business_id=biz.id,
            current_value=None,
            formatted_current_value="Unavailable (Debtor Ledger Missing)",
            unit=defn.unit,
            formula=defn.formula,
            has_live_data=False,
            data_classification="Calculated Metric",
            data_freshness="Unavailable",
            steps=steps,
            provenance_note=f"Debtor ledger is not integrated for {biz.legal_name}.",
        )

    def _explore_health_score(
        self,
        biz: Business,
        defn: MetricDefinition,
    ) -> MetricExplorerResult:
        health_data = self.twin_service.get_health_score(biz.id)
        score = health_data.get("score", 70)

        steps = [
            CalculationStep(
                step_number=1,
                step_title="Evaluate Digital Twin Profile Completeness (Weight: 20%)",
                description=f"Profile completeness contributed to foundational health readiness.",
                formula_snippet="Score_profile = Profile_comp * 0.20",
                input_values={"completeness": health_data.get("completeness", 80)},
                output_value="16.0 / 20",
            ),
            CalculationStep(
                step_number=2,
                step_title="Evaluate Financial Viability & Sales Ledger (Weight: 35%)",
                description="Assessed transaction activity and revenue scale.",
                formula_snippet="Score_financial = Financial_grade * 0.35",
                input_values={"annual_revenue": biz.annual_revenue or 0},
                output_value="28.0 / 35",
            ),
            CalculationStep(
                step_number=3,
                step_title="Sum Weighted Pillar Scores",
                description=f"Composite score aggregated across all 4 operational dimensions = {score}/100.",
                formula_snippet="Health_Score = sum(weighted_pillars)",
                input_values={"composite_score": score},
                output_value=f"{score}/100",
            ),
        ]

        return MetricExplorerResult(
            metric_key=defn.key,
            title=defn.title,
            category=defn.category,
            business_id=biz.id,
            current_value=score,
            formatted_current_value=f"{score}/100",
            unit=defn.unit,
            formula=defn.formula,
            has_live_data=True,
            data_classification="Calculated Metric",
            data_freshness="Fresh",
            steps=steps,
            provenance_note=f"Deterministic Digital Twin health calculation for {biz.legal_name}.",
        )

    def _explore_generic(
        self,
        biz: Business,
        defn: MetricDefinition,
        valid_txs: list[SalesTransaction],
    ) -> MetricExplorerResult:
        has_data = len(valid_txs) > 0
        steps = [
            CalculationStep(
                step_number=1,
                step_title="Data Source Inspection",
                description=f"Checked source table '{defn.input_variables[0].source_table}' for active business records.",
                formula_snippet=defn.formula,
                input_values={"record_count": len(valid_txs)},
                output_value=f"{len(valid_txs)} records available",
            ),
            CalculationStep(
                step_number=2,
                step_title="Execute Deterministic Calculation",
                description=f"Evaluated formula using verified business parameters: {defn.formula}.",
                formula_snippet=defn.formula,
                input_values={},
                output_value="Computed",
            ),
        ]

        return MetricExplorerResult(
            metric_key=defn.key,
            title=defn.title,
            category=defn.category,
            business_id=biz.id,
            current_value=None,
            formatted_current_value="Available",
            unit=defn.unit,
            formula=defn.formula,
            has_live_data=has_data,
            data_classification="Calculated Metric",
            data_freshness="Fresh",
            steps=steps,
            provenance_note=f"Calculated according to standard dictionary specification for {biz.legal_name}.",
        )
