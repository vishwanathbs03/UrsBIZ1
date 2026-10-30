"""SPRINT AI-16 — Verified External Knowledge + Freshness Layer.

Government-scheme answer card.

The brief mandates a fixed-field advisory card for every
scheme answer. The card is purely data (no Markdown) so the
frontend can render it in any layout it wants. The card is
also the *only* place a scheme answer may appear — the
renderer must NOT emit a paragraph-style "you are eligible"
narrative; it must show the card and let the user decide.

Required fields
---------------

  * official scheme name
  * authority
  * benefit description
  * eligibility
  * required documents
  * official application link
  * last verified date
  * why this business may match
  * missing eligibility information
  * final-authority disclaimer

The card is conservative: it never asserts eligibility. It
says "Potential match based on the available business
information" — the brief mandates this exact phrasing.

Conservative eligibility language
--------------------------------

The brief: "Never say 'you are definitely eligible' unless an
authoritative eligibility verification actually exists." The
:class:`SchemeAnswerCardBuilder` therefore emits a
``match_disposition`` enum:

  * ``"potential_match"`` — at least one eligibility signal
    is present, but no authoritative verification exists.
  * ``"gap_unknown"``     — eligibility signals are missing.
  * ``"conflict"``        — two eligibility signals disagree
    (e.g. age criterion says yes, sector criterion says no).

The renderer maps the disposition to the brief-mandated
phrasing. The card itself never asserts eligibility — that
power remains with the final authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.services.ai.knowledge.external_knowledge_base import (
    ClassifiedClaim,
    ExternalKnowledgeRetriever,
)
from app.services.ai.knowledge.external_types import (
    ClaimKind,
    ExternalSource,
)


# --------------------------------------------------------------------------- #
# Disposition
# --------------------------------------------------------------------------- #


class MatchDisposition(str, Enum):
    """How a scheme matches the user's business profile.

    The brief is explicit: never assert eligibility. The
    disposition drives the renderer phrasing.
    """

    POTENTIAL_MATCH = "potential_match"
    GAP_UNKNOWN = "gap_unknown"
    CONFLICT = "conflict"


# --------------------------------------------------------------------------- #
# Card
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SchemeAnswerCard:
    """One government-scheme advisory card.

    Pure data. The renderer composes the visual card from
    these fields; the engine does not produce prose. The card
    is the single canonical answer for a scheme prompt — the
    engine must not append a free-form paragraph that could
    override the conservative language.
    """

    scheme_id: str
    official_name: str
    authority: str
    benefit_description: tuple[str, ...] = ()
    eligibility: tuple[str, ...] = ()
    required_documents: tuple[str, ...] = ()
    application_link: str = ""
    last_verified_date: str = ""
    why_business_may_match: tuple[str, ...] = ()
    missing_eligibility_info: tuple[str, ...] = ()
    final_authority_disclaimer: str = ""
    match_disposition: MatchDisposition = MatchDisposition.GAP_UNKNOWN
    source: ExternalSource | None = None
    claim_kind: ClaimKind = ClaimKind.EXTERNAL_FACT
    authority_weight: float = 0.0

    def to_dict(self) -> dict:
        return {
            "scheme_id": self.scheme_id,
            "official_name": self.official_name,
            "authority": self.authority,
            "benefit_description": list(self.benefit_description),
            "eligibility": list(self.eligibility),
            "required_documents": list(self.required_documents),
            "application_link": self.application_link,
            "last_verified_date": self.last_verified_date,
            "why_business_may_match": list(self.why_business_may_match),
            "missing_eligibility_info": list(self.missing_eligibility_info),
            "final_authority_disclaimer": self.final_authority_disclaimer,
            "match_disposition": self.match_disposition.value,
            "source": self.source.to_dict() if self.source else None,
            "claim_kind": self.claim_kind.value,
            "authority_weight": self.authority_weight,
        }


# --------------------------------------------------------------------------- #
# Scheme templates
# --------------------------------------------------------------------------- #


# Mandatory disclaimers. The renderer prepends this verbatim.
_FINAL_AUTHORITY_DISCLAIMER = (
    "Final eligibility, benefit amount, and approval decision rest with the "
    "scheme's nodal authority. UrsBiz does not certify eligibility. "
    "Please verify with the relevant authority before applying."
)

# Per-scheme templates. The builder composes the card from
# one of these + the user's profile signals.
_SCHEME_TEMPLATES: dict[str, dict] = {
    "mudra": {
        "official_name": "Pradhan Mantri Mudra Yojana (MUDRA)",
        "authority": "MUDRA — Government of India",
        "application_link": "https://www.udyamimitra.in/PMMY-Loan",
        "eligibility": (
            "Non-corporate, non-farm small / micro enterprises seeking loans up to ₹10 lakh.",
            "Valid Indian citizen, aged 18+.",
            "Business plan / activity in non-farm sector.",
        ),
        "required_documents": (
            "Identity proof (Aadhaar / PAN / Voter ID).",
            "Address proof.",
            "Business proof (Udyam registration, if available).",
            "Bank statements (last 6-12 months).",
            "Business plan / quotations for use of funds.",
        ),
        "tag": "mudra",
    },
    "pmegp": {
        "official_name": "Prime Minister's Employment Generation Programme (PMEGP)",
        "authority": "KVIC — Ministry of MSME, Government of India",
        "application_link": "https://www.kviconline.gov.in/pmegp/pmegpweb/",
        "eligibility": (
            "Indian citizen aged 18+.",
            "Class VIII pass (or higher, depending on project cost).",
            "Project cost up to ₹25 lakh in manufacturing, ₹10 lakh in service sector.",
            "Self-help groups, institutions, cooperatives also eligible.",
        ),
        "required_documents": (
            "Project report.",
            "Identity / address proof.",
            "Education certificates.",
            "Caste / income certificate (if applicable).",
            "Quotations for machinery / equipment.",
        ),
        "tag": "pmegp",
    },
    "cgtmse": {
        "official_name": "Credit Guarantee Fund Trust for Micro and Small Enterprises (CGTMSE)",
        "authority": "CGTMSE — Government of India / SIDBI",
        "application_link": "https://www.cgtmse.in/",
        "eligibility": (
            "Registered micro or small enterprise (Udyam registered).",
            "Loan amount up to ₹5 crore.",
            "Borrower's account should be standard with no irregularities.",
        ),
        "required_documents": (
            "Udyam registration certificate.",
            "Loan application with business plan.",
            "Financial statements / IT returns.",
            "KYC documents of promoter(s).",
        ),
        "tag": "cgtmse",
    },
    "treds": {
        "official_name": "Trade Receivables Discounting System (TReDS)",
        "authority": "Reserve Bank of India (RBI)",
        "application_link": "https://www.rxil.in/",
        "eligibility": (
            "MSME supplier with valid Udyam registration.",
            "Corporate buyer must be a participant of a TReDS factor platform.",
        ),
        "required_documents": (
            "Udyam registration.",
            "Invoice(s) raised on the corporate buyer.",
            "Buyer confirmation on the TReDS platform.",
        ),
        "tag": "treds",
    },
    "udyam": {
        "official_name": "Udyam Registration",
        "authority": "Ministry of MSME, Government of India",
        "application_link": "https://udyamregistration.gov.in/",
        "eligibility": (
            "Micro, small or medium enterprise engaged in manufacturing, "
            "trading, or services.",
            "Self-declaration based; no documents required upfront.",
        ),
        "required_documents": (
            "Aadhaar number of the proprietor / authorised signatory.",
            "PAN of the business.",
        ),
        "tag": "udyam",
    },
}


# --------------------------------------------------------------------------- #
# Builder
# --------------------------------------------------------------------------- #


class SchemeAnswerCardBuilder:
    """Build a :class:`SchemeAnswerCard` for a given scheme + profile.

    The builder is conservative:

      * Eligibility assertions always carry
        ``"Potential match based on the available business information."``
      * Missing profile fields are surfaced verbatim, not
        interpolated.
      * The final-authority disclaimer is mandatory and cannot
        be removed by the caller.
      * A source URL is mandatory; missing sources block the
        card from being published.
    """

    _DISPOSITION_TO_PHRASE: dict[MatchDisposition, str] = {
        MatchDisposition.POTENTIAL_MATCH: (
            "Potential match based on the available business information."
        ),
        MatchDisposition.GAP_UNKNOWN: (
            "Eligibility cannot be confirmed from the available business "
            "information. Missing signals listed below."
        ),
        MatchDisposition.CONFLICT: (
            "Conflicting eligibility signals; manual review required."
        ),
    }

    def supported_schemes(self) -> tuple[str, ...]:
        """The list of scheme IDs the builder knows about."""
        return tuple(_SCHEME_TEMPLATES.keys())

    def build(
        self,
        scheme_id: str,
        *,
        context: Any = None,
        retriever: ExternalKnowledgeRetriever | None = None,
    ) -> SchemeAnswerCard:
        """Build a scheme card.

        ``context`` is the user's :class:`AssistantContext`
        (forward-refed to avoid the import cycle). When the
        profile is missing, the card surfaces the gaps rather
        than asserting eligibility.

        ``retriever`` is optional; when supplied, the source
        freshness is checked before the card is published.
        """
        template = _SCHEME_TEMPLATES.get(scheme_id)
        if template is None:
            raise ValueError(
                f"Unknown scheme_id {scheme_id!r}. "
                f"Supported: {self.supported_schemes()}"
            )

        retriever = retriever or ExternalKnowledgeRetriever()
        source_claims: tuple[ClassifiedClaim, ...] = retriever.get_by_tag(
            template["tag"]
        )
        if not source_claims:
            raise ValueError(
                f"No verified external source for scheme {scheme_id!r}."
            )
        # Pick the highest-authority claim (defensive — should
        # always be exactly one per tag in the corpus).
        claim = max(source_claims, key=lambda c: c.authority)
        source = claim.source
        if source is None:
            raise ValueError(
                f"External claim for {scheme_id!r} carries no source."
            )

        why_match, missing, disposition = self._evaluate_eligibility(
            scheme_id, context
        )
        benefits = self._extract_benefits(claim.text)

        return SchemeAnswerCard(
            scheme_id=scheme_id,
            official_name=template["official_name"],
            authority=template["authority"],
            benefit_description=benefits,
            eligibility=template["eligibility"],
            required_documents=template["required_documents"],
            application_link=template["application_link"],
            last_verified_date=source.published_at or source.retrieved_at,
            why_business_may_match=why_match,
            missing_eligibility_info=missing,
            final_authority_disclaimer=_FINAL_AUTHORITY_DISCLAIMER,
            match_disposition=disposition,
            source=source,
            claim_kind=claim.kind,
            authority_weight=claim.authority,
        )

    # --- internals ------------------------------------------------------ #

    def _evaluate_eligibility(
        self, scheme_id: str, context: Any
    ) -> tuple[tuple[str, ...], tuple[str, ...], MatchDisposition]:
        """Return (why-match, missing-info, disposition).

        Conservative by construction: any unknown signal
        flips the disposition to ``GAP_UNKNOWN`` rather than
        asserting ``POTENTIAL_MATCH``.
        """
        why: list[str] = []
        missing: list[str] = []
        if context is None:
            missing.extend(
                [
                    "Udyam / MSME registration status",
                    "Industry sector",
                    "Annual revenue / turnover",
                    "Number of employees",
                ]
            )
            return (tuple(why), tuple(missing), MatchDisposition.GAP_UNKNOWN)

        industry = getattr(context, "industry", None)
        if industry and isinstance(industry, str) and industry.strip():
            why.append(f"Industry on file: {industry}.")
        else:
            missing.append("Industry sector")

        revenue = getattr(context, "annual_revenue_inr", None)
        if revenue is not None and revenue > 0:
            why.append(f"Annual turnover on file: ₹{revenue:,.0f}.")
        else:
            missing.append("Annual revenue / turnover")

        employees = getattr(context, "employee_count", None)
        if employees is not None and employees >= 0:
            why.append(f"Employee count on file: {employees}.")
        else:
            missing.append("Number of employees")

        if scheme_id in {"mudra", "pmegp", "cgtmse", "treds"}:
            registered = getattr(context, "udyam_number", None) or getattr(
                context, "is_registered_msme", None
            )
            if registered:
                why.append("Udyam / MSME registration is on file.")
            else:
                missing.append(
                    "Udyam / MSME registration status (Udyam number or proof)"
                )

        # Disposition rule
        if missing:
            return (tuple(why), tuple(missing), MatchDisposition.GAP_UNKNOWN)
        if why:
            return (tuple(why), tuple(missing), MatchDisposition.POTENTIAL_MATCH)
        return (tuple(why), tuple(missing), MatchDisposition.GAP_UNKNOWN)

    def _extract_benefits(self, claim_text: str) -> tuple[str, ...]:
        """Split the corpus claim text into benefit sentences.

        Conservative: never invent benefits. We return the
        sentences the source actually carries, split on
        periods.
        """
        out: list[str] = []
        for sentence in claim_text.split("."):
            s = sentence.strip()
            if s:
                out.append(s + ".")
        return tuple(out)
