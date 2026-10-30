"""QuestionUnderstanding — SPRINT AI-1 universal assistant Stage 1.

Before the assistant can answer ANY business question, it must
first understand WHAT the user actually asked. The existing
:class:`~app.services.ai.providers.intent_router.QuestionIntent`
enum is a 6-way classification that neatly maps to the flagship
demo questions, but it is a **routing boundary today** — any
prompt that does not match a flagship keyword falls back to a
generic consultant template or, in the worst case, is rejected
as "unrecognized intent".

This module is the AI-1 fix. It introduces a richer
:class:`QuestionUnderstanding` dataclass that:

  * captures the literal question text,
  * assigns a coarse :attr:`topic` (finance / marketing / operations
    / hiring / export / strategy / education / risk / scenario /
    general) that the system can act on,
  * records the :class:`QuestionIntent` value the existing
    :func:`classify_intent` would have produced, as
    :attr:`relevant_existing_intents` (a tuple, since a prompt
    may overlap multiple intents and the legacy system used
    priority — we keep the same priority order here),
  * detects when the prompt is unambiguously non-business
    (:func:`is_purely_educational`) so the backend can auto-flip
    its internal mode to ``open`` while preserving the wire
    ``mode`` field the user picked,
  * records the **complexity** (simple / moderate / strategic /
    scenario) that the adaptive answer composer keys off,
  * records what the user wants the assistant to compute
    (:attr:`needs_calculations`) and which deterministic engines
    it should consult (:attr:`needs_deterministic_services`),
  * records what is unknown (:attr:`unknowns`) so the
    :class:`AdaptiveAnswer` composer can switch to a
    ``missing_info`` shell.

The dataclass is ``frozen=True`` so it can be safely shared
across the reasoning pipeline without defensive copying.

Backward-compatibility
----------------------

The five existing flagship intents remain reachable via
:attr:`relevant_existing_intents`. The existing
:func:`build_intent_frame` call sites are NOT changed — they
still call :func:`classify_intent` directly. ``QuestionUnderstanding``
is the AI-1 layer that **augments** the routing, not replaces
it. Prompts that match no flagship intent still get a useful
``topic`` (e.g. ``"marketing"``) and a useful ``complexity``
(e.g. ``"strategic"``), so the system never falls back to
"I don't recognize this intent."
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, TYPE_CHECKING

from app.services.ai.providers.intent_router import (
    QuestionIntent,
    classify_intent,
)

if TYPE_CHECKING:  # pragma: no cover - import-time only
    from app.services.ai.providers.base import AssistantContext


Complexity = Literal["simple", "moderate", "strategic", "scenario"]
Topic = Literal[
    "finance",
    "marketing",
    "operations",
    "hiring",
    "export",
    "strategy",
    "education",
    "risk",
    "scenario",
    "general",
]


# SPRINT AI-12 — Universal Reasoning Layer.
# 8-literal answer-mode vocabulary. Drives both the
# ``EvidenceRequirementPlanner`` and the answer-composer shell
# selection (the existing composer already picks from 4 shells;
# AI-12 adds 4 more: comparison / scheme / external / table_checklist).
AnswerMode = Literal[
    "general_knowledge",
    "business_analysis",
    "calculation",
    "scenario",
    "comparison",
    "scheme",
    "external",
    "mixed",
]


# --------------------------------------------------------------------------- #
# Topic heuristic
# --------------------------------------------------------------------------- #
#
# A keyword scan that maps a prompt to ONE coarse topic. The
# keyword lists are intentionally small and overlapping — the
# system never fails just because the prompt does not match a
# topic; it falls back to "general".
#
# Order matters: the first hit wins. Marketing is checked before
# finance because "selling more" overlaps with "make more
# revenue" — marketing is the more specific framing.

_FINANCE_KEYWORDS = (
    "loan", "funding", "credit", "cash", "cashflow", "cash flow",
    "working capital", "debt", "interest", "emi", "gst ",
    "tax", "taxes", "invoice", "invoicing", "margin", "gross margin",
    "revenue", "turnover", "pricing", "expense", "expenses",
    "profit", "loss", "break-even", "break even",
    "finance", "financial", "payments", "receivable",
)
_MARKETING_KEYWORDS = (
    "market", "marketing", "advertis", "brand", "branding",
    "social media", "instagram", "facebook ad", "google ad",
    "seo", "content marketing", "lead generation", "leads",
    "funnel", "awareness", "campaign", "promotion",
    "b2b marketing", "b2c marketing",
    "sell more", "sell online", "market my", "market our",
    "reach customers", "customer acquisition",
)
_OPERATIONS_KEYWORDS = (
    "inventory", "warehouse", "stock", "supply chain",
    "vendor", "supplier", "logistics", "shipping",
    "process", "operational", "operations", "efficiency",
    "bottleneck", "throughput", "production", "manufacturing",
    "quality", "lean", "six sigma", "automation",
)
_HIRING_KEYWORDS = (
    "hire", "hiring", "recruit", "recruitment", "interview",
    "onboarding", "employee", "employees", "staff",
    "workforce", "salary", "payroll", "compensation",
    "team", "talent", "headcount",
    "should i hire", "add an employee", "add staff",
)
_EXPORT_KEYWORDS = (
    "export", "exports", "international", "overseas",
    "foreign market", "global market", "ship abroad",
    "export market", "export expansion", "export readiness",
    "shipping abroad", "foreign buyer", "import",
)
_STRATEGY_KEYWORDS = (
    "strategy", "strategic", "plan", "roadmap", "playbook",
    "long-term", "long term", "vision", "goal", "goals",
    "growth", "grow", "scale", "competitive", "moat",
    "positioning", "differentiate", "pivot",
    "this month", "next quarter", "where should i focus",
    "creative ways", "three ways to grow",
    "analyze my entire business", "analyze my business",
)
_EDUCATION_KEYWORDS = (
    "what is", "what are", "explain", "define", "difference between",
    "how does", "how do", "meaning of", "tell me about",
    "compare", "vs ", "versus", "introduction to",
    "what does", "concept of", "teach me",
)
_RISK_KEYWORDS = (
    "risk", "risks", "risky", "danger", "weakness", "weak",
    "biggest problem", "biggest issue", "biggest risk",
    "main risk", "top risk", "what's wrong", "what is wrong",
    "gap in my", "concern", "bottleneck",
    "failing", "stuck", "downside", "threat",
)
_SCENARIO_KEYWORDS = (
    "what if", "what happens if", "what would happen if",
    "suppose", "scenario", "simulate", "simulation",
    "if my supplier", "if costs", "if revenue", "if demand",
    "if a competitor", "if i raise", "if i lower",
    "sensitivity", "best case", "worst case", "downside case",
)


@dataclass(frozen=True)
class QuestionUnderstanding:
    """Stage 1 output — structured understanding of the user prompt.

    Attributes
    ----------
    literal_question
        The raw prompt text (trimmed). Preserved so downstream
        renderers can echo the question verbatim when helpful.
    user_intent
        A short dotted path describing what the user wants
        (e.g. ``"operational.finance.working_capital"``). NOT
        used as a routing key — it is informational metadata for
        the prompt builder and the audit trail.
    topic
        Coarse topic bucket — one of the :data:`Topic` literals.
        Defaults to ``"general"`` when no keyword matches.
    is_business_specific
        True when the prompt references the user's own business
        (uses ``"my"``, ``"our"``, ``"I should"``, the profile
        industry, location, etc.). False for purely educational
        questions.
    is_purely_educational
        True when the prompt is explain / define / compare
        against a non-business subject matter. Determined by
        :func:`is_purely_educational`. Used by the backend to
        auto-flip its internal ``_effective_mode`` to ``"open"``
        while the wire ``mode`` stays as the user picked.
    needs_calculations
        Calculation labels the user implicitly asked for. One
        of ``"gap_math"``, ``"growth_multiple"``, ``"roi"``,
        ``"working_capital"``, ``"headcount_cost"``,
        ``"scenario_delta"``. Empty tuple when no calculation is
        needed.
    needs_deterministic_services
        Service names the assistant should consult. Reuses the
        existing service names from the deterministic pool
        (``"health_score"``, ``"recommendation"``,
        ``"schemes_sprint16"``, ``"finance"``,
        ``"knowledge_retrieval"``, ``"business_dna"``,
        ``"risk"``, ``"insights"``). Empty tuple when no
        service is needed.
    unknowns
        Context fields the assistant would need to answer this
        question well but the user has not provided. Drives the
        ``missing_info`` shell in the adaptive answer composer.
    relevant_existing_intents
        The :class:`QuestionIntent` values the existing
        classifier would have produced. Always at least one
        element (the default is ``QuestionIntent.GENERAL``).
        Order is priority order so the prompt builder can pick
        the first as the primary framing.
    sentiment
        ``"neutral"`` / ``"concerned"`` / ``"optimistic"`` —
        simple keyword scan. Defaults to ``"neutral"``.
    complexity
        One of ``"simple"``, ``"moderate"``, ``"strategic"``,
        ``"scenario"``. The adaptive answer composer keys off
        this to pick a shell.
    parsed_at
        ISO-8601 timestamp of when the understanding was
        produced. Useful for the audit trail.
    """

    literal_question: str
    user_intent: str
    topic: Topic
    is_business_specific: bool
    is_purely_educational: bool
    needs_calculations: tuple[str, ...] = field(default_factory=tuple)
    needs_deterministic_services: tuple[str, ...] = field(default_factory=tuple)
    unknowns: tuple[str, ...] = field(default_factory=tuple)
    relevant_existing_intents: tuple[QuestionIntent, ...] = field(default_factory=tuple)
    sentiment: str = "neutral"
    complexity: Complexity = "moderate"
    # SPRINT AI-11 — Universal Business-Aware Assistant hardening.
    # Additive fields that describe what capabilities the question
    # requires and how strongly it depends on the user's business
    # data. Both default to safe empty / NONE values so every
    # pre-AI-11 call site keeps working unchanged.
    capability: tuple[str, ...] = field(default_factory=tuple)
    business_dependency: str = "none"
    # SPRINT AI-12 — Universal Reasoning Layer. Eight more
    # additive fields that drive the tool planner / evidence
    # requirement planner / adaptive answer shell. All default
    # to safe empty / False / ``"general_knowledge"`` so every
    # pre-AI-12 call site (and every pre-AI-12 frozen dataclass
    # stored on disk) deserialises unchanged. Field is appended
    # at the END to preserve the additive-compat pattern of
    # every AI-N sprint.
    required_evidence_types: tuple[str, ...] = field(default_factory=tuple)
    required_tools: tuple[str, ...] = field(default_factory=tuple)
    requires_calculation: bool = False
    requires_scenario_analysis: bool = False
    requires_forecast: bool = False
    requires_external_information: bool = False
    answer_mode: str = "general_knowledge"
    expected_output_sections: tuple[str, ...] = field(default_factory=tuple)
    parsed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        """Serialize for the GenerationMeta audit envelope.

        Tuples become lists and the :attr:`relevant_existing_intents`
        enum tuple becomes a list of ``.value`` strings so the
        payload is JSON-serialisable without leaking the enum
        type. Used by the service when stamping the wire
        envelope.
        """
        return {
            "literal_question": self.literal_question,
            "user_intent": self.user_intent,
            "topic": self.topic,
            "is_business_specific": self.is_business_specific,
            "is_purely_educational": self.is_purely_educational,
            "needs_calculations": list(self.needs_calculations),
            "needs_deterministic_services": list(self.needs_deterministic_services),
            "unknowns": list(self.unknowns),
            "relevant_existing_intents": [
                intent.value for intent in self.relevant_existing_intents
            ],
            "sentiment": self.sentiment,
            "complexity": self.complexity,
            "capability": list(self.capability),
            "business_dependency": self.business_dependency,
            # SPRINT AI-12 — Universal Reasoning Layer wire
            # projection. Mirrors the 8 additive dataclass fields
            # so the GenerationMeta envelope carries the
            # capability-aware reasoning trace.
            "required_evidence_types": list(self.required_evidence_types),
            "required_tools": list(self.required_tools),
            "requires_calculation": self.requires_calculation,
            "requires_scenario_analysis": self.requires_scenario_analysis,
            "requires_forecast": self.requires_forecast,
            "requires_external_information": self.requires_external_information,
            "answer_mode": self.answer_mode,
            "expected_output_sections": list(self.expected_output_sections),
            "parsed_at": self.parsed_at,
        }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _first_match(text: str, keywords: tuple[str, ...]) -> bool:
    """Return True iff any keyword appears as a substring of ``text``."""
    for kw in keywords:
        if kw in text:
            return True
    return False


def _detect_topic(text: str) -> Topic:
    """Return the coarse topic for the prompt (default ``"general"``)."""
    # Order matters: more specific topics first.
    if _first_match(text, _RISK_KEYWORDS):
        return "risk"
    if _first_match(text, _SCENARIO_KEYWORDS):
        return "scenario"
    if _first_match(text, _HIRING_KEYWORDS):
        return "hiring"
    if _first_match(text, _EXPORT_KEYWORDS):
        return "export"
    if _first_match(text, _MARKETING_KEYWORDS):
        return "marketing"
    if _first_match(text, _OPERATIONS_KEYWORDS):
        return "operations"
    if _first_match(text, _FINANCE_KEYWORDS):
        return "finance"
    if _first_match(text, _STRATEGY_KEYWORDS):
        return "strategy"
    if _first_match(text, _EDUCATION_KEYWORDS):
        return "education"
    return "general"


def _is_business_specific(prompt: str, context: Any) -> bool:
    """True when the prompt references the user's own business.

    Heuristic — keep it cheap. Returns True when:

      * the prompt uses a possessive pronoun (``my``, ``our``),
      * or asks ``should I`` / ``what should I``,
      * or contains an industry / location / business-type
        keyword from the context,
      * or contains a flagship keyword (the existing
        intent classifier would have matched).

    Returns False for purely educational prompts.
    """
    text = (prompt or "").lower()
    if not text.strip():
        return False

    # Possessive or first-person phrasing
    if re.search(
        r"\b(my|our|me|us|i should|we should|should i|should we|can i|can we|could i|could we|how can i|how can we|how do i|how do we|how should i|how should we|i am|we are|help me|help us)\b",
        text,
    ):
        return True

    # Cross-check against the existing classifier — if the
    # flagship router matched, the prompt is implicitly
    # business-specific.
    # Sprint AI-21 — the legacy GOVERNMENT_SCHEMES intent
    # fires for any prompt with "scheme/subsidy/mudra"
    # keyword, but the brief explicitly classifies
    # "What government scheme is available?" as EXTERNAL.
    # The intent-bridge check is too aggressive for the
    # scheme + export families — suppress the bridge for
    # those intents ONLY when the prompt carries no
    # personalisation tokens. A prompt like "Are there
    # schemes that can help me buy machinery?" still has
    # "me" → business-specific (the bridge would have
    # flipped it but the suppression would have undone
    # that — we keep the personalisation).
    intent = classify_intent(prompt)
    if intent is QuestionIntent.GENERAL:
        pass
    elif intent in (
        QuestionIntent.GOVERNMENT_SCHEMES,
        QuestionIntent.EXPORT_EXPANSION,
    ):
        # External family — keep external unless the
        # prompt carries personalisation tokens (already
        # handled above).
        pass
    elif intent is not None:
        return True

    # Match against known context fields when available
    industry = getattr(context, "industry", None) if context is not None else None
    location = getattr(context, "location", None) if context is not None else None
    business_type = getattr(context, "business_type", None) if context is not None else None
    for token in (industry, location, business_type):
        if token and isinstance(token, str) and token.strip() and token.strip().lower() in text:
            return True

    return False


# Heuristic keywords that classify a prompt as "purely educational"
# — i.e. asking what something MEANS rather than what to do.
_EDUCATIONAL_OPENERS = (
    "what is", "what are", "what does", "what do",
    "explain", "define", "meaning of", "tell me about",
    "difference between", "how does", "how do",
    "compare ", "vs ", "versus", "introduction to",
)
# Topics that are always non-business — used to detect
# educational prompts that are NOT about the user's MSME.
_NON_BUSINESS_SUBJECTS = (
    "photosynthesis", "quantum", "philosophy", "religion",
    "recipe", "cooking", "astrology", "history of",
    "mathematics", "calculus", "algebra", "biology",
    "chemistry", "physics", "literature", "poetry",
    "movie", "film", "song", "lyrics", "game",
    "sports", "football", "cricket", "tennis",
)


def is_purely_educational(prompt: str) -> bool:
    """True when the prompt asks a concept-level question.

    The check is permissive: it returns True only when the prompt
    opens with an explainer opener AND is not business-specific.

    A prompt is "business-specific" only when it uses a
    possessive / first-person marker OR a directive marker
    ("should I", "recommend"). The mere presence of a business
    topic (e.g. "marketing", "GST", "working capital") does NOT
    flip an educational prompt to business-specific — the
    assistant should still be able to define the term.

    Edge cases handled:

      * "What is working capital?" — True (concept question, no
        business-specific markers).
      * "What is my working capital gap?" — False (possessive).
      * "What is a marketing funnel?" — True.
      * "What is the best marketing funnel for my business?" —
        False (possessive "my").
      * "Should I hire five employees?" — False (directive).
      * "" or None — False.
      * "Explain the difference between marketing and
        advertising." — True (no possessive / directive).
      * "Define GST." — True.
    """
    text = (prompt or "").lower().strip()
    if not text:
        return False

    # An imperative / directive phrase flips the prompt to
    # business-specific (the user is asking for advice).
    if re.search(r"\bshould i\b", text):
        return False
    # "Tell me about" / "Give me" / "Recommend" — directive
    if re.search(r"\b(tell me|give me|recommend|suggest)\b", text):
        return False

    # Possessive / first-person marker — the user is asking
    # about their own business (even if the topic is generic).
    if re.search(r"\b(my|our|i should|we should|i am|we are)\b", text):
        return False

    # Must start with an educational opener
    if not any(text.startswith(opener) for opener in _EDUCATIONAL_OPENERS):
        return False

    # If the prompt references a clearly non-business subject,
    # treat it as purely educational.
    if any(s in text for s in _NON_BUSINESS_SUBJECTS):
        return True

    # Default: a prompt that opens with an educational opener
    # and lacks any business-specific marker is purely
    # educational. This is the "What is working capital?" case.
    return True


def _detect_complexity(prompt: str, topic: Topic) -> Complexity:
    """Classify the prompt's complexity.

    Heuristic order:

      * scenario keywords → ``"scenario"``,
      * strategy / multi-intent / creative-thinking keywords → ``"strategic"``,
      * educational / explainer / definition → ``"simple"``,
      * otherwise ``"moderate"``.
    """
    text = (prompt or "").lower()
    if _first_match(text, _SCENARIO_KEYWORDS):
        return "scenario"
    if _first_match(text, _STRATEGY_KEYWORDS):
        return "strategic"
    # Educational / definition prompts are simple regardless of
    # which topic bucket they fall into (a topic that itself
    # came from a keyword like "working capital" still wins the
    # topic slot, but the complexity is the underlying question
    # type — asking what something is).
    if topic == "education" or _first_match(text, _EDUCATION_KEYWORDS):
        return "simple"
    return "moderate"


def _detect_needs_calculations(topic: Topic, prompt: str) -> tuple[str, ...]:
    """Return calculation labels the user implicitly asked for.

    The labels are NOT computed here — they are typed strings
    that the prompt builder can use to tell the LLM which
    numbers to show. The LLM itself never does the math; the
    deterministic engines produce the numbers and the
    assistant cites them.
    """
    text = (prompt or "").lower()
    needs: list[str] = []
    if "gap" in text or "reach" in text or "target" in text or "scale to" in text or "grow to" in text or "hit " in text or "crore" in text or "cr" in text:
        needs.append("gap_math")
    if "growth multiple" in text or "multiple" in text:
        needs.append("growth_multiple")
    if "roi" in text or "return on investment" in text:
        needs.append("roi")
    if "working capital" in text or "cash flow" in text or "cashflow" in text:
        needs.append("working_capital")
    if topic == "hiring" or "salary" in text or "payroll" in text:
        needs.append("headcount_cost")
    if topic == "scenario" or "scenario" in text or "if my" in text:
        needs.append("scenario_delta")
    return tuple(needs)


def _detect_needs_services(
    topic: Topic, prompt: str, context: Any
) -> tuple[str, ...]:
    """Return deterministic service names the prompt authorises.

    Defaults to the four most-used services. Adding more is
    free — the dispatcher caps at 5 tool calls per request.
    """
    text = (prompt or "").lower()
    services: list[str] = []

    # Knowledge retrieval is useful for nearly every prompt
    services.append("knowledge_retrieval")

    # Topic-keyed services
    if topic == "finance":
        services.append("finance")
    if topic in {"strategy", "scenario", "general"}:
        services.append("health_score")
        services.append("recommendation")
    if topic == "risk":
        services.append("risk")
    if topic == "export":
        services.append("schemes_sprint16")
    if "scheme" in text or "subsidy" in text or "mudra" in text or "pmegp" in text:
        services.append("schemes_sprint16")
    if topic == "hiring":
        services.append("finance")
    if topic == "marketing":
        services.append("insights")
    if topic == "operations":
        services.append("risk")

    # Dedupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for s in services:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return tuple(out)


def _detect_unknowns(
    topic: Topic, prompt: str, context: Any
) -> tuple[str, ...]:
    """Return context fields the assistant would want but does not have.

    Drives the ``missing_info`` shell in the adaptive answer
    composer. The list is intentionally short — three items
    max — so the trailing "what to provide next" section stays
    actionable.
    """
    unknowns: list[str] = []

    if context is None:
        return ("business_profile", "industry", "annual_revenue")

    if not getattr(context, "industry", None) or getattr(context, "industry", "") == "unknown":
        unknowns.append("industry")
    if not getattr(context, "annual_revenue_inr", None):
        unknowns.append("annual_revenue")
    if not getattr(context, "target_revenue_inr", None) and topic in {"strategy", "finance", "scenario"}:
        unknowns.append("target_revenue")
    if topic == "export" and not getattr(context, "certifications", None):
        unknowns.append("certifications")
    if topic == "hiring" and not getattr(context, "employee_count", None):
        unknowns.append("employee_count")

    return tuple(unknowns[:3])


def _detect_sentiment(text: str) -> str:
    """Return ``"concerned"`` / ``"optimistic"`` / ``"neutral"``."""
    if not text:
        return "neutral"
    negative = (
        "worried", "concerned", "anxious", "afraid",
        "struggling", "losing", "failing", "stuck",
        "problem", "issue", "wrong", "bad", "down",
    )
    positive = (
        "excited", "optimistic", "great", "amazing",
        "growing", "booming", "thriving", "love",
        "winning", "succeed", "success",
    )
    if any(w in text for w in negative):
        return "concerned"
    if any(w in text for w in positive):
        return "optimistic"
    return "neutral"


def _build_user_intent_string(topic: Topic, prompt: str) -> str:
    """Build a short dotted path describing the user intent."""
    text = (prompt or "").lower().strip()
    # Specific intent sub-paths for the most common topic buckets
    if topic == "finance":
        if "working capital" in text or "cash flow" in text:
            return "operational.finance.working_capital"
        if "loan" in text or "funding" in text:
            return "operational.finance.funding"
        if "pricing" in text or "margin" in text:
            return "operational.finance.pricing"
        return "operational.finance.general"
    if topic == "marketing":
        if "b2b" in text:
            return "operational.marketing.b2b"
        if "online" in text or "digital" in text:
            return "operational.marketing.digital"
        return "operational.marketing.general"
    if topic == "operations":
        if "vendor" in text or "supplier" in text:
            return "operational.operations.vendor"
        if "inventory" in text or "stock" in text:
            return "operational.operations.inventory"
        return "operational.operations.general"
    if topic == "hiring":
        return "operational.hiring.workforce"
    if topic == "export":
        return "strategic.export.international"
    if topic == "risk":
        return "diagnostic.risk.weakness"
    if topic == "scenario":
        return "diagnostic.scenario.simulation"
    if topic == "strategy":
        if "this month" in text or "next month" in text:
            return "strategic.planning.immediate"
        return "strategic.planning.general"
    if topic == "education":
        return "educational.concept.explanation"
    return "general.business.advice"


# --------------------------------------------------------------------------- #
# SPRINT AI-11 — capability + business_dependency derivation.
#
# These two fields are additive (defaults are empty tuple / "none")
# so every pre-AI-11 call site keeps working unchanged. The
# derivation reuses the existing topic + complexity + is_business_specific
# flags; it does NOT introduce a new keyword scan of its own.
# --------------------------------------------------------------------------- #


# The list mirrors the brief's §4 capability vocabulary. A prompt
# can match more than one (e.g. "Explain EBITDA AND tell me
# whether mine is healthy" → GENERAL_KNOWLEDGE + BUSINESS_ANALYSIS).
# When ≥ 2 capabilities fire AND they cross the general/business
# boundary, the builder rolls up to MIXED.
_ALLOWED_CAPABILITIES: tuple[str, ...] = (
    "GENERAL_KNOWLEDGE",
    "BUSINESS_FACT",
    "BUSINESS_ANALYSIS",
    "CALCULATION",
    "RECOMMENDATION",
    "SCENARIO",
    "FORECAST",
    "COMPARISON",
    "FINANCIAL",
    "OPERATIONAL",
    "RISK",
    "GOVERNMENT_SCHEME",
    "EXPORT",
    "ROADMAP",
    "EXTERNAL_INFORMATION",
    "MIXED",
    "UNKNOWN",
)


def _detect_capability(
    *,
    lower: str,
    topic: str,
    is_business_specific: bool,
    is_purely_educational: bool,
    complexity: str,
) -> tuple[str, ...]:
    """Return the capability tuple for the prompt.

    Deterministic: same inputs → same tuple. Order is stable
    (the list below defines priority — first match wins the
    slot, but multiple slots can fire).

    Algorithm
    ---------
    1. Start with the topic → base capability mapping.
    2. Add overlays for explicit comparison / forecast /
       calculation phrasing so those surface even when the
       topic is "education" (e.g. "compare my margin to the
       industry average" → topic=education BUT
       capability=COMPARISON+FINANCIAL).
    3. If is_purely_educational AND not is_business_specific,
       prepend GENERAL_KNOWLEDGE so the renderer can label the
       answer's trust category correctly.
    4. If the prompt references an external / general source
       ("common ways …", "industry best practice …",
       "what is …", "explain …") AND references the user's own
       data, fire MIXED — the renderer renders general knowledge
       + business evidence side-by-side.
    5. If no slot fires, default to UNKNOWN so the renderer
       never leaves the user staring at a blank trust label.
    """
    caps: list[str] = []

    # 1. topic → base capability.
    _TOPIC_TO_CAPABILITY: dict[str, str] = {
        "finance": "FINANCIAL",
        "marketing": "BUSINESS_ANALYSIS",
        "operations": "OPERATIONAL",
        "hiring": "OPERATIONAL",
        "export": "EXPORT",
        "strategy": "BUSINESS_ANALYSIS",
        "education": "GENERAL_KNOWLEDGE",
        "risk": "RISK",
        "scenario": "SCENARIO",
        "general": "BUSINESS_ANALYSIS",
    }
    base = _TOPIC_TO_CAPABILITY.get(topic)
    if base and base not in caps:
        caps.append(base)

    # 2. overlays — these can fire ON TOP OF the topic-based
    # capability. Each overlay is a strict keyword cluster; the
    # cluster is intentionally narrow to avoid over-firing.
    if any(
        k in lower
        for k in ("compare", "vs ", "versus", "difference between")
    ):
        if "COMPARISON" not in caps:
            caps.append("COMPARISON")
    if any(
        k in lower
        for k in (
            "forecast", "predict", "projection", "next year", "next quarter",
            # Sprint AI-21 — synonym coverage for FORECAST.
            "trajectory", "expected revenue", "projected order",
            "outlook", "projected", "next 18 months",
            "18 months out", "next month revenue",
        )
    ):
        if "FORECAST" not in caps:
            caps.append("FORECAST")
    if any(
        k in lower
        for k in (
            "calculate", "compute", "what is my", "percentage", "%", "growth rate",
            # Sprint AI-21 — synonym coverage for CALCULATION.
            "growth multiple", "by how much", "how much must we",
            "how much working capital", "how much cash",
            "how much revenue", "how much do we need",
            "how many employees", "how many can we",
            "how many senior", "how many workers",
            "runway", "burn rate", "multiple between",
        )
    ):
        if "CALCULATION" not in caps:
            caps.append("CALCULATION")
    if any(
        k in lower
        for k in (
            "scheme", "schemes", "subsidy", "msme", "udyam",
            "eligibility", "eligible",
        )
    ):
        if "GOVERNMENT_SCHEME" not in caps:
            caps.append("GOVERNMENT_SCHEME")
    if any(
        k in lower
        for k in (
            "roadmap", "12 month", "twelve month", "12-month",
            "playbook", "this month", "next month", "this quarter",
        )
    ):
        if "ROADMAP" not in caps:
            caps.append("ROADMAP")
    if any(
        k in lower
        for k in (
            "recommend", "suggestion", "should i", "how can i",
            "ways to", "how do i",
            # Sprint AI-21 — synonym + follow-up coverage.
            "what should we focus", "what should we tackle",
            "most impactful", "move the needle",
            "next 30 days", "which single move",
            "where should we", "what do you suggest",
            "what's the most impactful",
        )
    ):
        if "RECOMMENDATION" not in caps:
            caps.append("RECOMMENDATION")
    if any(
        k in lower
        for k in (
            "how many", "what is my employee", "do i have", "my employees",
            # Sprint AI-21 — pronoun coverage. The original
            # trigger only matched "my" — extend to "our",
            # "we", "us", "the company", "the firm", "the
            # business" so prompts like "What's our current
            # headcount?" or "What is our annual revenue?"
            # surface ``BUSINESS_FACT`` instead of dropping
            # to the topic-derived BUSINESS_ANALYSIS.
            "our", "we are", "our team", "our company",
            "our business", "our revenue", "our headcount",
            "our employees", "our score", "our industry",
            "our location", "our company name",
            "company name", "legal name", "where is",
            "how many", "headcount", "employee count",
        )
    ):
        if "BUSINESS_FACT" not in caps:
            caps.append("BUSINESS_FACT")
    if any(
        k in lower
        for k in (
            "external", "industry", "industry best", "industry average",
            "common ways", "best practice", "typical",
        )
    ):
        if "EXTERNAL_INFORMATION" not in caps:
            caps.append("EXTERNAL_INFORMATION")
    if complexity == "scenario":
        if "SCENARIO" not in caps:
            caps.append("SCENARIO")
    # Sprint AI-21 — RISK overlay for prompts that don't
    # trip the topic heuristic but carry risk meaning
    # (over-exposed, currency swings, customer concentration,
    # commodity shocks, regulatory changes, etc.).
    if any(
        k in lower
        for k in (
            "exposed", "exposure", "currency swings", "currency swing",
            "customer concentration", "over-reliant", "single customer",
            "regulatory changes", "commodity price", "commodity shock",
            "resilient", "resilience", "vulnerable", "vulnerability",
            "if a competitor", "customer churn",
        )
    ):
        if "RISK" not in caps:
            caps.append("RISK")
    # Sprint AI-21 — OPERATIONAL overlay for prompts that
    # don't trip the topic heuristic but carry operational
    # meaning (over-staffed, productivity, inventory turnover,
    # throughput, etc.).
    if any(
        k in lower
        for k in (
            "over-staffed", "under-staffed", "staffed",
            "productivity", "inventory turnover", "throughput",
            "lose the most time", "bottleneck", "headcount",
            "warehouse", "logistics",
        )
    ):
        if "OPERATIONAL" not in caps:
            caps.append("OPERATIONAL")

    # 3. prepend GENERAL_KNOWLEDGE when the prompt is purely
    # educational AND not about the user's business.
    if is_purely_educational and not is_business_specific:
        if "GENERAL_KNOWLEDGE" not in caps:
            caps.insert(0, "GENERAL_KNOWLEDGE")

    # 4. rollup to MIXED when ≥ 2 capabilities cross the
    # general/business boundary.
    _GENERAL = {"GENERAL_KNOWLEDGE", "EXTERNAL_INFORMATION", "UNKNOWN"}
    _BUSINESS = {
        "BUSINESS_FACT", "BUSINESS_ANALYSIS", "CALCULATION", "RECOMMENDATION",
        "SCENARIO", "FORECAST", "COMPARISON", "FINANCIAL", "OPERATIONAL",
        "RISK", "GOVERNMENT_SCHEME", "EXPORT", "ROADMAP",
    }
    general_hits = [c for c in caps if c in _GENERAL]
    business_hits = [c for c in caps if c in _BUSINESS]
    if general_hits and business_hits and "MIXED" not in caps:
        caps.append("MIXED")

    # 5. default fallback.
    if not caps:
        caps.append("UNKNOWN")

    # Filter to the allowed vocabulary (defensive — guards
    # against typos in the topic-mapping above).
    return tuple(c for c in caps if c in _ALLOWED_CAPABILITIES)


def _detect_business_dependency(
    *,
    lower: str,
    is_business_specific: bool,
    is_purely_educational: bool,
    capability: tuple[str, ...],
) -> str:
    """Return ``"required"``, ``"optional"``, or ``"none"``.

    The brief's contract:

      * **REQUIRED** — the question cannot be answered without
        the user's business data (e.g. "How many employees
        do I have?", "What is my EBITDA?").
      * **OPTIONAL** — the question can be answered from
        general knowledge, but business data would
        personalise the answer (e.g. "Common ways textile
        companies reduce working capital", "What are three
        ways I can reduce electricity costs?").
      * **NONE** — the question is pure general knowledge
        (e.g. "What is EBITDA?", "Explain working capital").
    """
    # Explicit business-specific phrasing → REQUIRED.
    if is_business_specific:
        return "required"

    # Capability-driven override: capabilities that always need
    # business data even when the prompt doesn't use "my/our/I".
    # The check intentionally SKIPS the override when
    # ``EXTERNAL_INFORMATION`` is also present — the question is
    # framed as industry / common-practice, so business data is
    # an optional personalisation, not a hard requirement.
    # Sprint AI-21 — the brief's "What government scheme is
    # available?" → EXTERNAL semantics removes
    # ``GOVERNMENT_SCHEME`` and ``FORECAST`` from the override
    # set. Both can be answered from external knowledge
    # without the user's business data; the user's profile
    # only personalises the answer.
    _REQUIRES_BUSINESS = {
        "BUSINESS_FACT", "CALCULATION", "RECOMMENDATION",
        "SCENARIO", "COMPARISON",
    }
    if "EXTERNAL_INFORMATION" not in capability and any(
        c in _REQUIRES_BUSINESS for c in capability
    ):
        return "required"

    # Mixed → OPTIONAL (general knowledge can answer, business
    # data would refine).
    if "MIXED" in capability:
        return "optional"

    # External industry / best-practice phrasing → OPTIONAL.
    if "EXTERNAL_INFORMATION" in capability:
        return "optional"

    # Purely educational OR explicitly general-knowledge →
    # NONE.
    if is_purely_educational or "GENERAL_KNOWLEDGE" in capability:
        return "none"

    return "none"


# --------------------------------------------------------------------------- #
# SPRINT AI-12 — Universal Reasoning Layer derivation.
#
# Six new fields on ``QuestionUnderstanding`` (plus answer_mode +
# expected_output_sections). All derived deterministically from the
# existing ``capability`` tuple (AI-11) plus the same lowercase prompt
# string + topic the rest of the module already uses. No new keyword
# scan of its own beyond a thin capability → tool-table lookup.
# --------------------------------------------------------------------------- #


# Capability → primary tools table. Drives ``required_tools`` and
# (indirectly, via ``EvidenceRequirementPlanner``) the
# ``required_evidence_types`` field. Matches the plan's §3 matrix.
_CAPABILITY_TO_PRIMARY_TOOLS: dict[str, tuple[str, ...]] = {
    "GENERAL_KNOWLEDGE": ("knowledge_retrieval",),
    "BUSINESS_ANALYSIS": ("health_score", "kpi", "insights"),
    "FINANCIAL": ("finance", "kpi"),
    "OPERATIONAL": ("health_score", "risk", "readiness"),
    "RISK": ("risk", "insights"),
    "SCENARIO": ("predictive_sprint14", "scenario"),
    "FORECAST": ("predictive_sprint14",),
    "CALCULATION": ("finance", "kpi"),
    "COMPARISON": ("compare_recommendations", "benchmark"),
    "RECOMMENDATION": ("recommendation", "insights"),
    "GOVERNMENT_SCHEME": ("schemes_sprint16", "funding"),
    "EXPORT": ("schemes_sprint16", "compliance", "knowledge_retrieval"),
    "ROADMAP": ("roadmap", "recommendation"),
    "EXTERNAL_INFORMATION": ("knowledge_retrieval", "compliance"),
    "BUSINESS_FACT": ("kpi",),
    "MIXED": (),
    "UNKNOWN": (),
}


# Sprint AI-20 — tool-minimality closure.
# Per-capability list of tools that must NEVER be in
# ``required_tools`` for that capability. The QU builder
# filters these out of ``required_tools`` before the
# planner emits the ToolPlan. Examples from the brief:
#   * GENERAL_KNOWLEDGE prompts must not call finance,
#     schemes, or forecast tools.
#   * GOVERNMENT_SCHEME prompts must not call forecast
#     or finance tools.
#   * SCENARIO prompts must not call scheme/roadmap
#     tools.
# An empty tuple means "no exclusions beyond the
# primary-tools table". Closed allow-list — adding a new
# capability without an explicit exclusions tuple
# defaults to safe behaviour (no exclusions applied).
_CAPABILITY_TO_EXCLUDED_TOOLS: dict[str, tuple[str, ...]] = {
    "GENERAL_KNOWLEDGE": (
        "finance",
        "schemes_sprint16",
        "funding",
        "predictive_sprint14",
        "scenario",
        "recommendation",
        "risk",
        "benchmark",
        "compare_recommendations",
        "compliance",
    ),
    "BUSINESS_FACT": (
        "predictive_sprint14",
        "scenario",
        "schemes_sprint16",
        "funding",
    ),
    "BUSINESS_ANALYSIS": (
        "schemes_sprint16",
        "funding",
        "predictive_sprint14",
        "scenario",
    ),
    "FINANCIAL": (
        "schemes_sprint16",
        "funding",
        "predictive_sprint14",
        "scenario",
    ),
    "CALCULATION": (
        "schemes_sprint16",
        "funding",
        "predictive_sprint14",
        "scenario",
    ),
    "SCENARIO": (
        "schemes_sprint16",
        "funding",
        "compliance",
        "roadmap",
        "benchmark",
    ),
    "FORECAST": (
        "schemes_sprint16",
        "funding",
        "compliance",
        "roadmap",
    ),
    "RECOMMENDATION": (
        "predictive_sprint14",
        "scenario",
        "schemes_sprint16",
        "funding",
    ),
    "RISK": (
        "schemes_sprint16",
        "funding",
        "predictive_sprint14",
    ),
    "OPERATIONAL": (
        "schemes_sprint16",
        "funding",
        "predictive_sprint14",
        "scenario",
    ),
    "COMPARISON": (
        "schemes_sprint16",
        "funding",
        "predictive_sprint14",
        "scenario",
    ),
    "GOVERNMENT_SCHEME": (
        "predictive_sprint14",
        "scenario",
        "finance",
        "benchmark",
        "compare_recommendations",
    ),
    "EXPORT": (
        "predictive_sprint14",
        "scenario",
        "finance",
    ),
    "ROADMAP": (
        "schemes_sprint16",
        "funding",
        "predictive_sprint14",
        "scenario",
    ),
    "EXTERNAL_INFORMATION": (
        "finance",
        "predictive_sprint14",
        "scenario",
        "schemes_sprint16",
        "funding",
    ),
    # MIXED, UNKNOWN — no exclusions; the union of
    # per-sub-question required_tools is the answer.
    "MIXED": (),
    "UNKNOWN": (),
}


# Sprint AI-20 — tools that improve the answer but are
# not strictly required. The QU does NOT include these
# in ``required_tools``; the planner surfaces them as
# ``ToolPlan.optional`` when the upstream
# ``applicable_deterministic_services`` carries them.
_CAPABILITY_TO_OPTIONAL_TOOLS: dict[str, tuple[str, ...]] = {
    "GENERAL_KNOWLEDGE": ("insights",),
    "BUSINESS_FACT": ("health_score",),
    "BUSINESS_ANALYSIS": ("benchmark",),
    "FINANCIAL": ("insights",),
    "CALCULATION": ("health_score",),
    "RECOMMENDATION": ("health_score",),
    "RISK": ("health_score",),
    "OPERATIONAL": ("benchmark",),
    "GOVERNMENT_SCHEME": ("compliance",),
    "EXPORT": ("benchmark",),
    "ROADMAP": ("benchmark",),
    "EXTERNAL_INFORMATION": (),
    "SCENARIO": ("finance",),
    "FORECAST": ("finance",),
    "COMPARISON": ("recommendation",),
    "MIXED": (),
    "UNKNOWN": (),
}

# Capability → expected output sections. Drives the answer-shell
# decision (mirrored by ``AdaptiveAnswer.mode_used``). The composer
# falls back to ``"expanded"`` for any unmapped capability.
_CAPABILITY_TO_OUTPUT_SECTIONS: dict[str, tuple[str, ...]] = {
    "GENERAL_KNOWLEDGE": ("definition", "why_it_matters", "example", "business_relevance"),
    "BUSINESS_ANALYSIS": ("executive_summary", "key_findings", "evidence", "analysis", "recommendations", "risks", "next_actions"),
    "CALCULATION": ("result", "inputs", "calculation", "interpretation", "assumptions"),
    "SCENARIO": ("baseline", "changes", "estimated_effects", "risks", "unknowns"),
    "COMPARISON": ("option_a", "option_b", "comparison", "best_fit", "trade_offs"),
    "GOVERNMENT_SCHEME": ("scheme", "eligibility", "match_reason", "benefits", "evidence", "application", "unknowns"),
    "EXTERNAL_INFORMATION": ("answer", "source_context", "business_relevance", "what_is_known", "what_requires_verification"),
}


def _detect_reasoning_metadata(
    *,
    lower: str,
    topic: str,
    is_business_specific: bool,
    is_purely_educational: bool,
    complexity: str,
    capability: tuple[str, ...],
) -> dict[str, Any]:
    """Return the AI-12 additive fields as a dict.

    Returns:
        A dict with keys:
          ``required_evidence_types`` (tuple[str, ...]),
          ``required_tools`` (tuple[str, ...]),
          ``requires_calculation`` (bool),
          ``requires_scenario_analysis`` (bool),
          ``requires_forecast`` (bool),
          ``requires_external_information`` (bool),
          ``answer_mode`` (str),
          ``expected_output_sections`` (tuple[str, ...]).

    Algorithm:
      1. Aggregate primary tools across the multi-label capability
         tuple (de-duped, order-preserved).
      2. Aggregate required evidence types across the
         capability tuple using the same table the
         ``EvidenceRequirementPlanner`` uses — keeps QU and
         the planner in lockstep.
      3. Set ``requires_*`` flags from capability membership.
      4. Pick an ``answer_mode`` from a deterministic priority
         list — the FIRST capability that maps to a non-empty
         tool table wins. ``MIXED`` is the fallback when 2+
         capabilities cross answer-shape boundaries.
      5. ``expected_output_sections`` keys off the picked
         ``answer_mode``.

    Side-effect free. Same inputs ⇒ same output.
    """
    # 1. aggregate primary tools.
    seen_tools: set[str] = set()
    ordered_tools: list[str] = []
    # Sprint AI-20 — tool-minimality closure. Per-capability
    # exclusions are scoped to the primary tools each
    # capability contributes (not the union) so a
    # multi-label capability tuple like
    # ``(GOVERNMENT_SCHEME, EXTERNAL_INFORMATION)`` keeps
    # ``schemes_sprint16`` from GOVERNMENT_SCHEME without
    # it being filtered out by EXTERNAL_INFORMATION's
    # cross-capability exclusion list.
    for cap in capability:
        excluded = set(
            _CAPABILITY_TO_EXCLUDED_TOOLS.get(cap, ())
        )
        for tool in _CAPABILITY_TO_PRIMARY_TOOLS.get(cap, ()):
            if tool in excluded:
                continue
            if tool not in seen_tools:
                seen_tools.add(tool)
                ordered_tools.append(tool)
    required_tools = tuple(ordered_tools)

    # 2. aggregate required evidence types. Mirrors
    # ``EvidenceRequirementPlanner._CAPABILITY_TO_EVIDENCE``
    # so QU + planner stay in lockstep; the planner is still
    # the source of truth for the orchestrator step.
    seen_ev: set[str] = set()
    ordered_ev: list[str] = []
    for cap in capability:
        req_ev, _opt_ev = _QU_CAPABILITY_TO_EVIDENCE.get(cap, ((), ()))
        for ev in req_ev:
            if ev not in seen_ev:
                seen_ev.add(ev)
                ordered_ev.append(ev)
    # Always include ``"profile"`` for business-specific prompts.
    if is_business_specific and "profile" not in seen_ev:
        ordered_ev.insert(0, "profile")
    required_evidence_types = tuple(ordered_ev)

    # 3. requires_* booleans.
    requires_calculation = any(
        c in capability for c in ("CALCULATION", "FINANCIAL")
    )
    requires_scenario_analysis = (
        complexity == "scenario" or "SCENARIO" in capability
    )
    requires_forecast = "FORECAST" in capability
    requires_external_information = any(
        c in capability for c in ("EXTERNAL_INFORMATION", "GOVERNMENT_SCHEME")
    )

    # 4. answer_mode priority. The first capability mapped to a
    # non-empty sections table wins. When 2+ capabilities cross
    # the answer-shape boundary the brief asks for ``mixed``.
    _CAP_TO_SHAPE: dict[str, str] = {
        "GENERAL_KNOWLEDGE": "general_knowledge",
        "BUSINESS_ANALYSIS": "business_analysis",
        "BUSINESS_FACT": "business_analysis",
        "CALCULATION": "calculation",
        "FINANCIAL": "calculation",
        "SCENARIO": "scenario",
        "FORECAST": "scenario",
        "COMPARISON": "comparison",
        "GOVERNMENT_SCHEME": "scheme",
        "EXPORT": "scheme",
        "EXTERNAL_INFORMATION": "external",
        "OPERATIONAL": "business_analysis",
        "RISK": "business_analysis",
        "RECOMMENDATION": "business_analysis",
        "ROADMAP": "business_analysis",
    }
    shapes_hit: list[str] = []
    for cap in capability:
        shape = _CAP_TO_SHAPE.get(cap)
        if shape and shape not in shapes_hit:
            shapes_hit.append(shape)
    if len(shapes_hit) > 1:
        answer_mode = "mixed"
    elif shapes_hit:
        answer_mode = shapes_hit[0]
    elif is_purely_educational and not is_business_specific:
        answer_mode = "general_knowledge"
    else:
        # No capability mapped — fall back to business_analysis
        # when business-specific (advisory default), else
        # general_knowledge.
        answer_mode = "business_analysis" if is_business_specific else "general_knowledge"

    # 5. expected_output_sections — keyed off the picked answer_mode.
    expected_output_sections = _CAPABILITY_TO_OUTPUT_SECTIONS.get(
        _pick_capability_for_shape(answer_mode, capability),
        (),
    )

    return {
        "required_tools": required_tools,
        "required_evidence_types": required_evidence_types,
        "requires_calculation": requires_calculation,
        "requires_scenario_analysis": requires_scenario_analysis,
        "requires_forecast": requires_forecast,
        "requires_external_information": requires_external_information,
        "answer_mode": answer_mode,
        "expected_output_sections": expected_output_sections,
    }


# Mirror of ``EvidenceRequirementPlanner._CAPABILITY_TO_EVIDENCE``.
# Kept in lockstep so the QU can fill ``required_evidence_types``
# without importing the planner (avoids the cycle through
# ``reasoning/__init__.py``). The planner is still the source of
# truth at the orchestrator step — this dict is a mirror.
_QU_CAPABILITY_TO_EVIDENCE: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "GENERAL_KNOWLEDGE": (("document", "knowledge_base"), ()),
    "BUSINESS_ANALYSIS": (("profile", "analytics", "kpi_history"), ("score_history", "rule_history")),
    "BUSINESS_FACT": (("profile",), ("analytics",)),
    "CALCULATION": (("profile", "transaction", "rate_card"), ("forecast_history",)),
    "FINANCIAL": (("profile", "transaction"), ("forecast_history",)),
    "OPERATIONAL": (("profile", "process_metrics"), ("team_metrics",)),
    "RISK": (("profile", "risk_register"), ("scenario_history",)),
    "SCENARIO": (("profile", "historical_assumption"), ("scenario_history",)),
    "FORECAST": (("profile", "forecast_history"), ("external_market",)),
    "COMPARISON": (("profile", "product", "scheme"), ("industry_benchmark",)),
    "RECOMMENDATION": (("profile", "rules"), ("recommendation_history",)),
    "GOVERNMENT_SCHEME": (("scheme", "profile", "funding"), ("application_history",)),
    "EXPORT": (("scheme", "certification"), ("market_intel",)),
    "ROADMAP": (("profile", "recommendation"), ("roadmap_history",)),
    "EXTERNAL_INFORMATION": (("document", "regulatory", "external"), ()),
    "MIXED": (("profile",), ("document",)),
    "UNKNOWN": (("profile",), ()),
}


def _pick_capability_for_shape(
    answer_mode: str, capability: tuple[str, ...]
) -> str:
    """Reverse-map an answer_mode back to the capability token that
    drove it. Returns the first capability in the tuple that
    maps to the shape (the answer-mode logic always walks the
    tuple in priority order, so the first matching entry is the
    authoritative one). Returns ``""`` when no capability can
    claim the shape.
    """
    reverse = {
        "general_knowledge": ("GENERAL_KNOWLEDGE",),
        "business_analysis": (
            "BUSINESS_ANALYSIS", "BUSINESS_FACT", "OPERATIONAL",
            "RISK", "RECOMMENDATION", "ROADMAP",
        ),
        "calculation": ("CALCULATION", "FINANCIAL"),
        "scenario": ("SCENARIO", "FORECAST"),
        "comparison": ("COMPARISON",),
        "scheme": ("GOVERNMENT_SCHEME", "EXPORT"),
        "external": ("EXTERNAL_INFORMATION",),
    }
    for target in reverse.get(answer_mode, ()):
        if target in capability:
            return target
    return ""


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def understand_question(
    prompt: str, context: Any = None
) -> QuestionUnderstanding:
    """Return a :class:`QuestionUnderstanding` for the given prompt.

    Pure function. No I/O. Safe to call from anywhere in the
    reasoning pipeline.

    Parameters
    ----------
    prompt
        The raw user prompt text.
    context
        Optional :class:`AssistantContext` (forward-ref to
        avoid the import cycle). When provided, the existence
        of certain fields is used to detect unknowns.
    """
    text = (prompt or "").strip()
    lower = text.lower()

    topic = _detect_topic(lower)
    is_biz = _is_business_specific(text, context)
    is_edu = is_purely_educational(text)
    complexity = _detect_complexity(lower, topic)
    needs_calc = _detect_needs_calculations(topic, lower)
    needs_services = _detect_needs_services(topic, lower, context)
    unknowns = _detect_unknowns(topic, lower, context)
    sentiment = _detect_sentiment(lower)
    user_intent = _build_user_intent_string(topic, lower)

    # SPRINT AI-11 — capability + business_dependency derivation.
    # Both fields are derived deterministically from the existing
    # heuristics; no new keyword scans, no LLM access.
    capability = _detect_capability(
        lower=lower,
        topic=topic,
        is_business_specific=is_biz,
        is_purely_educational=is_edu,
        complexity=complexity,
    )
    business_dependency = _detect_business_dependency(
        lower=lower,
        is_business_specific=is_biz,
        is_purely_educational=is_edu,
        capability=capability,
    )
    # SPRINT AI-12 — derive the 8 universal-reasoning fields from
    # the AI-11 capability tuple + topic + complexity. Pure
    # function — same inputs ⇒ same output. ``required_evidence_types``
    # stays empty here; the orchestrator's EvidenceRequirementPlanner
    # populates it from the capability tuple so the planner has a
    # single source of truth.
    reasoning_meta = _detect_reasoning_metadata(
        lower=lower,
        topic=topic,
        is_business_specific=is_biz,
        is_purely_educational=is_edu,
        complexity=complexity,
        capability=capability,
    )

    # The existing intent classifier → tuple of intents in
    # priority order. We always emit at least one (the GENERAL
    # fallback). For prompts that match multiple intents, we
    # preserve the priority order emitted by the existing
    # priority-coded scan: revenue-target > weakness > schemes
    # > roadmap > export > hiring > general.
    classified_intent = classify_intent(text)
    if classified_intent != QuestionIntent.GENERAL:
        relevant = (classified_intent, QuestionIntent.GENERAL)
    else:
        relevant = _INTENTS_BY_TOPIC.get(topic, (QuestionIntent.GENERAL,))

    return QuestionUnderstanding(
        literal_question=text,
        user_intent=user_intent,
        topic=topic,
        is_business_specific=is_biz,
        is_purely_educational=is_edu,
        needs_calculations=needs_calc,
        needs_deterministic_services=needs_services,
        unknowns=unknowns,
        relevant_existing_intents=relevant,
        sentiment=sentiment,
        complexity=complexity,
        capability=capability,
        business_dependency=business_dependency,
        # SPRINT AI-12 — pass through the universal-reasoning
        # fields. All default-safe so legacy callers that only
        # pass the AI-11 kwargs keep working unchanged.
        required_evidence_types=reasoning_meta["required_evidence_types"],
        required_tools=reasoning_meta["required_tools"],
        requires_calculation=reasoning_meta["requires_calculation"],
        requires_scenario_analysis=reasoning_meta["requires_scenario_analysis"],
        requires_forecast=reasoning_meta["requires_forecast"],
        requires_external_information=reasoning_meta["requires_external_information"],
        answer_mode=reasoning_meta["answer_mode"],
        expected_output_sections=reasoning_meta["expected_output_sections"],
    )


# Map each topic to the existing QuestionIntent values that are
# most relevant. The tuple is in priority order so the prompt
# builder can pick the first as the primary reroute.
_INTENTS_BY_TOPIC: dict[Topic, tuple[QuestionIntent, ...]] = {
    "finance": (
        QuestionIntent.REACH_REVENUE_TARGET,
        QuestionIntent.GENERAL,
    ),
    "marketing": (QuestionIntent.GENERAL,),
    "operations": (QuestionIntent.GENERAL,),
    "hiring": (QuestionIntent.GENERAL,),
    "export": (QuestionIntent.EXPORT_EXPANSION, QuestionIntent.GENERAL),
    "strategy": (
        QuestionIntent.REACH_REVENUE_TARGET,
        QuestionIntent.TWELVE_MONTH_ROADMAP,
        QuestionIntent.GENERAL,
    ),
    "education": (QuestionIntent.GENERAL,),
    "risk": (QuestionIntent.BIGGEST_WEAKNESS, QuestionIntent.GENERAL),
    "scenario": (
        QuestionIntent.REACH_REVENUE_TARGET,
        QuestionIntent.GENERAL,
    ),
    "general": (QuestionIntent.GENERAL,),
}
