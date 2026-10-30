"""Pydantic v2 schemas for the Business Digital Twin.

The schemas are deliberately split so the API contract maps 1:1 to
the wizard steps:

  * BasicSection        — wizard step 1
  * CapacitySection     — wizard step 3
  * ProductIn/Out       — wizard step 2
  * DigitalPresenceIn/Out — wizard step 4
  * CertificationIn/Out — wizard step 5
  * ExportHistoryIn/Out — wizard step 6
  * BusinessGoalIn/Out  — wizard step 7
  * BusinessChallengeIn/Out — wizard step 8
  * BusinessCreate      — POST /business  (everything optional except basics)
  * BusinessUpdate      — PUT  /business  (everything optional, partial)
  * BusinessResponse    — GET  /business  (full nested tree, with id/owner)
  * BusinessSummary     — lightweight card for listings
  * ProfileCompleteness — derived, returned alongside the business

CRUD contract
-------------

The business always belongs to exactly one user. The owner_id is
resolved from the authenticated session, not the request body. The
same Business row is returned by GET (one business per user); POST
returns 409 if a business already exists.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #

# Reusable Pydantic field constraints. The auth module uses Annotated
# the same way — keeping the style consistent.

NonEmptyStr = Annotated[str, Field(min_length=1, max_length=200)]
OptionalStr = Annotated[str, Field(max_length=200)]
OptionalLongStr = Annotated[str, Field(max_length=2000)]
UrlField = Annotated[str, Field(max_length=500)]
IsoCountry = Annotated[str, Field(min_length=2, max_length=2)]
PriorityLiteral = Literal["low", "medium", "high"]
SeverityLiteral = Literal["low", "medium", "high", "critical"]
BusinessTypeLiteral = Literal[
    "sole_proprietorship",
    "partnership",
    "llc",
    "private_limited",
    "public_limited",
    "cooperative",
    "other",
]
CurrencyCode = Annotated[str, Field(min_length=3, max_length=3)]


def _normalize_url(value: str | None) -> str | None:
    """Trim and coerce empty strings to None so optional URL fields
    don't fail validation when the user leaves them blank."""
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


# --------------------------------------------------------------------------- #
# Section 1 — Basic information
# --------------------------------------------------------------------------- #


class BasicSection(BaseModel):
    """Wizard step 1. Every business must provide these."""

    legal_name: NonEmptyStr
    trade_name: OptionalStr | None = None
    industry: NonEmptyStr
    sub_industry: OptionalStr | None = None
    business_type: BusinessTypeLiteral | None = None
    established_year: int = Field(ge=1800, le=2100)
    employee_count: int = Field(ge=0, le=10_000_000)
    annual_revenue: float = Field(ge=0)
    revenue_currency: CurrencyCode = "USD"
    description: OptionalLongStr | None = None
    country: OptionalStr | None = None
    state_region: OptionalStr | None = None
    city: OptionalStr | None = None

    @field_validator("established_year")
    @classmethod
    def _no_future_year(cls, value: int) -> int:
        if value > datetime.utcnow().year:
            raise ValueError("Established year cannot be in the future.")
        return value


# --------------------------------------------------------------------------- #
# Section 2 — Products
# --------------------------------------------------------------------------- #


class ProductBase(BaseModel):
    name: NonEmptyStr
    category: OptionalStr | None = None
    hs_code: OptionalStr | None = None
    description: Annotated[str, Field(max_length=2000)] | None = None
    unit_price: float | None = Field(default=None, ge=0)
    currency: CurrencyCode = "USD"
    monthly_volume: int | None = Field(default=None, ge=0)
    is_exported: bool = False


class ProductCreate(ProductBase):
    """Create payload — client-generated id is ignored."""


class ProductUpdate(ProductBase):
    """PUT-style product payload."""


class ProductOut(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Section 3 — Capacity
# --------------------------------------------------------------------------- #


class CapacitySection(BaseModel):
    production_capacity: Annotated[str, Field(max_length=500)] | None = None
    production_capacity_unit: Annotated[str, Field(max_length=50)] | None = None
    capacity_utilization_pct: int | None = Field(default=None, ge=0, le=100)
    monthly_production_units: int | None = Field(default=None, ge=0)


# --------------------------------------------------------------------------- #
# Section 4 — Digital presence (one-to-one)
# --------------------------------------------------------------------------- #


class DigitalPresenceBase(BaseModel):
    website_url: UrlField | None = None
    linkedin_url: UrlField | None = None
    facebook_url: UrlField | None = None
    instagram_url: UrlField | None = None
    twitter_url: UrlField | None = None
    youtube_url: UrlField | None = None
    has_ecommerce: bool = False
    ecommerce_platform: OptionalStr | None = None
    uses_digital_marketing: bool = False
    uses_cloud_systems: bool = False

    @field_validator(
        "website_url",
        "linkedin_url",
        "facebook_url",
        "instagram_url",
        "twitter_url",
        "youtube_url",
        mode="before",
    )
    @classmethod
    def _strip_urls(cls, value):
        return _normalize_url(value)


class DigitalPresenceCreate(DigitalPresenceBase):
    pass


class DigitalPresenceUpdate(DigitalPresenceBase):
    pass


class DigitalPresenceOut(DigitalPresenceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Section 5 — Certifications
# --------------------------------------------------------------------------- #


class CertificationBase(BaseModel):
    name: NonEmptyStr
    issuing_body: OptionalStr | None = None
    issued_date: date | None = None
    expiry_date: date | None = None
    certificate_number: OptionalStr | None = None

    @model_validator(mode="after")
    def _expiry_after_issue(self) -> "CertificationBase":
        if self.issued_date and self.expiry_date and self.expiry_date < self.issued_date:
            raise ValueError("Expiry date cannot be before issued date.")
        return self


class CertificationCreate(CertificationBase):
    pass


class CertificationUpdate(CertificationBase):
    pass


class CertificationOut(CertificationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Section 6 — Export history
# --------------------------------------------------------------------------- #


class ExportHistoryBase(BaseModel):
    destination_country: NonEmptyStr
    product_category: OptionalStr | None = None
    first_export_date: date | None = None
    annual_export_value: float | None = Field(default=None, ge=0)
    currency: CurrencyCode = "USD"
    iec_number: OptionalStr | None = None


class ExportHistoryCreate(ExportHistoryBase):
    pass


class ExportHistoryUpdate(ExportHistoryBase):
    pass


class ExportHistoryOut(ExportHistoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Section 7 — Business goals
# --------------------------------------------------------------------------- #


class BusinessGoalBase(BaseModel):
    title: NonEmptyStr
    description: Annotated[str, Field(max_length=2000)] | None = None
    timeframe: Annotated[str, Field(max_length=50)] | None = None
    priority: PriorityLiteral = "medium"
    target_date: date | None = None


class BusinessGoalCreate(BusinessGoalBase):
    pass


class BusinessGoalUpdate(BusinessGoalBase):
    pass


class BusinessGoalOut(BusinessGoalBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Section 8 — Business challenges
# --------------------------------------------------------------------------- #


class BusinessChallengeBase(BaseModel):
    title: NonEmptyStr
    description: Annotated[str, Field(max_length=2000)] | None = None
    severity: SeverityLiteral = "medium"
    category: OptionalStr | None = None


class BusinessChallengeCreate(BusinessChallengeBase):
    pass


class BusinessChallengeUpdate(BusinessChallengeBase):
    pass


class BusinessChallengeOut(BusinessChallengeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Aggregate payload — POST /business
# --------------------------------------------------------------------------- #


class BusinessCreate(BaseModel):
    """Full payload for the create endpoint. The wizard assembles this
    client-side from all section forms and submits it once."""

    basic: BasicSection
    capacity: CapacitySection | None = None
    products: list[ProductCreate] = Field(default_factory=list)
    digital_presence: DigitalPresenceCreate | None = None
    certifications: list[CertificationCreate] = Field(default_factory=list)
    export_history: list[ExportHistoryCreate] = Field(default_factory=list)
    goals: list[BusinessGoalCreate] = Field(default_factory=list)
    challenges: list[BusinessChallengeCreate] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Partial update — PUT /business
# --------------------------------------------------------------------------- #


class BusinessUpdate(BaseModel):
    """All fields optional so the wizard can save drafts section by
    section without forcing the user to re-submit everything."""

    basic: BasicSection | None = None
    capacity: CapacitySection | None = None
    products: list[ProductCreate] | None = None
    digital_presence: DigitalPresenceUpdate | None = None
    certifications: list[CertificationCreate] | None = None
    export_history: list[ExportHistoryCreate] | None = None
    goals: list[BusinessGoalCreate] | None = None
    challenges: list[BusinessChallengeCreate] | None = None


# --------------------------------------------------------------------------- #
# Response models
# --------------------------------------------------------------------------- #


class BusinessOut(BaseModel):
    """Full business tree. Returned by GET /business and by POST/PUT."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    legal_name: str
    trade_name: str | None
    industry: str
    sub_industry: str | None
    business_type: str | None
    established_year: int
    employee_count: int
    annual_revenue: float
    revenue_currency: str
    description: str | None
    country: str | None
    state_region: str | None
    city: str | None
    production_capacity: str | None
    production_capacity_unit: str | None
    capacity_utilization_pct: int | None
    monthly_production_units: int | None
    is_completed: bool
    created_at: datetime
    updated_at: datetime

    products: list[ProductOut] = Field(default_factory=list)
    certifications: list[CertificationOut] = Field(default_factory=list)
    digital_presence: DigitalPresenceOut | None = None
    export_history: list[ExportHistoryOut] = Field(default_factory=list)
    goals: list[BusinessGoalOut] = Field(default_factory=list)
    challenges: list[BusinessChallengeOut] = Field(default_factory=list)


class BusinessSummary(BaseModel):
    """Lightweight card for places that don't need the nested tree."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    legal_name: str
    industry: str
    country: str | None
    annual_revenue: float
    revenue_currency: str
    is_completed: bool
    updated_at: datetime


class BusinessListItem(BaseModel):
    """Sprint 23 — list-card shape returned by ``GET /business/list``.

    The profile panel lists every business the user owns with a
    'Switch' / 'Delete' affordance per row. ``BusinessSummary`` is
    too thin (no ``trade_name``, no ``city``, no ``created_at`` —
    the dashboard renders it differently) so this is a deliberate
    sibling, not a replacement.

    Fields are all present on the ``Business`` ORM model — no
    eager-load is required for the read query.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    legal_name: str
    trade_name: str | None
    industry: str
    city: str | None
    is_completed: bool
    created_at: datetime


class BusinessListResponse(BaseModel):
    """Envelope for ``GET /business/list``."""

    items: list[BusinessListItem]
    active_business_id: int | None = None
    count: int


class BusinessMinimalCreate(BaseModel):
    """Sprint 23 — minimum required fields for the inline
    'Add a business' form inside the profile panel.

    These are exactly the six required fields of the existing
    ``BasicSection`` (``legal_name``, ``industry``,
    ``established_year``, ``employee_count``, ``annual_revenue``,
    ``revenue_currency``). The remaining 7 wizard steps are filled
    out on the regular ``/business`` page after the row exists, so
    the panel form stays narrow and the wizard stays the source of
    truth for the full business profile.
    """

    legal_name: NonEmptyStr
    industry: NonEmptyStr
    established_year: int = Field(ge=1800, le=2100)
    employee_count: int = Field(ge=0, le=10_000_000)
    annual_revenue: float = Field(ge=0)
    revenue_currency: CurrencyCode = "USD"

    @field_validator("established_year")
    @classmethod
    def _no_future_year(cls, value: int) -> int:
        """Mirror the wizard's BasicSection year rule."""
        if value > datetime.utcnow().year:
            raise ValueError("Established year cannot be in the future.")
        return value


# --------------------------------------------------------------------------- #
# Profile completeness
# --------------------------------------------------------------------------- #


class CompletenessMissingField(BaseModel):
    """One specific field that is missing or invalid. ``section`` maps
    1:1 to a wizard step so the UI can deep-link the user straight
    back to the right form."""

    section: Literal[
        "basic",
        "products",
        "capacity",
        "digital_presence",
        "compliance",
        "export_history",
        "goals",
        "challenges",
    ]
    field: str
    label: str


class ProfileCompleteness(BaseModel):
    """Profile completeness score + the list of missing fields. Score
    is an integer 0..100 — we use a 17-point rubric so 6% per
    field, but the rubric is generated by the service."""

    score: int = Field(ge=0, le=100)
    completed: bool
    total_fields: int
    completed_fields: int
    missing: list[CompletenessMissingField] = Field(default_factory=list)


class BusinessWithCompleteness(BaseModel):
    """Returned by GET /business alongside the business tree."""

    business: BusinessOut
    completeness: ProfileCompleteness
    meta: "BusinessMeta"


class BusinessMeta(BaseModel):
    """Lightweight sidecar returned with every Business payload.

    Designed for UI cards (completion bar, "last edited" copy) and
    cheap polling. None of these values are expensive to compute,
    so we always include them rather than gating them on a query
    param.
    """

    profile_completion: int = Field(ge=0, le=100)
    profile_status: Literal["draft", "in_progress", "complete"] = "draft"
    last_updated: datetime


# --------------------------------------------------------------------------- #
# Generic messages
# --------------------------------------------------------------------------- #


class DeleteResponse(BaseModel):
    detail: str = "Business profile deleted."
    id: int


# Suppress unused-import warnings for EmailStr (kept for forward
# compatibility with future contact fields).
_ = EmailStr
