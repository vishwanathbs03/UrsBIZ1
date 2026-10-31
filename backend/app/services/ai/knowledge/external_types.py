"""SPRINT AI-16 — Verified External Knowledge + Freshness Layer.

Core type module: source authority levels, freshness status, and
the canonical claim-kind vocabulary.

Layered authority model
-----------------------

External information MUST NOT be treated as equal to internal
business evidence. We model the world in four tiers:

  * **TIER_1** — Official government / regulatory / scheme authority.
    Examples: Ministry of MSME, RBI, SEBI, FSSAI, ECHA, DGFT, BIS.
    High confidence; eligibility decisions may be based on these
    (subject to the business-evidence gate).
  * **TIER_2** — Official institutional documentation. Examples:
    Invest India, NITI Aayog, World Bank Doing Business, US Census
    Bureau. High-medium confidence.
  * **TIER_3** — Reputable secondary source. Examples: McKinsey
    reports, BCG, CII publications, established trade press.
    Medium confidence.
  * **TIER_4** — General web content. Low confidence; never
    load-bearing for any eligibility / numeric decision.

The tier becomes a 0..1 authority weight that flows into
``Claim.source_authority`` and the server confidence formula.

Freshness model
---------------

Every external source MUST carry:

  * ``source_url``        — the canonical URL
  * ``publisher``         — the organisation that published the page
  * ``retrieved_at``      — when WE pulled it
  * ``published_at``      — when the publisher last updated it
                             (may be empty for evergreen pages)
  * ``freshness_status``  — ``FRESH`` / ``AGING`` / ``STALE`` /
                             ``UNKNOWN``
  * ``authority_level``   — the TIER_1..4 value above

``freshness_status`` is computed against a content-category-aware
expiry table (e.g. tax rules expire in 12 months, statutory interest
rates in 6 months, encyclopedia definitions in 36+ months).

Claim-kind vocabulary
---------------------

The brief mandates six mutually exclusive kinds, replacing the
legacy 7-bucket taxonomy with an explicit business / external split:

  * **INTERNAL_BUSINESS** — drawn from the user's profile / kpi /
    analytics. Highest authority (1.0).
  * **CALCULATED**        — derived from internal data via a known
    formula. Authority = min(input authorities).
  * **EXTERNAL_FACT**     — drawn from a verified external source.
    Authority = tier weight × freshness weight.
  * **SCENARIO**          — illustrative what-if; assumptions must
    be declared. Authority demoted to ≤ 0.7.
  * **ASSUMPTION**        — unverified premise the answer leans on.
    Low authority (≤ 0.5).
  * **UNKNOWN**           — gap. Authority = 0.

External information NEVER silently overwrites internal business
evidence. The claim-kind is the gate the audit trail walks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# --------------------------------------------------------------------------- #
# Authority tiers
# --------------------------------------------------------------------------- #


class SourceAuthority(str, Enum):
    """Authority tier for an external source.

    Ordered from highest to lowest. The numeric ``weight`` attribute
    is what ``Claim.source_authority`` is set to (further multiplied
    by a freshness factor for ``EXTERNAL_FACT`` claims).
    """

    TIER_1 = "tier_1"  # Official government / regulatory / scheme authority
    TIER_2 = "tier_2"  # Official institutional documentation
    TIER_3 = "tier_3"  # Reputable secondary source
    TIER_4 = "tier_4"  # General web content

    @property
    def weight(self) -> float:
        """0..1 base authority weight for the tier."""
        return {
            SourceAuthority.TIER_1: 0.95,
            SourceAuthority.TIER_2: 0.80,
            SourceAuthority.TIER_3: 0.55,
            SourceAuthority.TIER_4: 0.30,
        }[self]

    @property
    def label(self) -> str:
        """Human-readable label for the trust UI."""
        return {
            SourceAuthority.TIER_1: "Official authority (Tier 1)",
            SourceAuthority.TIER_2: "Official institution (Tier 2)",
            SourceAuthority.TIER_3: "Reputable secondary (Tier 3)",
            SourceAuthority.TIER_4: "General web (Tier 4)",
        }[self]


# --------------------------------------------------------------------------- #
# Freshness status
# --------------------------------------------------------------------------- #


class FreshnessStatus(str, Enum):
    """How recent the external source is, relative to its category's expiry."""

    FRESH = "fresh"        # Recent enough; no confidence penalty.
    AGING = "aging"        # Older than ideal; small confidence penalty.
    STALE = "stale"        # Past the safe window; large confidence penalty.
    UNKNOWN = "unknown"    # No published_at available; treat as low-trust.


# --------------------------------------------------------------------------- #
# Content category — drives expiry table
# --------------------------------------------------------------------------- #


class ContentCategory(str, Enum):
    """How fast a kind of external information goes stale.

    The expiry table is the canonical single source of truth for
    "how long is a piece of external information safe to cite
    without a refresh". It feeds the freshness check.
    """

    STATUTORY = "statutory"        # Tax / GST / labour law: 12 months
    REGULATORY = "regulatory"      # REACH / BIS / FSSAI: 18 months
    SCHEME = "scheme"              # Government scheme: 12 months
    FINANCIAL_RATE = "financial"   # Bank / lending rate: 6 months
    ENCYCLOPEDIC = "encyclopedic"  # Definition / concept: 36 months
    MARKET = "market"              # Market data / industry trend: 12 months
    EXPORT_REQUIREMENT = "export"  # Export certification: 18 months

    @property
    def safe_window_days(self) -> int:
        """How many days before the source should be re-verified."""
        return {
            ContentCategory.STATUTORY: 365,
            ContentCategory.REGULATORY: 547,
            ContentCategory.SCHEME: 365,
            ContentCategory.FINANCIAL_RATE: 182,
            ContentCategory.ENCYCLOPEDIC: 1095,
            ContentCategory.MARKET: 365,
            ContentCategory.EXPORT_REQUIREMENT: 547,
        }[self]


# --------------------------------------------------------------------------- #
# External source record
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ExternalSource:
    """One verified external source.

    Carries everything the brief requires:

      * ``source_url``       — the canonical URL
      * ``publisher``        — the publishing organisation
      * ``retrieved_at``     — when WE pulled it (ISO-8601)
      * ``published_at``     — when the publisher last updated it
                               (may be empty for evergreen pages)
      * ``freshness_status`` — ``FRESH`` / ``AGING`` / ``STALE`` /
                               ``UNKNOWN``
      * ``authority_level``  — the TIER_1..4 value
      * ``category``         — what kind of information this is
      * ``content_excerpt``  — the literal text we are citing
                               (kept short for audit)
      * ``title``            — page / document title
    """

    source_url: str
    publisher: str
    retrieved_at: str
    authority_level: SourceAuthority
    category: ContentCategory
    title: str = ""
    content_excerpt: str = ""
    published_at: str = ""

    @property
    def freshness_status(self) -> FreshnessStatus:
        """Computed against the content-category safe window.

        Frozen dataclass → no @property caching; the value is
        cheap to compute (two ``datetime`` parses and a compare)
        and called rarely (per-source, not per-claim).
        """
        if not self.published_at:
            return FreshnessStatus.UNKNOWN
        try:
            pub = _parse_iso(self.published_at)
            ret = _parse_iso(self.retrieved_at)
        except (ValueError, TypeError):
            return FreshnessStatus.UNKNOWN
        age_days = (ret - pub).days
        safe = self.category.safe_window_days
        if age_days < 0:
            # Published-after-retrieved ⇒ treat as suspicious /
            # publisher-side metadata error. Mark aging so the UI
            # surfaces "verify manually".
            return FreshnessStatus.AGING
        if age_days <= safe:
            return FreshnessStatus.FRESH
        if age_days <= safe * 2:
            return FreshnessStatus.AGING
        return FreshnessStatus.STALE

    @property
    def freshness_penalty(self) -> float:
        """0..1 multiplier that lowers ``EXTERNAL_FACT`` authority.

        The model is: a STALE source retains 50% of its tier
        authority (the brief mandates that "stale information must
        reduce confidence", not zero out the claim). An AGING
        source retains 80%. UNKNOWN retains 60% (we know the page
        exists; we just don't know when it was last updated).
        """
        return {
            FreshnessStatus.FRESH: 1.0,
            FreshnessStatus.AGING: 0.8,
            FreshnessStatus.STALE: 0.5,
            FreshnessStatus.UNKNOWN: 0.6,
        }[self.freshness_status]

    @property
    def effective_authority(self) -> float:
        """The authority weight the freshness penalty already
        applied. Used as ``Claim.source_authority`` for
        ``EXTERNAL_FACT`` claims."""
        return round(self.authority_level.weight * self.freshness_penalty, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_url": self.source_url,
            "publisher": self.publisher,
            "retrieved_at": self.retrieved_at,
            "published_at": self.published_at,
            "authority_level": self.authority_level.value,
            "category": self.category.value,
            "freshness_status": self.freshness_status.value,
            "freshness_penalty": self.freshness_penalty,
            "effective_authority": self.effective_authority,
            "title": self.title,
            "content_excerpt": self.content_excerpt,
        }


# --------------------------------------------------------------------------- #
# Claim kind vocabulary
# --------------------------------------------------------------------------- #


class ClaimKind(str, Enum):
    """The brief's mandated six-way claim classification.

    These are the values ``Claim.claim_type`` may take AFTER the
    AI-16 classifier runs. The legacy 7-bucket vocabulary (FACT,
    CALCULATION, INFERENCE, RECOMMENDATION, SCENARIO, EXTERNAL_FACT,
    UNKNOWN) is preserved for backward compat in
    :data:`COMPAT_LEGACY_KINDS`; the AI-16 classifier maps legacy
    labels to the new vocabulary as a safety net.
    """

    INTERNAL_BUSINESS = "internal_business"
    CALCULATED = "calculated"
    EXTERNAL_FACT = "external_fact"
    SCENARIO = "scenario"
    ASSUMPTION = "assumption"
    UNKNOWN = "unknown"

    @property
    def default_authority(self) -> float:
        """Default authority weight the kind carries."""
        return {
            ClaimKind.INTERNAL_BUSINESS: 1.0,
            ClaimKind.CALCULATED: 0.9,
            ClaimKind.EXTERNAL_FACT: 0.65,  # overridden per-source
            ClaimKind.SCENARIO: 0.55,       # brief caps at ≤ 0.7
            ClaimKind.ASSUMPTION: 0.4,      # brief caps at ≤ 0.5
            ClaimKind.UNKNOWN: 0.0,
        }[self]


# Legacy claim_type labels still emitted by the LLM. Kept so the
# claim-kind classifier can map them to the new vocabulary without
# breaking wire compatibility.
COMPAT_LEGACY_KINDS: tuple[str, ...] = (
    "FACT",
    "CALCULATION",
    "INFERENCE",
    "RECOMMENDATION",
    "SCENARIO",
    "EXTERNAL_FACT",
    "UNKNOWN",
)


# --------------------------------------------------------------------------- #
# Parsed claim (one classified atomic assertion)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ClassifiedClaim:
    """One classified atomic claim, with provenance + authority.

    The reasoning pipeline emits a tuple of these per answer. The
    ``MixedQuestionSeparator`` and ``ExternalQuestionHandler`` use
    the kind to decide whether to render business evidence or
    external sources — keeping the two streams strictly separate.
    """

    text: str
    kind: ClaimKind
    source: ExternalSource | None = None
    authority: float = 0.0
    is_verified: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "kind": self.kind.value,
            "authority": self.authority,
            "is_verified": self.is_verified,
            "notes": self.notes,
            "source": self.source.to_dict() if self.source else None,
        }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _parse_iso(value: str) -> datetime:
    """Parse a permissive ISO-8601 string into a UTC ``datetime``."""
    s = (value or "").strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def now_iso() -> str:
    """Current UTC time in ISO-8601 form (Z-suffixed)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
