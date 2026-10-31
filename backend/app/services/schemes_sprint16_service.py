"""Government Scheme Recommendation Engine — Sprint 16.

Sprint H6.3 — Government Scheme Trust Layer:
  * Each scheme now carries `official_authority`, `official_source_url`,
    and `last_verified` so user-visible surfaces can render the same
    sourced evidence and never claim authority that UrsBiz does not have.
  * Benefit numbers and percentages are now framed as the official
    rule, not as UrsBiz-issued guarantees. The wording is "the official
    rule may provide up to ..." — never "you will receive ...".
  * One scheme (the "Digital MSME Enablement Scheme") could not be
    verified to an official source and was removed; the catalog now
    surfaces the Udyam Registration scheme instead, which is the
    official Ministry of MSME entry point every other MSME scheme
    gates on.
  * Currency is expressed in INR (the official scheme currency). USD
    equivalents are not asserted because exchange rates change daily
    and the official authority prices the scheme in INR.

Ranks static deterministic MSME schemes using:
  * Industry
  * Annual Turnover
  * Employee Count
  * Location / Region
  * Business Age

Categorizes results into:
  * recommended
  * matching
  * partialMatch
  * outsideBand

Terminology (Sprint H6.3 Part 4):
  * MATCHING — a similarity score between the business profile and
    the known scheme rules. UrsBiz computes this; it is informational.
  * ELIGIBILITY — only determined by the official authority after
    reviewing the actual application. UrsBiz never asserts this.
  * APPROVAL — only the official authority grants this. UrsBiz never
    asserts this.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.business import Business
from app.repositories.business_repository import BusinessNotFound, BusinessRepository
from app.schemas.schemes_sprint16 import (
    BusinessSchemesResponse,
    CategorizedSchemes,
    SchemeItem,
)

# Date the catalog was last cross-checked against the named official
# source URL. The verifier asserts the format; the date is updated when
# the human editor reviews the catalog against the official page.
LAST_VERIFIED = "2026-08-03"

# Static Deterministic Government Schemes Dataset
#
# Verification status legend:
#   "verified"   - official page reachable, scheme name + benefit
#                  wording cross-checked.
#   "unverified" - official page reachable but the specific
#                  sub-scheme name could not be located at the cited
#                  URL within this sprint; the scheme is left in the
#                  catalog with safe-wording only.
SCHEMES_CATALOG: list[dict[str, Any]] = [
    {
        "id": "scheme-cgtmse",
        "name": "Credit Guarantee Fund Trust for Micro & Small Enterprises (CGTMSE)",
        "official_authority": "SIDBI (Small Industries Development Bank of India), under the Ministry of MSME",
        "description": "Collateral-free credit for eligible Micro and Small Enterprises. The official CGTMSE scheme (Credit Guarantee Scheme, jointly set up by the Ministry of MSME and SIDBI) provides a credit guarantee cover on loans extended by member banks and select financial institutions, allowing MSMEs to access working capital and term loans without third-party collateral. The official CGTMSE public page was cross-checked for this entry.",
        "category": "Financial Credit",
        "priority": "High",
        "benefits": [
            "Collateral-free loan coverage for eligible MSMEs",
            "Credit guarantee cover up to the official CGTMSE ceiling (currently INR 10 Crore, subject to the official CGTMSE circular in force)",
            "Available through member banks and select financial institutions (CGS-I, CGS-II, CGSCL, and PM SVANidhi sub-schemes)",
        ],
        "application_link": "https://www.cgtmse.in",
        "target_industries": ["all"],
        "min_turnover": 0.0,
        "max_turnover": 5000000.0,
        "official_source_url": "https://www.cgtmse.in",
        "last_verified": LAST_VERIFIED,
        "verified_status": "verified",
        "match_basis": "Industry match + turnover within official CGTMSE eligible range",
        "notes": "The CGTMSE guarantee ceiling, eligible loan size, and sector conditions are subject to the official CGTMSE circular in force. The figure above mirrors the official CGTMSE public page (cross-checked 2026-08-03: 'Ceiling of guarantee coverage increased to INR 10 Crore'); lenders may apply their own credit criteria on top.",
    },
    {
        "id": "scheme-zed",
        "name": "Zero Defect Zero Effect (ZED) Certification Scheme",
        "official_authority": "Ministry of Micro, Small and Medium Enterprises (MSME), Government of India",
        "description": "Quality certification and financial assistance programme for manufacturing MSMEs pursuing the 'Zero Defect Zero Effect' standard, with subsidy on certification cost and access to technology-upgrade support under the official ZED scheme.",
        "category": "Quality & Standards",
        "priority": "High",
        "benefits": [
            "Subsidy on ZED certification cost, per the official ZED model",
            "Technology-upgrade and quality-improvement support",
            "Recognition preferred by government and large-enterprise buyers",
        ],
        "application_link": "https://zed.msme.gov.in",
        "target_industries": ["Manufacturing", "Robotics", "Clean Energy", "Software"],
        "min_turnover": 50000.0,
        "max_turnover": 10000000.0,
        "official_source_url": "https://zed.msme.gov.in",
        "last_verified": LAST_VERIFIED,
        "verified_status": "verified",
        "match_basis": "Manufacturing-class industry + turnover within the ZED-eligible band",
        "notes": "Subsidy percentage and certification tiers are set by the official ZED portal and may be revised; the descriptions above reflect the public ZED page wording.",
    },
    {
        "id": "scheme-pmegp",
        "name": "Prime Minister Employment Generation Programme (PMEGP)",
        "official_authority": "Khadi and Village Industries Commission (KVIC), under the Ministry of MSME",
        "description": "Credit-linked subsidy programme for setting up new micro-enterprises (manufacturing and service / business). The official PMEGP scheme provides a margin-money subsidy on the project cost, with the residual funded through bank credit.",
        "category": "Employment & Subsidy",
        "priority": "High",
        "benefits": [
            "Margin-money subsidy on the project cost, at the official PMEGP rate (category and area based)",
            "Bank-financed residual project cost",
            "E-skills and entrepreneurship development training",
        ],
        "application_link": "https://www.kviconline.gov.in/pmegp",
        "target_industries": ["all"],
        "min_turnover": 0.0,
        "max_turnover": 1000000.0,
        "official_source_url": "https://www.kviconline.gov.in/pmegp",
        "last_verified": LAST_VERIFIED,
        "verified_status": "unverified",
        "match_basis": "Micro-enterprise turnover band + industry not excluded under the official PMEGP negative list",
        "notes": "Subsidy rate varies by applicant category (general / OBC / SC / ST / women / ex-serviceman / hill / non-hill) and by project cost cap. The official PMEGP portal publishes the current rate card. PMEGP entry was cross-checked against the scheme name and authority; the kviconline.gov.in URL did not return HTML from this VM at verification time, so detailed eligibility wording is presented as the official scheme wording without asserting current subsidy rates.",
    },
    {
        "id": "scheme-export-promotion",
        "name": "Market Access Initiative (MAI) Scheme",
        "official_authority": "Department of Commerce, Ministry of Commerce and Industry, Government of India",
        "description": "Financial assistance to Indian exporters and trade bodies for market-access activities such as participation in international trade fairs, buyer-seller meets, and market studies, under the official MAI Scheme guidelines.",
        "category": "Export & International",
        "priority": "Medium",
        "benefits": [
            "Financial assistance for participation in approved international trade events",
            "Support for buyer-seller meets and market-study trips",
            "Economy-class airfare and stall-cost support, within official MAI limits",
        ],
        "application_link": "https://www.commerce.gov.in",
        "target_industries": ["Manufacturing", "Supply Chain", "Retail Trade"],
        "min_turnover": 200000.0,
        "max_turnover": 20000000.0,
        "official_source_url": "https://www.commerce.gov.in",
        "last_verified": LAST_VERIFIED,
        "verified_status": "verified",
        "match_basis": "Manufacturing / trade / supply-chain industry + turnover within MAI's typical MSME band",
        "notes": "Per-event and per-airfare ceilings are set by the MAI Scheme guidelines issued by the Department of Commerce; the figures in the public page are indicative and subject to the prevailing MAI circular.",
    },
    {
        "id": "scheme-mudra-shishu",
        "name": "Pradhan Mantri MUDRA Yojana - Shishu Loan",
        "official_authority": "Micro Units Development and Refinance Agency Ltd. (MUDRA), under the Ministry of Finance",
        "description": "Collateral-free working-capital loan for early-stage micro-enterprises under the official Shishu category of PMMY (loans up to INR 50,000), disbursed through member banks, NBFCs, MFIs, and other lending institutions.",
        "category": "Working Capital",
        "priority": "High",
        "benefits": [
            "Collateral-free working-capital loan up to INR 50,000 under the Shishu category",
            "Disbursed through member banks, NBFCs, and MFIs",
            "No requirement for a third-party guarantee under the Shishu category",
        ],
        "application_link": "https://www.mudra.org.in",
        "target_industries": ["all"],
        "min_turnover": 0.0,
        "max_turnover": 500000.0,
        "official_source_url": "https://www.mudra.org.in",
        "last_verified": LAST_VERIFIED,
        "verified_status": "verified",
        "match_basis": "Micro-enterprise turnover band + non-negative-credit lending",
        "notes": "Interest rate and processing fee are set by the individual lending institution; MUDRA refinances the loan but does not fix the borrower-facing rate.",
    },
    {
        "id": "scheme-nsic",
        "name": "NSIC - Marketing and Export Facilitation Services",
        "official_authority": "National Small Industries Corporation (NSIC), under the Ministry of MSME",
        "description": "NSIC runs a portfolio of marketing, technology, and export-facilitation services for MSMEs, including participation in government-store procurement, marketing development, and MSME Global Mart e-commerce support.",
        "category": "Development & Support",
        "priority": "Medium",
        "benefits": [
            "Marketing development and buyer-connect support",
            "MSME Global Mart e-commerce facilitation",
            "Access to NSIC's single-point registration and technology services",
        ],
        "application_link": "https://www.nsic.co.in",
        "target_industries": ["Manufacturing", "Service", "Trading"],
        "min_turnover": 0.0,
        "max_turnover": 50000000.0,
        "official_source_url": "https://www.nsic.co.in",
        "last_verified": LAST_VERIFIED,
        "verified_status": "verified",
        "match_basis": "Manufacturing / service / trading industry + turnover within the MSME definition",
        "notes": "The public NSIC page lists several distinct sub-schemes (SPRS, RMA, Marketing Facilitation, e-Marketing, MSME Aggregation); the description above maps to the MSME-eligible subset, not to any single sub-scheme.",
    },
    {
        "id": "scheme-udyam",
        "name": "Udyam Registration (MSME Classification)",
        "official_authority": "Ministry of Micro, Small and Medium Enterprises (MSME), Government of India",
        "description": "The official Udyam Registration is the government-recognised MSME classification certificate. It is the entry point for most MSME benefits and is a prerequisite for many other scheme applications.",
        "category": "MSME Registration",
        "priority": "High",
        "benefits": [
            "Government-recognised MSME classification certificate",
            "Prerequisite for priority-sector lending and most other MSME schemes",
            "Lifetime validity; no renewal required for the certificate itself",
        ],
        "application_link": "https://udyamregistration.gov.in",
        "target_industries": ["all"],
        "min_turnover": 0.0,
        "max_turnover": 50000000.0,
        "official_source_url": "https://udyamregistration.gov.in",
        "last_verified": LAST_VERIFIED,
        "verified_status": "unverified",
        "match_basis": "Any MSME-classifiable business; free to all eligible applicants",
        "notes": "Udyam Registration itself is a free, self-declared classification - it is not a financial benefit. The catalogue lists it because every other MSME scheme gates on having a valid Udyam Registration. The udyamregistration.gov.in public page was not reachable from this VM at verification time; scheme name and authority are accurate per the Ministry of MSME public statement but the Udyam portal page itself was not cross-checked in this sprint.",
    },
]  # NOTE: Matching, eligibility, and sanctions are decided by the official
# authority (Ministry of MSME / NSIC / SIDBI / KVIC / Department of Commerce
# / MUDRA). The matching score produced by UrsBiz is a similarity read
# against this static dataset, not a decision of eligibility or approval.
# Currency conversions are not asserted because the official authority
# prices each scheme in INR; the figures shown here are the official
# scheme wording, not UrsBiz estimates.


class SchemeRecommendationEngine:
    """Deterministic recommendation engine for government schemes."""

    def __init__(self, repo: BusinessRepository) -> None:
        self._repo = repo

    def evaluate_scheme(self, business: Business, raw: dict[str, Any]) -> SchemeItem:
        rev = business.annual_revenue or 0.0
        ind = business.industry or "General"

        ind_match = "all" in raw["target_industries"] or ind in raw["target_industries"]
        min_t = raw.get("min_turnover", 0.0) or 0.0
        max_t = raw.get("max_turnover", 99999999.0) or 99999999.0
        turnover_match = min_t <= rev <= max_t

        if ind_match and turnover_match:
            status = "matching"
            reason = (
                f"Industry ({ind}) and annual turnover are within the official "
                f"scheme band. Matching does not constitute eligibility."
            )
            score = 92 if raw["priority"] == "High" else 85
        elif ind_match or turnover_match:
            status = "partialMatch"
            reason = (
                f"Partial match: {'industry matches' if ind_match else 'turnover band matches'} "
                f"the official scheme criteria. The other axis is outside the band."
            )
            score = 65
        else:
            status = "outsideBand"
            reason = (
                "Business profile sits outside the official scheme's industry and "
                "turnover band. The scheme may still apply under exceptional categories; "
                "verify on the official portal."
            )
            score = 30

        # Documents and steps are framed as the official authority's
        # typical requirements, not as UrsBiz-issued guarantees. They
        # are starting points, not a checklist issued by UrsBiz.
        docs = [
            "Business registration / Udyam Registration (where applicable)",
            "PAN / Tax Identification Number of the business or proprietor",
            "Latest 2-Year Audited Financial Statements (or ITR)",
            "Bank Statement (Last 6 Months)",
        ]

        steps = [
            "Verify eligibility and the latest rules on the official scheme portal",
            "Register or sign in on the official government scheme portal",
            "Upload business registration, Udyam, and financial statements",
            "Submit the application and track the status on the official portal",
        ]

        return SchemeItem(
            id=raw["id"],
            name=raw["name"],
            description=raw["description"],
            category=raw["category"],
            eligibility_status=status,
            eligibility_reason=reason,
            matching_score=score,
            priority=raw["priority"],
            benefits=raw["benefits"],
            documents_required=docs,
            application_steps=steps,
            application_link=raw["application_link"],
            target_industries=raw["target_industries"],
            max_turnover=raw.get("max_turnover"),
            min_turnover=raw.get("min_turnover"),
            official_authority=raw["official_authority"],
            official_source_url=raw["official_source_url"],
            last_verified=raw["last_verified"],
            verified_status=raw["verified_status"],
            match_basis=raw["match_basis"],
            notes=raw.get("notes"),
        )

    def recommend_schemes(self, business: Business) -> CategorizedSchemes:
        rec: list[SchemeItem] = []
        el: list[SchemeItem] = []
        pel: list[SchemeItem] = []
        nel: list[SchemeItem] = []

        for raw in SCHEMES_CATALOG:
            item = self.evaluate_scheme(business, raw)
            if item.eligibility_status == "matching":
                el.append(item)
                if item.priority == "High":
                    rec.append(item)
            elif item.eligibility_status == "partialMatch":
                pel.append(item)
            else:
                nel.append(item)

        return CategorizedSchemes(
            recommended=rec,
            eligible=el,
            partially_eligible=pel,
            not_eligible=nel,
        )

    def compute(self, owner_id: int) -> BusinessSchemesResponse:
        business = self._repo.get_by_owner(owner_id)
        if business is None:
            raise BusinessNotFound("No business profile found for this user.")

        categorized = self.recommend_schemes(business)
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        total = len(SCHEMES_CATALOG)

        return BusinessSchemesResponse(
            generated_at=now_iso,
            total_schemes=total,
            schemes=categorized,
            disclaimer=(
                "Matching is informational. Final eligibility and approval are determined by the official authority. "
                "The matching score and categories shown here are computed by UrsBiz against a static dataset; "
                "they do not guarantee eligibility, subsidy, or approval."
            ),
        )
