"""Pydantic schemas for Sprint 16 Government Schemes Engine.

Sprint H6.3 — adds the trust fields the user-visible surfaces need to
show sourced evidence alongside the matching score:

  * official_authority  - the named authority (e.g. SIDBI / KVIC)
  * official_source_url - the official page used to verify this entry
  * last_verified       - ISO date the entry was last cross-checked
  * verified_status     - "verified" / "unverified"
  * match_basis         - human-readable basis for the match score
  * notes               - caveats specific to this scheme

The envelope also gets a top-level `disclaimer` so every surface that
renders schemes can show the same text without re-implementing it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SchemeItem(BaseModel):
    """A government scheme recommendation item.

    `eligibility_status` values (Sprint H6.3):
      * "matching"     - business profile matches the official scheme band
      * "partialMatch" - one of industry or turnover matches
      * "outsideBand"  - business profile sits outside the band
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str
    category: str
    eligibility_status: str = Field(..., description="matching, partialMatch, outsideBand")
    eligibility_reason: str
    matching_score: int = Field(..., ge=0, le=100)
    priority: str = Field(..., description="High, Medium, Low")
    benefits: list[str] = Field(default_factory=list)
    documents_required: list[str] = Field(default_factory=list)
    application_steps: list[str] = Field(default_factory=list)
    application_link: str
    target_industries: list[str] = Field(default_factory=list)
    max_turnover: float | None = None
    min_turnover: float | None = None
    official_authority: str
    official_source_url: str
    last_verified: str
    verified_status: str = Field(..., description="verified, unverified")
    match_basis: str
    notes: str | None = None


class CategorizedSchemes(BaseModel):
    """Categorized government scheme lists.

    All four buckets are populated; the ranker decides which bucket a
    scheme lands in. Frontend surfaces should treat every bucket as
    "a similarity read", not as a decision of eligibility.
    """

    model_config = ConfigDict(extra="forbid")

    recommended: list[SchemeItem] = Field(default_factory=list)
    eligible: list[SchemeItem] = Field(default_factory=list)
    partially_eligible: list[SchemeItem] = Field(default_factory=list)
    not_eligible: list[SchemeItem] = Field(default_factory=list)


class BusinessSchemesResponse(BaseModel):
    """Response envelope for GET /api/v1/business/schemes."""

    model_config = ConfigDict(extra="forbid")

    generated_at: str
    total_schemes: int
    schemes: CategorizedSchemes
    disclaimer: str = Field(
        ...,
        description="Sprint H6.3 Part 3 disclaimer every UI surface must render.",
    )
