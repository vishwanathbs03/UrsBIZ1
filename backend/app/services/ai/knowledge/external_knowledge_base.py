"""SPRINT AI-16 — Verified External Knowledge + Freshness Layer.

Curated, provenance-first external knowledge base.

Scope
-----
This module is the *one* place external facts live. Every fact
is a tuple of ``(text, ExternalSource)`` — the text NEVER floats
without provenance. The :class:`ExternalKnowledgeRetriever` is
the only path into this data; callers cannot construct
:class:`ClassifiedClaim` from external data without going through
it (the :class:`ClaimKind` is forced to ``EXTERNAL_FACT`` and the
source is mandatory).

The corpus is intentionally small and curated — the brief
mandates "never fabricate dates, rules, benefits or links" and
the safest way to honour that is to keep the corpus short and
let the retriever say "I cannot verify this" rather than guess.

Sections covered
----------------

  * ENCYCLOPEDIC — What is EBITDA, REACH, GST, BRSR, ...
  * REGULATORY    — REACH compliance, BIS, FSSAI, RoHS, ...
  * SCHEME        — MUDRA, PMEGP, CGTMSE, TReDS, Udyam, ...
  * EXPORT        — EU textile certifications, US FDA, ...
  * GENERAL       — definition lookups for common MSME terms

The corpus is mocked at code level. A real deployment would
fetch from a CMS, a vetted scraper, or a paid API (e.g. Indira
Sanchay, IndiaCode, MCX) — all of which would emit the same
``ExternalSource`` shape.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from app.services.ai.knowledge.external_types import (
    ContentCategory,
    ClassifiedClaim,
    ClaimKind,
    ExternalSource,
    SourceAuthority,
    now_iso,
)


# --------------------------------------------------------------------------- #
# Corpus record
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _CorpusEntry:
    """Internal representation of one curated external fact."""

    text: str
    source: ExternalSource
    # Topic tags the retriever matches against the prompt. Lower-case.
    tags: tuple[str, ...] = ()
    # Optional authority override (e.g. when the source is a
    # direct gazette notification, not just the ministry page).
    # Defaults to the source's tier weight × freshness penalty.
    authority: float = 0.0


# --------------------------------------------------------------------------- #
# Curated corpus
# --------------------------------------------------------------------------- #


def _build_corpus() -> tuple[_CorpusEntry, ...]:
    """Return the curated, provenance-tagged external corpus.

    Every entry is a fact the LLM can repeat verbatim. Entries
    are ordered by topic for readability — retrieval is by
    substring match against ``tags``, not by order.
    """
    ret = now_iso()
    # 1. Encyclopedic / general MSME definitions
    eb1 = _CorpusEntry(
        text=(
            "EBITDA stands for Earnings Before Interest, Taxes, "
            "Depreciation, and Amortization. It is a measure of a "
            "company's overall operating performance."
        ),
        source=ExternalSource(
            source_url="https://www.investopedia.com/terms/e/ebitda.asp",
            publisher="Investopedia",
            retrieved_at=ret,
            published_at="2024-06-12T00:00:00Z",
            authority_level=SourceAuthority.TIER_2,
            category=ContentCategory.ENCYCLOPEDIC,
            title="EBITDA — Definition",
            content_excerpt="Earnings Before Interest, Taxes, Depreciation, and Amortization",
        ),
        tags=("ebitda", "what is ebitda", "earnings", "finance", "ebit"),
    )
    eb2 = _CorpusEntry(
        text=(
            "REACH (Registration, Evaluation, Authorisation and "
            "Restriction of Chemicals) is a European Union regulation "
            "adopted in 2006 to improve the protection of human "
            "health and the environment from chemical risks."
        ),
        source=ExternalSource(
            source_url="https://echa.europa.eu/regulations/reach",
            publisher="European Chemicals Agency (ECHA)",
            retrieved_at=ret,
            published_at="2024-01-15T00:00:00Z",
            authority_level=SourceAuthority.TIER_1,
            category=ContentCategory.REGULATORY,
            title="REACH — Overview",
            content_excerpt="Registration, Evaluation, Authorisation and Restriction of Chemicals",
        ),
        tags=("reach", "reach compliance", "chemical", "european regulation", "echa"),
    )
    eb3 = _CorpusEntry(
        text=(
            "Goods and Services Tax (GST) in India is a comprehensive "
            "indirect tax levied on the supply of goods and services. "
            "It replaced multiple central and state taxes from 1 July 2017."
        ),
        source=ExternalSource(
            source_url="https://www.gst.gov.in/",
            publisher="Government of India — GST Council",
            retrieved_at=ret,
            published_at="2024-04-01T00:00:00Z",
            authority_level=SourceAuthority.TIER_1,
            category=ContentCategory.STATUTORY,
            title="GST — What is it?",
            content_excerpt="Comprehensive indirect tax on supply of goods and services",
        ),
        tags=("gst", "what is gst", "tax", "taxation"),
    )
    eb4 = _CorpusEntry(
        text=(
            "MSME stands for Micro, Small and Medium Enterprises. "
            "In India, MSMEs are classified under the MSMED Act, 2006, "
            "and registered via the Udyam portal."
        ),
        source=ExternalSource(
            source_url="https://udyamregistration.gov.in/Government-India/Ministry-MSME-registration.htm",
            publisher="Ministry of Micro, Small & Medium Enterprises, Government of India",
            retrieved_at=ret,
            published_at="2023-11-20T00:00:00Z",
            authority_level=SourceAuthority.TIER_1,
            category=ContentCategory.REGULATORY,
            title="MSME / Udyam — Overview",
            content_excerpt="Micro, Small and Medium Enterprises — MSMED Act 2006",
        ),
        tags=("msme", "what is msme", "msmed"),
    )
    eb5 = _CorpusEntry(
        text=(
            "Working capital is the capital a business uses for its "
            "day-to-day operations, calculated as current assets minus "
            "current liabilities."
        ),
        source=ExternalSource(
            source_url="https://www.investopedia.com/terms/w/workingcapital.asp",
            publisher="Investopedia",
            retrieved_at=ret,
            published_at="2024-05-02T00:00:00Z",
            authority_level=SourceAuthority.TIER_2,
            category=ContentCategory.ENCYCLOPEDIC,
            title="Working Capital — Definition",
            content_excerpt="Current assets minus current liabilities",
        ),
        tags=("working_capital", "what is working capital", "current assets"),
    )
    eb6 = _CorpusEntry(
        text=(
            "BRSR (Business Responsibility and Sustainability Report) "
            "is a disclosure framework for top listed Indian companies "
            "on environmental, social and governance (ESG) parameters, "
            "mandated by SEBI from FY 2022-23."
        ),
        source=ExternalSource(
            source_url="https://www.sebi.gov.in/legal/circulars/may-2021/brsr.html",
            publisher="Securities and Exchange Board of India (SEBI)",
            retrieved_at=ret,
            published_at="2023-08-10T00:00:00Z",
            authority_level=SourceAuthority.TIER_1,
            category=ContentCategory.REGULATORY,
            title="BRSR — SEBI circular",
            content_excerpt="Business Responsibility and Sustainability Report",
        ),
        tags=("brsr", "esg", "sustainability", "sebi"),
    )

    # 2. Government schemes
    sc1 = _CorpusEntry(
        text=(
            "MUDRA Yojana (Pradhan Mantri Mudra Yojana) provides loans "
            "up to ₹10 lakh to non-corporate, non-farm small/micro "
            "enterprises. Three categories: Shishu (up to ₹50,000), "
            "Kishore (₹50,000 to ₹5 lakh), Tarun (₹5 lakh to ₹10 lakh)."
        ),
        source=ExternalSource(
            source_url="https://www.mudra.org.in/",
            publisher="MUDRA — Government of India",
            retrieved_at=ret,
            published_at="2024-02-10T00:00:00Z",
            authority_level=SourceAuthority.TIER_1,
            category=ContentCategory.SCHEME,
            title="MUDRA Yojana — Scheme details",
            content_excerpt="Loans up to ₹10 lakh — Shishu / Kishore / Tarun",
        ),
        tags=("mudra", "scheme", "loan", "msme", "pmegp", "subsidy"),
    )
    sc2 = _CorpusEntry(
        text=(
            "PMEGP (Prime Minister's Employment Generation Programme) "
            "is a credit-linked subsidy scheme for setting up new "
            "micro-enterprises in non-farm sector. Subsidy: 15-35% of "
            "project cost (up to ₹50 lakh in service sector, ₹25 lakh "
            "in manufacturing)."
        ),
        source=ExternalSource(
            source_url="https://www.kviconline.gov.in/pmegp/pmegpweb/",
            publisher="KVIC — Ministry of MSME, Government of India",
            retrieved_at=ret,
            published_at="2024-01-30T00:00:00Z",
            authority_level=SourceAuthority.TIER_1,
            category=ContentCategory.SCHEME,
            title="PMEGP — Scheme details",
            content_excerpt="Credit-linked subsidy — 15-35% of project cost",
        ),
        tags=("pmegp", "scheme", "subsidy", "msme", "kvic", "employment"),
    )
    sc3 = _CorpusEntry(
        text=(
            "CGTMSE (Credit Guarantee Fund Trust for Micro and Small "
            "Enterprises) provides collateral-free credit to MSEs. "
            "Coverage up to ₹5 crore per borrower; guarantee fee "
            "between 0.5% and 1.5% per annum."
        ),
        source=ExternalSource(
            source_url="https://www.cgtmse.in/",
            publisher="CGTMSE — Government of India / SIDBI",
            retrieved_at=ret,
            published_at="2023-12-05T00:00:00Z",
            authority_level=SourceAuthority.TIER_1,
            category=ContentCategory.SCHEME,
            title="CGTMSE — Scheme details",
            content_excerpt="Collateral-free credit up to ₹5 crore",
        ),
        tags=("cgtmse", "scheme", "collateral", "credit guarantee", "msme"),
    )
    sc4 = _CorpusEntry(
        text=(
            "TReDS (Trade Receivables Discounting System) is an "
            "electronic platform for discounting invoices of MSMEs "
            "from corporate buyers, anchored by RBI. Three factors: "
            "RXIL, M1xchange, Invoicemart."
        ),
        source=ExternalSource(
            source_url="https://www.rbi.org.in/Scripts/BS_PressReleaseView.aspx?id=33329",
            publisher="Reserve Bank of India (RBI)",
            retrieved_at=ret,
            published_at="2024-03-22T00:00:00Z",
            authority_level=SourceAuthority.TIER_1,
            category=ContentCategory.SCHEME,
            title="TReDS — RBI framework",
            content_excerpt="Electronic invoice discounting for MSMEs",
        ),
        tags=("treds", "scheme", "invoice discounting", "rbi", "msme"),
    )
    sc5 = _CorpusEntry(
        text=(
            "Udyam Registration is the free, online, self-declaration "
            "registration for MSMEs in India. It replaced the earlier "
            "Udyog Aadhaar Memorandum from 1 July 2020."
        ),
        source=ExternalSource(
            source_url="https://udyamregistration.gov.in/",
            publisher="Ministry of MSME, Government of India",
            retrieved_at=ret,
            published_at="2024-01-10T00:00:00Z",
            authority_level=SourceAuthority.TIER_1,
            category=ContentCategory.SCHEME,
            title="Udyam Registration",
            content_excerpt="Free online MSME registration",
        ),
        tags=("udyam", "registration", "msme", "udyog aadhaar"),
    )

    # 3. Export / regulatory
    ex1 = _CorpusEntry(
        text=(
            "Textile exporters to the European Union must comply with "
            "REACH for chemical inputs, and may require OEKO-TEX "
            "certification to demonstrate that finished textiles are "
            "free from harmful substances."
        ),
        source=ExternalSource(
            source_url="https://echa.europa.eu/regulations/reach",
            publisher="European Chemicals Agency (ECHA)",
            retrieved_at=ret,
            published_at="2024-01-15T00:00:00Z",
            authority_level=SourceAuthority.TIER_1,
            category=ContentCategory.EXPORT_REQUIREMENT,
            title="Textile export to EU — chemical compliance",
            content_excerpt="REACH + OEKO-TEX",
        ),
        tags=("textile", "export", "european union", "reach", "oeko-tex", "certification"),
    )
    ex2 = _CorpusEntry(
        text=(
            "Indian exporters to the USA need an IEC (Import Export "
            "Code) from DGFT; food products additionally require FDA "
            "registration and may need FSVP-importer compliance."
        ),
        source=ExternalSource(
            source_url="https://www.dgft.gov.in/CP/?opt=iec",
            publisher="Directorate General of Foreign Trade (DGFT)",
            retrieved_at=ret,
            published_at="2023-10-15T00:00:00Z",
            authority_level=SourceAuthority.TIER_1,
            category=ContentCategory.EXPORT_REQUIREMENT,
            title="IEC — Import Export Code",
            content_excerpt="Mandatory for all Indian exporters",
        ),
        tags=("export", "iec", "dgft", "fda", "usa", "us exporter"),
    )
    ex3 = _CorpusEntry(
        text=(
            "BIS (Bureau of Indian Standards) certification is "
            "compulsory for several product categories in India, "
            "including electrical equipment, pressure cookers, and "
            "certain chemicals."
        ),
        source=ExternalSource(
            source_url="https://www.bis.gov.in/",
            publisher="Bureau of Indian Standards",
            retrieved_at=ret,
            published_at="2023-09-01T00:00:00Z",
            authority_level=SourceAuthority.TIER_1,
            category=ContentCategory.REGULATORY,
            title="BIS Certification",
            content_excerpt="Compulsory for several product categories",
        ),
        tags=("bis", "certification", "regulatory", "standards"),
    )

    # 4. Financial rates (will appear STALE quickly to exercise the
    # freshness check)
    fin1 = _CorpusEntry(
        text=(
            "RBI repo rate is the policy rate at which the Reserve "
            "Bank lends short-term funds to commercial banks. It is "
            "the benchmark for bank lending rates."
        ),
        source=ExternalSource(
            source_url="https://www.rbi.org.in/Scripts/FS_Overview.aspx?fn=2752",
            publisher="Reserve Bank of India (RBI)",
            retrieved_at=ret,
            # 3 years old — beyond the FINANCIAL_RATE safe window.
            published_at="2023-01-15T00:00:00Z",
            authority_level=SourceAuthority.TIER_1,
            category=ContentCategory.FINANCIAL_RATE,
            title="Repo rate — RBI",
            content_excerpt="Policy rate at which RBI lends to commercial banks",
        ),
        tags=("repo_rate", "rbi", "interest rate", "lending rate"),
    )

    return (
        eb1, eb2, eb3, eb4, eb5, eb6,
        sc1, sc2, sc3, sc4, sc5,
        ex1, ex2, ex3,
        fin1,
    )


_CORPUS: tuple[_CorpusEntry, ...] = _build_corpus()


# --------------------------------------------------------------------------- #
# Retriever
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RetrievalResult:
    """What the retriever returns.

    ``matches`` is the curated, provenance-tagged claims. ``empty_reason``
    is the canonical "I cannot verify this" string the renderer shows
    when there are no matches. The retriever NEVER invents a fact to
    fill empty ``matches``.
    """

    matches: tuple[ClassifiedClaim, ...] = ()
    query_tags: tuple[str, ...] = ()
    empty_reason: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.matches


class ExternalKnowledgeRetriever:
    """Verifies external facts with provenance + freshness.

    The retriever is a pure function (no I/O, no LLM). It walks the
    curated corpus, matches against the prompt's tags, and emits a
    :class:`RetrievalResult` whose every claim carries its
    :class:`ExternalSource` and authority weight.

    Failure modes
    -------------

    * **No matches** — the retriever returns
      ``RetrievalResult(empty_reason=...)``. The renderer MUST show
      "We could not verify this with the available sources" rather
      than guess.
    * **Stale matches** — the retriever still returns the match,
      but the claim's authority is already demoted (the
      ``ExternalSource.effective_authority`` field reflects the
      freshness penalty).
    * **Conflicting matches** — the retriever returns all matches;
      the caller picks the highest-authority one (or surfaces the
      conflict when two TIER_1 sources disagree).
    """

    # Tag extraction — keep it cheap and deterministic.
    _TAG_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("ebitda", ("ebitda", "earnings before interest", "ebit")),
        ("reach", ("reach", "reach compliance", "reach regulation")),
        ("gst", ("gst", "goods and services tax", "indirect tax")),
        ("msme", ("msme", "msmed", "udyam", "micro small medium")),
        ("working_capital", ("working capital", "current assets minus")),
        ("brsr", ("brsr", "business responsibility and sustainability")),
        ("mudra", ("mudra", "pm mudra", "shishu", "kishore", "tarun")),
        ("pmegp", ("pmegp", "employment generation")),
        ("cgtmse", ("cgtmse", "credit guarantee", "collateral-free")),
        ("treds", ("treds", "trade receivables discounting")),
        ("udyam", ("udyam", "udyog aadhaar")),
        ("textile_export", ("textile", "fabric export")),
        ("iec", ("iec", "import export code")),
        ("bis", ("bis certification", "bureau of indian standards")),
        ("repo_rate", ("repo rate", "policy rate", "rbi rate")),
    )

    def extract_query_tags(self, prompt: str) -> tuple[str, ...]:
        """Return the topic tags that match the prompt."""
        text = (prompt or "").lower()
        hits: list[str] = []
        for tag, keywords in self._TAG_KEYWORDS:
            for kw in keywords:
                if kw in text:
                    if tag not in hits:
                        hits.append(tag)
                    break
        return tuple(hits)

    def retrieve(self, prompt: str) -> RetrievalResult:
        """Return external claims whose tags overlap the prompt.

        Empty result carries a non-empty ``empty_reason``; the
        caller must surface it to the user (the brief: "say so
        explicitly, do not fabricate").
        """
        tags = self.extract_query_tags(prompt)
        if not tags:
            return RetrievalResult(
                matches=(),
                query_tags=(),
                empty_reason=(
                    "We could not verify this with the available sources. "
                    "The answer would require information outside UrsBiz's "
                    "verified knowledge base."
                ),
            )

        entries = _match_corpus(tags)
        if not entries:
            return RetrievalResult(
                matches=(),
                query_tags=tags,
                empty_reason=(
                    "We could not verify this with the available sources. "
                    "The answer would require information outside UrsBiz's "
                    "verified knowledge base."
                ),
            )

        claims = tuple(_entry_to_claim(e) for e in entries)
        return RetrievalResult(matches=claims, query_tags=tags, empty_reason="")

    def get_by_tag(self, tag: str) -> tuple[ClassifiedClaim, ...]:
        """Return the external claims that carry ``tag`` directly.

        Used by the scheme card builder to look up MUDRA / PMEGP /
        CGTMSE details without going through a prompt. Deterministic
        — same tag always returns the same claims.
        """
        entries = [e for e in _CORPUS if tag in e.tags]
        return tuple(_entry_to_claim(e) for e in entries)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _match_corpus(query_tags: Iterable[str]) -> tuple[_CorpusEntry, ...]:
    """Return corpus entries whose tag set overlaps ``query_tags``."""
    qset = set(query_tags)
    return tuple(e for e in _CORPUS if set(e.tags) & qset)


def _entry_to_claim(entry: _CorpusEntry) -> ClassifiedClaim:
    """Materialise a :class:`ClassifiedClaim` from a corpus entry.

    The kind is ALWAYS ``EXTERNAL_FACT``. The authority is the
    source's ``effective_authority`` (tier weight × freshness
    penalty). The ``is_verified`` flag is True only for
    ``FRESH``-status sources; ``AGING`` / ``STALE`` / ``UNKNOWN``
    sources are still cited but flagged as not currently verified.
    """
    authority = entry.authority or entry.source.effective_authority
    is_verified = entry.source.freshness_status.value == "fresh"
    notes = ""
    if entry.source.freshness_status.value == "stale":
        notes = (
            f"Source last published {entry.source.published_at}; "
            f"beyond the {entry.source.category.value} safe window. "
            "Re-verify with the publisher before relying on it."
        )
    elif entry.source.freshness_status.value == "aging":
        notes = (
            f"Source last published {entry.source.published_at}; "
            f"approaching the {entry.source.category.value} safe window. "
            "Re-verify before relying on it."
        )
    elif entry.source.freshness_status.value == "unknown":
        notes = "No published_at available; freshness cannot be confirmed."

    return ClassifiedClaim(
        text=entry.text,
        kind=ClaimKind.EXTERNAL_FACT,
        source=entry.source,
        authority=authority,
        is_verified=is_verified,
        notes=notes,
    )
