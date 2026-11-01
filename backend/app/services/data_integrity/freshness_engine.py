"""Source-Specific Data Freshness Engine (Phase 5 Data Integrity).

Enforces distinct, domain-appropriate freshness policies across 7 core modules:
  - Sales Transactions: 30d fresh / 90d stale / >90d expired
  - Customer Analytics: 45d fresh / 120d stale / >120d expired
  - Product Analytics: 45d fresh / 120d stale / >120d expired
  - Business Profile: 180d fresh / 365d stale / >365d expired
  - Financial Indicators: 90d fresh / 180d stale / >180d expired
  - Demand Forecasts: 14d fresh / 45d stale / >45d expired
  - Government Schemes: 60d fresh / 180d stale / >180d expired
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Optional

from app.schemas.data_provenance import (
    FreshnessStatus,
    ModuleDomain,
    SourceFreshnessRule,
)

logger = logging.getLogger("ursbiz.data_freshness")


DEFAULT_FRESHNESS_POLICIES: dict[ModuleDomain, SourceFreshnessRule] = {
    ModuleDomain.SALES: SourceFreshnessRule(
        module=ModuleDomain.SALES,
        fresh_threshold_days=30,
        stale_threshold_days=90,
        description="Daily/weekly sales turnover and invoice ledger updates.",
    ),
    ModuleDomain.CUSTOMERS: SourceFreshnessRule(
        module=ModuleDomain.CUSTOMERS,
        fresh_threshold_days=45,
        stale_threshold_days=120,
        description="B2B client repeat ordering and account purchasing cadence.",
    ),
    ModuleDomain.PRODUCTS: SourceFreshnessRule(
        module=ModuleDomain.PRODUCTS,
        fresh_threshold_days=45,
        stale_threshold_days=120,
        description="SKU movement velocity and top-seller volume rankings.",
    ),
    ModuleDomain.BUSINESS_PROFILE: SourceFreshnessRule(
        module=ModuleDomain.BUSINESS_PROFILE,
        fresh_threshold_days=180,
        stale_threshold_days=365,
        description="Semi-annual business profile and digital presence audit.",
    ),
    ModuleDomain.FINANCIAL_INDICATORS: SourceFreshnessRule(
        module=ModuleDomain.FINANCIAL_INDICATORS,
        fresh_threshold_days=90,
        stale_threshold_days=180,
        description="Quarterly financial statements and GST return filing cycle.",
    ),
    ModuleDomain.DEMAND_FORECAST: SourceFreshnessRule(
        module=ModuleDomain.DEMAND_FORECAST,
        fresh_threshold_days=14,
        stale_threshold_days=45,
        description="Bi-weekly Phase 4 statistical demand model re-estimation.",
    ),
    ModuleDomain.GOVERNMENT_SCHEMES: SourceFreshnessRule(
        module=ModuleDomain.GOVERNMENT_SCHEMES,
        fresh_threshold_days=60,
        stale_threshold_days=180,
        description="Quarterly/semi-annual official ministry scheme updates.",
    ),
    ModuleDomain.HEALTH_SCORE: SourceFreshnessRule(
        module=ModuleDomain.HEALTH_SCORE,
        fresh_threshold_days=30,
        stale_threshold_days=90,
        description="Monthly multi-facet business health score recalculation.",
    ),
}

# Reconciled Operational Freshness Policies (Phase 5 Final Engineering Verification):
# Explicit thresholds: Sales: 7d fresh / 30d stale; Forecast: 14d fresh / 45d stale;
# Profile: 90d fresh / 180d stale; Recommendation evidence: 30d fresh / 90d stale.
STRICT_FRESHNESS_POLICIES: dict[ModuleDomain, SourceFreshnessRule] = {
    ModuleDomain.SALES: SourceFreshnessRule(
        module=ModuleDomain.SALES,
        fresh_threshold_days=7,
        stale_threshold_days=30,
        description="High-velocity sales transactions: fresh within 7 days, stale if >30 days.",
    ),
    ModuleDomain.CUSTOMERS: SourceFreshnessRule(
        module=ModuleDomain.CUSTOMERS,
        fresh_threshold_days=30,
        stale_threshold_days=90,
        description="Customer purchase frequency and churn monitoring.",
    ),
    ModuleDomain.PRODUCTS: SourceFreshnessRule(
        module=ModuleDomain.PRODUCTS,
        fresh_threshold_days=30,
        stale_threshold_days=90,
        description="Product sales velocity and portfolio distribution.",
    ),
    ModuleDomain.BUSINESS_PROFILE: SourceFreshnessRule(
        module=ModuleDomain.BUSINESS_PROFILE,
        fresh_threshold_days=90,
        stale_threshold_days=180,
        description="Quarterly business profile, GSTIN, and digital readiness audit.",
    ),
    ModuleDomain.FINANCIAL_INDICATORS: SourceFreshnessRule(
        module=ModuleDomain.FINANCIAL_INDICATORS,
        fresh_threshold_days=60,
        stale_threshold_days=120,
        description="Bi-monthly financial metrics and working capital ledger.",
    ),
    ModuleDomain.DEMAND_FORECAST: SourceFreshnessRule(
        module=ModuleDomain.DEMAND_FORECAST,
        fresh_threshold_days=14,
        stale_threshold_days=45,
        description="Bi-weekly Phase 4 statistical demand forecast re-estimation.",
    ),
    ModuleDomain.GOVERNMENT_SCHEMES: SourceFreshnessRule(
        module=ModuleDomain.GOVERNMENT_SCHEMES,
        fresh_threshold_days=60,
        stale_threshold_days=180,
        description="Quarterly government scheme eligibility and portal verification.",
    ),
    ModuleDomain.HEALTH_SCORE: SourceFreshnessRule(
        module=ModuleDomain.HEALTH_SCORE,
        fresh_threshold_days=30,
        stale_threshold_days=90,
        description="Monthly health score and operational completeness evaluation.",
    ),
}


class DataFreshnessEngine:
    """Evaluates business data freshness against domain-specific policies."""

    def __init__(
        self,
        policies: Optional[dict[ModuleDomain, SourceFreshnessRule]] = None,
    ) -> None:
        self.policies = policies or DEFAULT_FRESHNESS_POLICIES

    def evaluate_freshness(
        self,
        module: ModuleDomain,
        as_of_timestamp: Optional[datetime | str],
        reference_time: Optional[datetime] = None,
    ) -> tuple[FreshnessStatus, int, str]:
        """Determine freshness status, age in days, and reasoning.
        
        Returns:
            (FreshnessStatus, age_days, explanation)
        """
        now = reference_time or datetime.now(timezone.utc)
        rule = self.policies.get(module) or self.policies[ModuleDomain.SALES]

        if not as_of_timestamp:
            return (
                FreshnessStatus.EXPIRED_OR_UNAVAILABLE,
                9999,
                f"No recorded timestamp available for {module.value}. Data upload required.",
            )

        if isinstance(as_of_timestamp, str):
            try:
                # Handle ISO timestamps with or without timezone
                clean_ts = as_of_timestamp.replace("Z", "+00:00")
                as_of_dt = datetime.fromisoformat(clean_ts)
            except Exception:
                try:
                    as_of_dt = datetime.strptime(as_of_timestamp[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except Exception:
                    return (
                        FreshnessStatus.EXPIRED_OR_UNAVAILABLE,
                        9999,
                        f"Unparseable timestamp '{as_of_timestamp}' for {module.value}.",
                    )
        else:
            as_of_dt = as_of_timestamp

        if as_of_dt.tzinfo is None:
            as_of_dt = as_of_dt.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        diff = now - as_of_dt
        age_days = max(0, diff.days)

        if age_days <= rule.fresh_threshold_days:
            return (
                FreshnessStatus.FRESH,
                age_days,
                f"Data is current ({age_days}d old, threshold <= {rule.fresh_threshold_days}d).",
            )
        elif age_days <= rule.stale_threshold_days:
            return (
                FreshnessStatus.POTENTIALLY_STALE,
                age_days,
                f"Data is potentially stale ({age_days}d old, exceeded fresh threshold of {rule.fresh_threshold_days}d).",
            )
        else:
            return (
                FreshnessStatus.EXPIRED_OR_UNAVAILABLE,
                age_days,
                f"Data is expired ({age_days}d old, exceeded stale limit of {rule.stale_threshold_days}d). Active update required.",
            )

    def generate_freshness_disclaimer(
        self,
        module: ModuleDomain,
        status: FreshnessStatus,
        age_days: int,
        latest_date_str: Optional[str] = None,
    ) -> Optional[str]:
        """Generate human-readable AI disclaimer when data is stale or expired."""
        if status == FreshnessStatus.FRESH:
            return None

        date_suffix = f" on {latest_date_str}" if latest_date_str else ""

        if status == FreshnessStatus.POTENTIALLY_STALE:
            return (
                f"Temporal Caution: {module.value.replace('_', ' ').title()} records were last updated {age_days} days ago{date_suffix}. "
                f"Insights reflect conditions at that time and should be confirmed before new operational commitments."
            )
        else:
            return (
                f"Stale Data Notice: {module.value.replace('_', ' ').title()} records are more than {age_days} days old{date_suffix}. "
                f"Fresh ledger upload is required to unlock real-time recommendations."
            )
