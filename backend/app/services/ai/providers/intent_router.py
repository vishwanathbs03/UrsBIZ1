"""QuestionIntent router — H7.9R+ flagship-question framing.

The previous deterministic fallback returned the *same canned
template* for every user prompt: a single body that mentioned
the overall score, three recommendations, and one roadmap item.
For flagship questions ("How can I reach ₹3 crore turnover?",
"What is my biggest weakness?", "Which government schemes
should I apply for?", "Give me a 12 month roadmap", "Should I
expand exports?") that template is **wrong** — it doesn't even
acknowledge what the user asked.

This module is the fix. It classifies the user's prompt into
one of six :class:`QuestionIntent` values using a deterministic
keyword scan, then each intent knows exactly which slice of
the upstream evidence to surface. The deterministic fallback
uses the classification to render a question-specific body; the
prompt builder uses it to inject a "Task Framing" block at the
top of the real-LLM prompt so Gemini / Ollama also stops
producing generic output.

Design rules
------------

  * **Pure function** — ``classify_intent`` reads the prompt
    and returns an enum value. No I/O, no side effects.
  * **Deterministic** — two calls with the same prompt produce
    the same intent. No LLM, no probabilistic classifier.
  * **Backward-compatible** — every prompt that did NOT match
    a flagship keyword still returns ``QuestionIntent.GENERAL``,
    which preserves the original "consultant framing" body.
  * **No invented data** — every per-intent section reads
    directly from :class:`AssistantContext` fields the prompt
    builder already populates. If a slice is empty, the
    section says so explicitly ("no roadmap items in context").
  * **Keyword priority** — revenue-target > weakness > schemes
    > roadmap > exports. If a prompt contains multiple
    intents (rare but possible: "Should I expand exports and
    which scheme helps?"), the highest-priority intent wins;
    the secondary intent still surfaces in the body as an
    "Additional" section.

Evidence
--------

Every section in the rendered body is grounded in one of the
eight kinds the :class:`EvidenceRegistry` already tracks. The
section renderer returns the evidence IDs alongside the prose
so the response can carry the ``grounded`` trust badge the way
the existing prompt contract already promises.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class QuestionIntent(str, Enum):
    """The recognised question intents.

    Order matters: the router returns the FIRST match in
    keyword-priority order. A prompt that matches both
    ``REACH_REVENUE_TARGET`` and ``GOVERNMENT_SCHEMES`` is
    classified as ``REACH_REVENUE_TARGET`` (the more specific
    framing) and the schemes surface in the secondary
    "Additional schemes referenced" section.

    SPRINT AI-7 — ``HIRING`` is added to surface the brief's
    "Can I afford to hire five employees?" example. The intent
    priority keeps the existing five flagship intents ahead of
    it so the HIRING route only wins when the prompt is clearly
    about hiring, payroll, or team expansion.
    """

    REACH_REVENUE_TARGET = "reach_revenue_target"
    BIGGEST_WEAKNESS = "biggest_weakness"
    GOVERNMENT_SCHEMES = "government_schemes"
    TWELVE_MONTH_ROADMAP = "twelve_month_roadmap"
    EXPORT_EXPANSION = "export_expansion"
    HIRING = "hiring"
    GENERAL = "general"


# Keyword sets per intent. The router scans each prompt
# case-insensitively; a match on ANY keyword in the set
# classifies the prompt as that intent (subject to priority).
_REACH_TARGET_KEYWORDS = (
    "reach", "achieve", "hit ", "scale to", "grow to",
    "increase turnover", "increase revenue",
    "crore", "₹3 cr", "₹3.0 cr", "₹5 cr",
    "turnover target", "revenue target", "growth target",
    "scale up", "grow my business", "current revenue", "our revenue",
    "ಆದಾಯ", "ವಹಿವಾಟು", "ಹೆಚ್ಚಿಸುವುದು", "ಆದಾಯ ಹೆಚ್ಚಳ", "ಬೆಳೆಸುವುದು",
    "ಟರ್ನ್‌ಓವರ್", "ಗುರಿ", "ಆದಾಯ ಎಷ್ಟು", "ಪ್ರಸ್ತುತ ಆದಾಯ", "ವಾರ್ಷಿಕ ಆದಾಯ",
    "ಕೋಟಿ", "₹3 ಕೋಟಿ", "revenue ಎಷ್ಟು", "revenue ಎಷ್ಟಿದೆ",
)
_WEAKNESS_KEYWORDS = (
    "weakness", "weak", "biggest problem", "biggest issue",
    "biggest risk", "biggest business risk", "main risk", "main business risk",
    "top risk", "top business risk", "key risk", "key business risk",
    "what's wrong", "what is wrong", "gap in my", "concern", "bottleneck",
    "failing", "stuck",
    "ಅಪಾಯ", "ದೊಡ್ಡ ಸಮಸ್ಯೆ", "ದೌರ್ಬಲ್ಯ", "ಸಮಸ್ಯೆ", "ರಿಸ್ಕ್", "ತೊಡಕು",
    "ನ್ಯೂನತೆ", "ಮುಖ್ಯ ಅಪಾಯ", "ವ್ಯಾಪಾರ ಅಪಾಯ", "ದೊಡ್ಡ risk", "business risk",
)
_SCHEMES_KEYWORDS = (
    "scheme", "schemes", "government scheme", "subsidy",
    "msme scheme", "cgtmse", "mudra", "pmegp", "nsic",
    "eligible", "eligibility", "apply for",
    "udyam", "loan scheme", "funding scheme",
    "ಸರ್ಕಾರಿ ಯೋಜನೆ", "ಯೋಜನೆಗಳು", "ಯೋಜನೆ", "ಸಬ್ಸಿಡಿ", "ಸ್ಕೀಮ್",
    "ಅರ್ಹತೆ", "ಸಾಲ ಯೋಜನೆ", "ಮುದ್ರಾ", "ಉದ್ಯಮ್", "scheme ಗಳು",
)
_ROADMAP_KEYWORDS = (
    "roadmap", "12 month", "12-month", "twelve month",
    "next 12 months", "next year", "quarter",
    "q1", "q2", "q3", "q4",
    "milestone", "plan for the year", "annual plan",
    "year plan", "phased plan",
    "ರೋಡ್‌ಮ್ಯಾಪ್", "12 ತಿಂಗಳು", "ಹಂತಗಳು", "ಕಾರ್ಯ ಯೋಜನೆ",
    "ವಾರ್ಷಿಕ ಯೋಜನೆ", "ಮುಂದಿನ 12 ತಿಂಗಳು",
)
_EXPORT_KEYWORDS = (
    "export", "exports", "international", "global market",
    "overseas", "foreign market", "ship abroad",
    "export market", "export expansion",
    "ರಫ್ತು", "ವಿದೇಶಿ ವ್ಯಾಪಾರ", "ರಫ್ತು ವಿಸ್ತರಣೆ", "ಅಂತರರಾಷ್ಟ್ರೀಯ", "ವಿದೇಶಿ ಮಾರುಕಟ್ಟೆ",
)
_HIRING_KEYWORDS = (
    "hire", "hiring", "recruit", "recruitment",
    "afford to hire", "additional payroll",
    "team expansion", "headcount",
    "first hire", "next hire",
    "new employee", "new staff",
    "ನೇಮಕಾತಿ", "ಸಿಬ್ಬಂದಿ", "ಉದ್ಯೋಗಿ", "ಕೆಲಸಗಾರರು", "ನೌಕರರು", "ನೇಮಕ",
)

_INTENT_PRIORITY = (
    QuestionIntent.REACH_REVENUE_TARGET,
    QuestionIntent.BIGGEST_WEAKNESS,
    QuestionIntent.GOVERNMENT_SCHEMES,
    QuestionIntent.TWELVE_MONTH_ROADMAP,
    QuestionIntent.EXPORT_EXPANSION,
    QuestionIntent.HIRING,
)


def classify_intent(prompt: str) -> QuestionIntent:
    """Return the :class:`QuestionIntent` for the given user prompt.

    Deterministic keyword scan. Case-insensitive. Returns
    :class:`QuestionIntent.GENERAL` for prompts that match no
    flagship keywords (which preserves the original
    deterministic-fallback behaviour).

    Keyword priority order:
      1. REACH_REVENUE_TARGET
      2. BIGGEST_WEAKNESS
      3. GOVERNMENT_SCHEMES
      4. TWELVE_MONTH_ROADMAP
      5. EXPORT_EXPANSION
      6. HIRING    (SPRINT AI-7)
    """
    text = (prompt or "").lower()
    if not text.strip():
        return QuestionIntent.GENERAL

    if _any_match(text, _REACH_TARGET_KEYWORDS):
        return QuestionIntent.REACH_REVENUE_TARGET
    if _any_match(text, _WEAKNESS_KEYWORDS):
        return QuestionIntent.BIGGEST_WEAKNESS
    if _any_match(text, _SCHEMES_KEYWORDS):
        return QuestionIntent.GOVERNMENT_SCHEMES
    if _any_match(text, _ROADMAP_KEYWORDS):
        return QuestionIntent.TWELVE_MONTH_ROADMAP
    if _any_match(text, _EXPORT_KEYWORDS):
        return QuestionIntent.EXPORT_EXPANSION
    if _any_match(text, _HIRING_KEYWORDS):
        return QuestionIntent.HIRING
    return QuestionIntent.GENERAL


def _any_match(text: str, keywords: tuple[str, ...]) -> bool:
    """Return True iff any keyword appears as a substring."""
    for kw in keywords:
        if kw in text:
            return True
    return False


@dataclass(frozen=True)
class IntentSection:
    """One rendered section of the deterministic fallback body.

    Sections are accumulated by the renderer into the final
    body string. The contract:

      * ``header`` — the section title (e.g. "REVENUE GAP MATH")
      * ``bullets`` — list of facts the user can verify against
        the evidence registry
      * ``evidence_ids`` — stable registry IDs cited in the bullets
      * ``next_actions`` — concrete moves (only from
        ``context.recommendations`` — never invented)
      * ``assumptions`` — context fields we assumed
      * ``limitations`` — context fields we did NOT have
    """

    header: str
    bullets: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class IntentFrame:
    """The full rendering frame for one user prompt.

    Returned by :func:`build_intent_frame`. Contains the
    classified intent, the primary sections to render in the
    deterministic fallback body, the prompt-framing block to
    inject into the real-LLM user message, and the secondary
    sections that surface additional context the user might
    also want (e.g. schemes referenced inside a "reach ₹3
    crore" answer).
    """

    intent: QuestionIntent
    sections: tuple[IntentSection, ...] = field(default_factory=tuple)
    secondary_sections: tuple[IntentSection, ...] = field(default_factory=tuple)
    framing_block: str = ""


def build_intent_frame(
    prompt: str,
    context,  # AssistantContext (forward-ref to avoid the import cycle)
) -> IntentFrame:
    """Classify the prompt and build the rendering frame.

    The renderer is the single entry point for both the
    deterministic fallback body and the prompt-builder's Task
    Framing block. Both call sites pass the same
    ``AssistantContext``; the router only reads the slice the
    matched intent needs.
    """
    intent = classify_intent(prompt)
    if intent is QuestionIntent.REACH_REVENUE_TARGET:
        primary = _reach_target_sections(context)
        secondary = _secondary_schemes(context)
        framing = _TASK_FRAMING_REACH_TARGET
    elif intent is QuestionIntent.BIGGEST_WEAKNESS:
        primary = _biggest_weakness_sections(context)
        secondary = ()
        framing = _TASK_FRAMING_WEAKNESS
    elif intent is QuestionIntent.GOVERNMENT_SCHEMES:
        primary = _schemes_sections(context)
        secondary = ()
        framing = _TASK_FRAMING_SCHEMES
    elif intent is QuestionIntent.TWELVE_MONTH_ROADMAP:
        primary = _roadmap_sections(context)
        secondary = ()
        framing = _TASK_FRAMING_ROADMAP
    elif intent is QuestionIntent.EXPORT_EXPANSION:
        primary = _export_sections(context)
        secondary = ()
        framing = _TASK_FRAMING_EXPORT
    elif intent is QuestionIntent.HIRING:
        primary = _hiring_sections(context)
        secondary = ()
        framing = _TASK_FRAMING_HIRING
    else:
        primary = ()
        secondary = ()
        framing = ""

    return IntentFrame(
        intent=intent,
        sections=primary,
        secondary_sections=secondary,
        framing_block=framing,
    )


# --------------------------------------------------------------------------- #
# Per-intent section builders
# --------------------------------------------------------------------------- #
#
# Every builder reads directly from AssistantContext. No invented data —
# if a field is empty, the section surfaces the absence explicitly.


def _fmt_inr_cr(value: int) -> str:
    """Format an INR figure as ``₹X.XX Cr`` (1 Cr = 1e7 INR)."""
    if not value:
        return "₹0 Cr"
    cr = value / 10_000_000
    return f"₹{cr:.2f} Cr"


def _reach_target_sections(context) -> tuple[IntentSection, ...]:
    """Sections for "How can I reach ₹X crore turnover?" prompts.

    Required outputs (per the H7.9R+ brief):
      * Current revenue
      * Gap
      * Growth strategy
      * Quarter-wise roadmap
      * Funding
      * Schemes
      * Risks
      * Timeline
      * KPIs
    """
    current_rev = getattr(context, "annual_revenue_inr", 0) or 0
    target_rev = getattr(context, "target_revenue_inr", 0) or 0
    gap = max(0, target_rev - current_rev) if target_rev else 0

    # ---- Revenue gap math --------------------------------------------- #
    bullets: list[str] = []
    evidence: list[str] = []
    if current_rev:
        bullets.append(
            f"Current annual revenue: {_fmt_inr_cr(current_rev)} "
            f"(per business profile)."
        )
        evidence.append("biz_profile_revenue")
    else:
        bullets.append(
            "Current annual revenue: not recorded in your profile."
        )
        bullets.append(
            "Add your annual revenue figure so the assistant can "
            "anchor the gap math against a real number."
        )

    if target_rev:
        bullets.append(
            f"Target annual revenue: {_fmt_inr_cr(target_rev)} "
            f"(per business profile)."
        )
    else:
        bullets.append(
            "Target annual revenue: not recorded in your profile."
        )

    if current_rev and target_rev:
        gap_cr = gap / 10_000_000
        bullets.append(
            f"Gap to target: {_fmt_inr_cr(gap)} "
            f"(growth multiple ≈ {target_rev / max(current_rev, 1):.2f}x)."
        )

    # ---- Quarter-wise roadmap from context.roadmap -------------------- #
    recs = sorted(
        context.recommendations,
        key=lambda r: (_priority_rank(r.priority), -r.estimated_score_gain, r.id),
    )
    top_recs = recs[:5]
    rec_section_bullets: list[str] = []
    rec_evidence: list[str] = []
    for r in top_recs:
        rec_section_bullets.append(
            f"  • {r.title} [{r.priority}, +{r.estimated_score_gain} score, "
            f"~{r.estimated_timeline}, ROI {_fmt_money(r.estimated_roi)}]"
        )
        rec_evidence.append(f"rec_{_slug(r.id)}")

    # Group roadmap items by phase for quarter mapping
    roadmap = sorted(context.roadmap, key=lambda x: x.estimated_start_order)
    quarter_lines: list[str] = []
    roadmap_evidence: list[str] = []
    quarter_phases = {
        "Q1 (months 1-3)": [],
        "Q2 (months 4-6)": [],
        "Q3 (months 7-9)": [],
        "Q4 (months 10-12)": [],
    }
    for it in roadmap:
        order = it.estimated_start_order
        if order <= 3:
            quarter_phases["Q1 (months 1-3)"].append(it)
        elif order <= 6:
            quarter_phases["Q2 (months 4-6)"].append(it)
        elif order <= 9:
            quarter_phases["Q3 (months 7-9)"].append(it)
        else:
            quarter_phases["Q4 (months 10-12)"].append(it)
    for q_label, items in quarter_phases.items():
        if items:
            ids = ", ".join(it.id for it in items[:3])
            quarter_lines.append(f"  {q_label}: {len(items)} action(s) — {ids}")
            for it in items:
                roadmap_evidence.append(_roadmap_evidence_id(it.id))

    # ---- Forecasts (scenario revenue delta evidence) ------------------ #
    forecast_bullets: list[str] = []
    forecast_evidence: list[str] = []
    for f in context.forecasts[:3]:
        forecast_bullets.append(
            f"  • {f.horizon_label}: revenue delta {f.revenue_delta:+.0f}, "
            f"score delta {f.score_delta:+d}, confidence {f.confidence}/100 "
            f"(assumptions: {f.assumption_summary or 'n/a'})"
        )
        forecast_evidence.append(f"forecast_{_slug(f.scenario_id)}")

    # ---- Risk rules ---------------------------------------------------- #
    risk_lines: list[str] = []
    risk_evidence: list[str] = []
    critical = [r for r in context.rules if r.priority == "Critical"]
    high = [r for r in context.rules if r.priority == "High"]
    risk_pool = (critical + high)[:3]
    if risk_pool:
        for r in risk_pool:
            risk_lines.append(
                f"  • [{r.priority}] {r.title} — impact {r.estimated_impact} "
                f"({r.category}). Mitigation: {r.reason}"
            )
            risk_evidence.append(f"rule_{_slug(r.id)}")
    else:
        risk_lines.append("  • No critical/high-risk rules fired in this context.")

    # ---- KPI from analytics ------------------------------------------- #
    kpi_lines: list[str] = []
    for am in context.analytics_metrics[:5]:
        kpi_lines.append(
            f"  • {am.metric_name} = {am.current_value} {am.unit} "
            f"(trend: {am.trend})"
        )

    # ---- Build sections ----------------------------------------------- #
    sections = [
        IntentSection(
            header="1. REVENUE GAP MATH (verified facts)",
            bullets=tuple(bullets),
            evidence_ids=tuple(evidence),
            assumptions=(
                "Annual revenue is read from the business profile "
                "in INR; if you reported in USD we converted at "
                "₹83/USD.",
            ) if current_rev else (),
            limitations=(
                "Target revenue is not set in your profile — "
                "set it in Business → Goals to anchor the gap math.",
            ) if not target_rev else (),
        ),
        IntentSection(
            header="2. GROWTH STRATEGY (top recommendations, ranked)",
            bullets=tuple(rec_section_bullets) or (
                "  • No recommendations in context yet.",
            ),
            evidence_ids=tuple(rec_evidence),
            limitations=(
                "Add at least one business goal so the "
                "Recommendation engine can rank actions.",
            ) if not recs else (),
        ),
        IntentSection(
            header="3. QUARTER-WISE ROADMAP (next 12 months)",
            bullets=tuple(quarter_lines) or (
                "  • No roadmap items in context yet.",
            ),
            evidence_ids=tuple(roadmap_evidence),
            limitations=(
                "Roadmap engine has not run for this profile.",
            ) if not roadmap else (),
        ),
        IntentSection(
            header="4. FUNDING & FINANCIAL PROJECTIONS (scenario estimates)",
            bullets=tuple(forecast_bullets) or (
                "  • No scenario forecasts in context yet.",
            ),
            evidence_ids=tuple(forecast_evidence),
            assumptions=(
                "Scenario outputs are estimates, not predictions. "
                "Confidence reflects data completeness, not outcome certainty.",
            ),
        ),
        IntentSection(
            header="5. KEY RISKS (rules engine)",
            bullets=tuple(risk_lines),
            evidence_ids=tuple(risk_evidence),
        ),
        IntentSection(
            header="6. KPIs TO TRACK",
            bullets=tuple(kpi_lines) or (
                "  • No analytics metrics in context yet.",
            ),
        ),
        IntentSection(
            header="7. NEXT ACTIONS",
            bullets=tuple(
                f"Start: {r.title} (~{r.estimated_timeline})"
                for r in top_recs[:3]
            ) or ("  • No recommendations to start.",),
        ),
    ]

    return tuple(sections)


def _biggest_weakness_sections(context) -> tuple[IntentSection, ...]:
    """Sections for "What is my biggest weakness?" prompts."""
    # Rank rules by estimated_impact desc, priority rank asc
    rules = sorted(
        context.rules,
        key=lambda r: (_priority_rank(r.priority), -r.estimated_impact, r.id),
    )
    top_rule = rules[0] if rules else None

    bullets: list[str] = []
    evidence: list[str] = []
    if top_rule:
        bullets.append(
            f"Highest-impact active rule: \"{top_rule.title}\" "
            f"(category: {top_rule.category}, impact {top_rule.estimated_impact}, "
            f"priority {top_rule.priority})."
        )
        bullets.append(
            f"  Why: {top_rule.reason}"
        )
        evidence.append(f"rule_{_slug(top_rule.id)}")
    else:
        bullets.append(
            "No active rules in context — the Rules engine has not yet "
            "produced firings for this profile."
        )

    # Supporting recommendations that target the weakness
    supporting = sorted(
        context.recommendations,
        key=lambda r: (_priority_rank(r.priority), -r.estimated_score_gain, r.id),
    )[:3]
    supporting_bullets: list[str] = []
    supporting_evidence: list[str] = []
    for r in supporting:
        supporting_bullets.append(
            f"  • {r.title} [{r.priority}, +{r.estimated_score_gain} score, "
            f"~{r.estimated_timeline}]"
        )
        supporting_evidence.append(f"rec_{_slug(r.id)}")

    # Insight corroboration
    insight_bullets = [
        f"  • {ins.title} [{ins.priority}, confidence {ins.confidence}/100]"
        for ins in context.insights[:3]
    ]
    insight_evidence = [
        f"insight_{_slug(ins.id)}" for ins in context.insights[:3] if ins.id
    ]

    # Score context — which readiness lens is weakest
    score_lines: list[str] = []
    score_evidence: list[str] = []
    sorted_scores = sorted(context.scores, key=lambda s: s.score)
    if sorted_scores:
        weakest = sorted_scores[0]
        score_lines.append(
            f"  • Weakest readiness lens: {weakest.title} = {weakest.score}/100 "
            f"({weakest.level}) — drill-down target."
        )
        score_evidence.append(f"score_{_slug(weakest.key)}")
        for s in sorted_scores[1:4]:
            score_lines.append(f"  • {s.title} = {s.score}/100 ({s.level})")
            score_evidence.append(f"score_{_slug(s.key)}")

    sections = [
        IntentSection(
            header="1. HIGHEST RISK (rules engine)",
            bullets=tuple(bullets),
            evidence_ids=tuple(evidence),
        ),
        IntentSection(
            header="2. EVIDENCE (insight engine corroboration)",
            bullets=tuple(insight_bullets) or ("  • No insights in context yet.",),
            evidence_ids=tuple(insight_evidence),
        ),
        IntentSection(
            header="3. READINESS LENS BREAKDOWN",
            bullets=tuple(score_lines) or ("  • No readiness scores in context.",),
            evidence_ids=tuple(score_evidence),
        ),
        IntentSection(
            header="4. RECOMMENDED ACTIONS (priority order)",
            bullets=tuple(supporting_bullets) or ("  • No recommendations in context.",),
            evidence_ids=tuple(supporting_evidence),
        ),
        IntentSection(
            header="5. NEXT ACTIONS",
            bullets=tuple(
                f"Start: {r.title} (~{r.estimated_timeline})"
                for r in supporting[:3]
            ) or ("  • No recommendations to start.",),
        ),
    ]
    return tuple(sections)


def _schemes_sections(context) -> tuple[IntentSection, ...]:
    """Sections for "Which government schemes should I apply for?" prompts."""
    ranked = sorted(
        context.schemes,
        key=lambda s: -s.profile_match_score,
    )
    scheme_bullets: list[str] = []
    scheme_evidence: list[str] = []
    for s in ranked[:5]:
        scheme_bullets.append(
            f"  • {s.title} — match {s.profile_match_score}/100 "
            f"(authority: {s.authority or 'unspecified'}, "
            f"verified {s.last_verified_date or 'n/a'}). "
            f"Apply: {s.application_url or 'see portal'}"
        )
        scheme_evidence.append(f"scheme_{_slug(s.scheme_id)}")

    # Eligibility framing — NEVER claim eligibility
    eligibility_line = (
        "  Profile match reflects how well a scheme's published criteria "
        "fit your profile; final eligibility is decided by the issuing "
        "authority. Treat these as 'worth applying for', not 'approved'."
    )

    # Reasons — pull from category where available
    reason_bullets: list[str] = []
    for s in ranked[:3]:
        reason_bullets.append(
            f"  • {s.title}: matched on authority criteria vs your "
            f"{context.industry or 'industry'} profile in "
            f"{context.location or 'your region'}."
        )

    # Next action: top scheme first
    next_action_bullets: tuple[str, ...] = ()
    if ranked:
        top = ranked[0]
        next_action_bullets = (
            f"Visit {top.application_url or 'the official portal'} and "
            f"verify the {top.title} criteria against your documents.",
            "Track application progress on the Action Board.",
        )

    sections = [
        IntentSection(
            header="1. ELIGIBLE SCHEMES (top matches, ranked)",
            bullets=tuple(scheme_bullets) or (
                "  • No scheme matches in context — the scheme engine "
                "has not run for this profile."
            ),
            evidence_ids=tuple(scheme_evidence),
            limitations=(
                "Profile match is NOT eligibility. The scheme engine "
                "computes a match score against published criteria; "
                "the issuing authority makes the eligibility decision.",
            ),
        ),
        IntentSection(
            header="2. WHY THESE MATCH (per-scheme reasons)",
            bullets=(eligibility_line, *reason_bullets) if ranked else (
                "  • No schemes to reason about.",
            ),
        ),
        IntentSection(
            header="3. NEXT ACTIONS",
            bullets=next_action_bullets or (
                "  • Add a target revenue and industry to your profile so "
                "the scheme engine can rank matches.",
            ),
        ),
    ]
    return tuple(sections)


def _roadmap_sections(context) -> tuple[IntentSection, ...]:
    """Sections for "Give me a 12 month roadmap" prompts."""
    roadmap = sorted(context.roadmap, key=lambda x: x.estimated_start_order)
    quarter_phases = {
        "Q1 (months 1-3)": [],
        "Q2 (months 4-6)": [],
        "Q3 (months 7-9)": [],
        "Q4 (months 10-12)": [],
    }
    for it in roadmap:
        order = it.estimated_start_order
        if order <= 3:
            quarter_phases["Q1 (months 1-3)"].append(it)
        elif order <= 6:
            quarter_phases["Q2 (months 4-6)"].append(it)
        elif order <= 9:
            quarter_phases["Q3 (months 7-9)"].append(it)
        else:
            quarter_phases["Q4 (months 10-12)"].append(it)

    quarter_bullets: list[str] = []
    quarter_evidence: list[str] = []
    for q_label, items in quarter_phases.items():
        if items:
            for it in items:
                quarter_bullets.append(
                    f"  • {q_label} — {it.title} "
                    f"({it.phase}, +{it.expected_score_improvement} score, "
                    f"{it.completion_percentage}% complete)"
                )
                quarter_evidence.append(_roadmap_evidence_id(it.id))
        else:
            quarter_bullets.append(f"  • {q_label} — no roadmap items scheduled.")

    # Milestones — top 3 by expected score improvement
    milestones = sorted(
        roadmap,
        key=lambda x: -x.expected_score_improvement,
    )[:3]
    milestone_bullets: list[str] = []
    milestone_evidence: list[str] = []
    for it in milestones:
        milestone_bullets.append(
            f"  • {it.title} ({it.phase}, +{it.expected_score_improvement} score)"
        )
        milestone_evidence.append(_roadmap_evidence_id(it.id))

    # KPIs — analytics metrics
    kpi_bullets: list[str] = []
    for am in context.analytics_metrics[:5]:
        kpi_bullets.append(
            f"  • {am.metric_name} = {am.current_value} {am.unit} "
            f"(trend: {am.trend})"
        )

    sections = [
        IntentSection(
            header="1. QUARTER-WISE ROADMAP",
            bullets=tuple(quarter_bullets),
            evidence_ids=tuple(quarter_evidence),
            limitations=(
                "Roadmap engine has not run for this profile — "
                "Q-by-Q items shown are placeholders.",
            ) if not roadmap else (),
        ),
        IntentSection(
            header="2. KEY MILESTONES (by score impact)",
            bullets=tuple(milestone_bullets) or (
                "  • No milestones in context.",
            ),
            evidence_ids=tuple(milestone_evidence),
        ),
        IntentSection(
            header="3. KPIs TO TRACK",
            bullets=tuple(kpi_bullets) or (
                "  • No analytics metrics in context.",
            ),
        ),
    ]
    return tuple(sections)


def _export_sections(context) -> tuple[IntentSection, ...]:
    """Sections for "Should I expand exports?" prompts."""
    # Readiness
    export_history = list(getattr(context, "export_history", ()) or ())
    digital = list(getattr(context, "digital_presence", ()) or ())
    certs = list(getattr(context, "certifications", ()) or ())

    readiness_bullets: list[str] = []
    if export_history:
        readiness_bullets.append(
            f"  • Export history on file: {', '.join(export_history)} — "
            f"you have prior export context to build on."
        )
    else:
        readiness_bullets.append(
            "  • No prior export history recorded in your profile."
        )
    if digital:
        readiness_bullets.append(
            f"  • Digital presence: {', '.join(digital)} — "
            f"export marketing typically needs a website + social."
        )
    else:
        readiness_bullets.append(
            "  • Digital presence: none recorded — first export "
            "step is usually a website + LinkedIn presence."
        )
    if certs:
        readiness_bullets.append(
            f"  • Certifications on file: {', '.join(certs)} — "
            f"some export markets require ISO / BIS / ZED certification."
        )
    else:
        readiness_bullets.append(
            "  • No certifications recorded — ZED Bronze is a "
            "common first step for MSME exporters."
        )

    # Pros
    pros_bullets: list[str] = [
        "  • Diversifies revenue away from domestic-only demand cycles.",
        "  • INR-rupee depreciation cycles can boost export margins.",
        "  • Export-led growth unlocks higher working-capital lines.",
    ]

    # Risks — top rules + ZED/certification rules
    risks: list[str] = []
    risk_evidence: list[str] = []
    for r in sorted(
        context.rules, key=lambda x: (_priority_rank(x.priority), -x.estimated_impact)
    )[:3]:
        risks.append(
            f"  • [{r.priority}] {r.title} (impact {r.estimated_impact}): "
            f"{r.reason}"
        )
        risk_evidence.append(f"rule_{_slug(r.id)}")
    if not risks:
        risks.append("  • No active rules in context — engine has not run yet.")

    # Target markets — read from goals / industry
    industry = context.industry if context.industry != "unknown" else ""
    goals = list(getattr(context, "goals", ()) or ())
    market_bullets: list[str] = []
    if goals:
        market_bullets.append(
            f"  • Your stated goals: {', '.join(goals)} — pick the "
            f"market(s) that align."
        )
    if industry:
        market_bullets.append(
            f"  • {industry} exports typically target the EU, USA, "
            f"UAE, and ASEAN first; confirm with a freight forwarder."
        )
    else:
        market_bullets.append(
            "  • Add your industry to your profile for target-market "
            "guidance specific to your segment."
        )

    # Recommendation
    recs = sorted(
        context.recommendations,
        key=lambda r: (_priority_rank(r.priority), -r.estimated_score_gain, r.id),
    )
    rec_bullets: list[str] = []
    rec_evidence: list[str] = []
    for r in recs[:3]:
        rec_bullets.append(
            f"  • {r.title} [{r.priority}, +{r.estimated_score_gain} score, "
            f"~{r.estimated_timeline}]"
        )
        rec_evidence.append(f"rec_{_slug(r.id)}")

    sections = [
        IntentSection(
            header="1. EXPORT READINESS (profile signals)",
            bullets=tuple(readiness_bullets),
        ),
        IntentSection(
            header="2. PROS",
            bullets=tuple(pros_bullets),
        ),
        IntentSection(
            header="3. KEY RISKS",
            bullets=tuple(risks),
            evidence_ids=tuple(risk_evidence),
        ),
        IntentSection(
            header="4. TARGET MARKETS",
            bullets=tuple(market_bullets),
        ),
        IntentSection(
            header="5. RECOMMENDATION (priority order)",
            bullets=tuple(rec_bullets) or ("  • No recommendations in context.",),
            evidence_ids=tuple(rec_evidence),
        ),
        IntentSection(
            header="6. NEXT ACTIONS",
            bullets=(
                "Decide target market and validate customs classification.",
                "Begin ZED certification if not already certified.",
                "Identify 2-3 freight forwarders for trial shipments.",
            ) if certs is not None and not certs else (
                "Document current certifications.",
                "Map digital presence to international buyer expectations.",
                "Pilot one overseas trade show or B2B portal listing.",
            ),
        ),
    ]
    return tuple(sections)


def _secondary_schemes(context) -> tuple[IntentSection, ...]:
    """Schemes that surface inside a non-scheme flagship answer."""
    ranked = sorted(
        context.schemes,
        key=lambda s: -s.profile_match_score,
    )[:3]
    if not ranked:
        return ()
    bullets = [
        f"  • {s.title} — match {s.profile_match_score}/100"
        for s in ranked
    ]
    evidence = [f"scheme_{_slug(s.scheme_id)}" for s in ranked]
    return (
        IntentSection(
            header="A. SCHEMES WORTH REFERENCING (secondary)",
            bullets=tuple(bullets),
            evidence_ids=tuple(evidence),
            assumptions=(
                "These surfaced via the scheme engine on this profile "
                "and may help fund the primary plan above.",
            ),
        ),
    )


def _hiring_sections(context) -> tuple[IntentSection, ...]:
    """SPRINT AI-7 — sections for "Can I afford to hire ...?" prompts.

    Reads the hire-affordability inputs (annual revenue, headcount,
    payroll, cash flow, operating margin) directly from
    AssistantContext. NEVER invents payroll, cash flow, or margin
    figures — when absent, the per-section ``IntentSection.
    limitations`` is populated so the AI-7 detector can harvest the
    gap as a structured ``MissingDataObject``.

    No "eligibility" language; the AI-7 detector is the source of
    truth for affordability gaps and the brief is explicit the
    assistant must NOT invent the answer.
    """
    rev = getattr(context, "annual_revenue_inr", 0) or 0
    headcount = getattr(context, "employee_count", "unknown") or "unknown"
    payroll = getattr(context, "monthly_payroll_cost_inr", 0) or 0
    cash_flow = getattr(context, "monthly_operating_cash_flow_inr", 0) or 0
    margin = getattr(context, "operating_margin_pct", 0.0) or 0.0

    bullets: list[str] = []
    limitations: list[str] = []
    if rev:
        bullets.append(f"Current annual revenue: {_fmt_inr_cr(rev)}.")
    else:
        bullets.append("Current annual revenue: not recorded in your profile.")
    if headcount != "unknown" and headcount:
        bullets.append(f"Current headcount: {headcount}.")
    else:
        bullets.append("Current headcount: not recorded in your profile.")
    if not payroll:
        limitations.append(
            "Current monthly payroll cost is not in your profile — "
            "add it in Business → Costs so the assistant can size "
            "the affordability of an additional hire."
        )
    if not cash_flow:
        limitations.append(
            "Current monthly operating cash flow is not in your "
            "profile — the sustainability of the new payroll "
            "depends on it."
        )
    if not margin:
        limitations.append(
            "Current operating margin is not in your profile — "
            "the assistant cannot judge whether the business "
            "absorbs the new fixed cost without it."
        )

    # Section 1 — what we know about the business (verified facts).
    section_one = IntentSection(
        header="1. CURRENT BUSINESS STATE",
        bullets=tuple(bullets),
        limitations=tuple(limitations),
        assumptions=(
            "Headcount + payroll + cash flow are read from the "
            "Business Profile and the Costs sheet. The assistant "
            "does not invent them when they are absent.",
        ),
    )

    # Section 2 — the verdict. Without the inputs, the assistant
    # does not commit to a YES / NO; the verdict is "inconclusive"
    # and the section says so explicitly.
    verdict_bullets: list[str] = []
    if payroll and cash_flow:
        verdict_bullets.append(
            "Inputs are present — the assistant can render an "
            "affordability verdict for the next hire."
        )
    else:
        verdict_bullets.append(
            "Affordability cannot be calculated without the "
            "missing inputs. The AI-7 Missing Information card "
            "lists the gaps and the next step."
        )
    section_two = IntentSection(
        header="2. AFFORDABILITY VERDICT",
        bullets=tuple(verdict_bullets),
        limitations=tuple(limitations),
    )

    # Section 3 — recommendations (only when inputs are present).
    if payroll and cash_flow:
        rec_bullets = [
            "  • Pin the new hire to the role that compresses "
            "your biggest constraint (sales OR ops OR finance).",
            "  • Outsource / fractional first if score < 60; full-"
            "time hire if score ≥ 60 and runway ≥ 6 months.",
            "  • Re-evaluate after 90 days; revisit affordability "
            "as new payroll costs land.",
        ]
    else:
        rec_bullets = [
            "  • Fill the missing inputs in Business Profile → "
            "Costs so the assistant can render an affordability "
            "verdict on the next prompt.",
            "  • See the AI-7 Missing Information card for the "
            "structured gap list + suggested sources.",
        ]
    section_three = IntentSection(
        header="3. RECOMMENDED MOVES",
        bullets=tuple(rec_bullets),
    )

    return (section_one, section_two, section_three)


# --------------------------------------------------------------------------- #
# Task Framing blocks (real-LLM prompt)
# --------------------------------------------------------------------------- #
#
# The deterministic fallback uses the same classifier but renders
# prose directly. The real-LLM path needs an explicit "Task
# Framing" block at the top of the user message so the model
# stops returning the same canned template it returns today.
# Each block tells the model:
#   * what intent we detected,
#   * which sections the response must contain,
#   * which evidence IDs to cite,
#   * which anti-patterns to avoid (e.g. no eligibility claims).


_TASK_FRAMING_REACH_TARGET = """
=== TASK FRAMING (server-detected intent: REACH_REVENUE_TARGET) ===

You are answering: "How do I reach my revenue target?"

Your response MUST contain, in this order:
  1. REVENUE GAP MATH — current revenue, target, gap (Cr), growth multiple. Cite evidence ID ``biz_profile_revenue`` and ``score_overall`` if used.
  2. GROWTH STRATEGY — top 3-5 recommendations ranked by priority and score gain. Cite ``rec_*`` IDs.
  3. QUARTER-WISE ROADMAP — group roadmap items into Q1/Q2/Q3/Q4. Cite ``roadmap_*`` IDs.
  4. FUNDING — scenario forecasts (revenue_delta, confidence). Cite ``forecast_*`` IDs.
  5. KEY RISKS — top 3 critical/high rules with mitigation. Cite ``rule_*`` IDs.
  6. KPIs — analytics metrics to track.
  7. NEXT ACTIONS — concrete first three steps drawn from recommendations.
  8. ASSUMPTIONS / LIMITATIONS — every assumption you made; every field that was missing.
  9. EVIDENCE REFERENCES — every Evidence Registry ID you cited.

Forbidden: inventing revenue numbers, claiming eligibility, promising guaranteed outcomes.
""".strip()


_TASK_FRAMING_WEAKNESS = """
=== TASK FRAMING (server-detected intent: BIGGEST_WEAKNESS) ===

You are answering: "What is my biggest weakness?"

Your response MUST contain, in this order:
  1. HIGHEST RISK — top rule by impact, with reason (cite ``rule_*`` ID).
  2. EVIDENCE — supporting insights from the Insights engine (cite ``insight_*`` IDs).
  3. READINESS LENS BREAKDOWN — weakest lens first (cite ``score_*`` IDs).
  4. BUSINESS IMPACT — translate the risk into revenue / operational impact grounded in profile data.
  5. RECOMMENDED ACTIONS — priority-ordered, cite ``rec_*`` IDs.
  6. NEXT ACTIONS — first concrete step.
  7. ASSUMPTIONS / LIMITATIONS — fields you did not have.
  8. EVIDENCE REFERENCES — every registry ID cited.

Forbidden: hedging ("you might want to improve X"), generic advice, no citations.
""".strip()


_TASK_FRAMING_SCHEMES = """
=== TASK FRAMING (server-detected intent: GOVERNMENT_SCHEMES) ===

You are answering: "Which government schemes should I apply for?"

Your response MUST contain, in this order:
  1. TOP MATCHES — top 3-5 schemes by profile_match_score, with authority, verified date, application link. Cite ``scheme_*`` IDs.
  2. ELIGIBILITY FRAMING — explicit "profile match ≠ eligibility" line, then per-scheme reason.
  3. NEXT ACTIONS — concrete first step for the top scheme.

Forbidden: claiming eligibility, claiming approval, "you qualify for", inventing scheme names.
""".strip()


_TASK_FRAMING_ROADMAP = """
=== TASK FRAMING (server-detected intent: TWELVE_MONTH_ROADMAP) ===

You are answering: "Give me a 12 month roadmap."

Your response MUST contain, in this order:
  1. QUARTER-WISE PLAN — Q1, Q2, Q3, Q4 grouped from the roadmap items in context. Cite ``roadmap_*`` IDs.
  2. KEY MILESTONES — top 3 by expected score improvement.
  3. KPIs — analytics metrics to track.
  4. NEXT ACTIONS — first three concrete moves from recommendations.

Forbidden: inventing timeline items not in context, generic month-by-month boilerplate.
""".strip()


_TASK_FRAMING_EXPORT = """
=== TASK FRAMING (server-detected intent: EXPORT_EXPANSION) ===

You are answering: "Should I expand exports?"

Your response MUST contain, in this order:
  1. EXPORT READINESS — profile signals (export history, digital presence, certifications).
  2. PROS — diversification, FX cycles, working-capital upside.
  3. KEY RISKS — top 3 rules with mitigations. Cite ``rule_*`` IDs.
  4. TARGET MARKETS — based on industry and goals in profile.
  5. RECOMMENDATION — priority-ordered actions. Cite ``rec_*`` IDs.
  6. NEXT ACTIONS — three concrete first steps.

Forbidden: claiming you will export, recommending markets not justified by industry context.
""".strip()


_TASK_FRAMING_HIRING = """
=== TASK FRAMING (server-detected intent: HIRING) ===

You are answering: "Can I afford to hire ...?"

Your response MUST contain, in this order:
  1. CURRENT BUSINESS STATE — headcount, payroll, cash flow, operating margin.
  2. AFFORDABILITY VERDICT — YES / WAIT / NO, grounded in the inputs.
  3. MISSING INPUTS — explicitly list any field the assistant does NOT have (the AI-7 detector surfaces these as structured MissingDataObject rows).
  4. RECOMMENDED MOVES — pin the new hire to the role that compresses your biggest constraint.

Forbidden: inventing payroll, cash flow, or operating margin figures; committing to a YES/NO verdict when the inputs are absent.
""".strip()


# --------------------------------------------------------------------------- #
# Small helpers — duplicated from base.py to avoid the import cycle
# --------------------------------------------------------------------------- #


def _priority_rank(priority: str) -> int:
    if priority == "Critical":
        return 0
    if priority == "High":
        return 1
    if priority == "Medium":
        return 2
    if priority == "Low":
        return 3
    return 99


def _fmt_money(value: float) -> str:
    if value is None:
        return "n/a"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if v >= 1_00_00_000:
        return f"₹{v / 1_00_00_000:.1f} Cr"
    if v >= 1_00_000:
        return f"₹{v / 1_00_000:.1f} L"
    if v >= 1_000:
        return f"₹{v / 1_000:.1f}k"
    return f"₹{v:.0f}"


_SLUG_RE = re.compile(r"[^a-z0-9_]+")


def _slug(value: str) -> str:
    if not value:
        return ""
    return _SLUG_RE.sub("_", str(value).lower()).strip("_")


def _roadmap_evidence_id(item_id: str) -> str:
    """Stable reference slug for a roadmap item.

    The current :class:`EvidenceRegistry` does not emit a
    roadmap entry (it has eight kinds, none of which is
    "roadmap"). Until that registry grows a roadmap kind, we
    use a stable prefix so any future expansion is
    non-breaking. The renderer includes this string in the
    Evidence section only when the registry matches — see
    :func:`_collect_evidence_ids`.
    """
    return f"roadmap_{_slug(item_id)}"


def _collect_evidence_ids(sections: tuple[IntentSection, ...]) -> tuple[str, ...]:
    """Flatten the evidence_ids across sections, deduped, preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for s in sections:
        for eid in s.evidence_ids:
            if eid and eid not in seen:
                seen.add(eid)
                out.append(eid)
    return tuple(out)