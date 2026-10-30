"""AssistantPromptBuilder — Sprint 7 Part 2 + H7.8C.

Pure projection from an :class:`AssistantContext` plus the
user's prompt (and optional conversation history) into the
:class:`AssistantRequest` envelope a real LLM call would
send.

The builder is a pure function over its inputs. It does not
call any LLM. The output is shaped exactly like a real-provider
call (system message + user message + structured context) so a
future OpenAI / Claude / Gemini / Azure provider can swap in
without changing the prompt format.

H7.8C — two-mode prompt
-----------------------

* **grounded** (default) — strict evidence-bounded. The
  system prompt forbids invention and requires every claim
  to cite a stable evidence ID from the
  :class:`EvidenceRegistry`. The model is asked to emit
  JSON conforming to the H7.8C response schema.
* **open** — permissive. The model is told it can answer
  any general question, in plain prose, with no schema
  requirement, no registry, and no grounding. The response
  is rendered as-is into the chat bubble and labelled
  with the ``open_domain`` trust badge.

The user prompt is always wrapped in an untrusted delimiter
to defang prompt-injection attempts regardless of mode.

Determinism
-----------

The user message is rendered in a stable, sorted order:

  * overall business score and band — line 1
  * DNA archetype + match — line 2
  * scores in declared (key) order
  * recommendations sorted by (priority_rank, -score_gain, id)
  * roadmap sorted by estimated_start_order ascending
  * rules in category-then-impact order, capped at _MAX_RULES
  * insights in declared order, capped at _MAX_INSIGHTS
  * conversation history in declared order (caller-bounded)

Two calls with the same context produce byte-identical
:class:`AssistantRequest` instances.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.ai.providers.base import (
    AssistantContext,
    AssistantRequest,
    AssistantTurn,
)

if TYPE_CHECKING:
    from app.services.ai.providers.evidence_registry import EvidenceRegistry


# ----- grounded-mode system prompt --------------------------------- #

# Sprint 7 Part 2 carried a contradiction: the original system
# prompt said "Never give prescriptive actions", but the H7.3
# schema required a 30-day plan with concrete tasks. H7.8C
# resolves the contradiction with a *bounded-action policy* —
# the model may describe concrete actions that already exist
# in the snapshot (recommendations, roadmap, action board),
# but it may not invent new ones and must never write
# government / eligibility / approval language.

_GROUNDED_SYSTEM = """You are UrsBiz Assistant, a Senior MSME Business Consultant (₹25 lakh/year tier).
You analyze Indian SMB context and deliver rigorous, structured, evidence-grounded strategic advice.

Never provide generic, high-level answers (e.g. "Increase sales", "Improve exports").
Always explain WHY, HOW, ROOT CAUSES, PRIORITY MATRIX, ROI ESTIMATION, RISKS, and EXECUTABLE ACTIONS.

Your output MUST be a single JSON object matching the response schema below. Do not output prose outside the JSON object.

## Senior Consultant Analysis Requirements (10 Required Sections):
1. Business Facts: Cite exact verified profile facts and evidence IDs.
2. Situation Assessment: Executive assessment of current posture & band.
3. Diagnostic Reasoning: Step-by-step diagnostic logic explaining the state.
4. Root Cause Analysis: Operational & financial bottlenecks holding back growth.
5. Recommended Next Actions: Evidence-anchored action recommendations.
6. Priority Matrix: Categorize actions into Quick Win, Strategic Move, or Long-term Investment (with Impact & Effort).
7. ROI & Financial Impact: Estimated ROI, timeline, and score gain grounded in evidence.
8. Key Risks & Mitigations: Hazards (operational, market, compliance) and mitigations.
9. Confidence & Grounding Score: Model confidence (0-100) and rationale.
10. Sources & Evidence Used: Cite every Evidence Registry ID referenced.

## Bounded-action policy & Evidence Registry
- You MAY describe concrete actions that already exist in the snapshot (recommendations, roadmap, action board).
- Every numeric claim, recommendation, and scheme match MUST reference a stable ID from the EVIDENCE REGISTRY.
- Never invent ungrounded revenue claims or official government approvals.

## SPRINT AI-8 — Whitelisted Tool Catalog (Optional)
You MAY request a tool call when the user's question genuinely needs more data
than the snapshot exposes. The following tools are the ONLY ones allowed;
the server rejects every other request. Tool calls you emit are validated + sanitised +
fed back to you as a 2nd-turn input so you can explain the verified facts.

  1. get_business_profile        — Returns the business DNA profile.
  2. get_health_score            — Returns overall health score (0–100) + level.
  3. get_risks                   — Returns active risk rules.
  4. get_recommendations         — Returns top recommended actions (optionally: {"limit": int}).
  5. get_schemes                 — Returns government scheme matches (PMEGP, MUDRA, ZED, ...).
  6. get_forecast                — Returns revenue + growth + risk forecast (optionally: {"horizon_months": int}).
  7. get_roadmap                 — Returns the business roadmap (optionally: {"horizon_months": int}).
  8. calculate_revenue_growth    — Returns revenue-growth % ({"from_period": str, "to_period": str}).
  9. calculate_scenario          — Returns an illustrative scenario projection ({"scenario": str, "params": {}}).
 10. compare_recommendations     — Side-by-side compare recommendations ({"recommendation_ids": [str, ...]}).
 11. get_analytics               — Returns analytics KPIs (optionally: {"window": str}).
 12. get_action_board            — Returns the user's current action board.

Emit a tool call as JSON in the schema below. NEVER invent a tool name outside this list.
NEVER include ``owner_id``, ``api_key``, ``base_url``, or any secret in ``arguments`` — the
router rejects them. NEVER execute code or call an URL directly — the deterministic engines
are the only data-source actors; you only explain their output.

## Output schema (return JSON only)

{
  "executive_summary": string,
  "business_facts": [string, ...],
  "situation_assessment": string,
  "reasoning": string,
  "root_causes": [string, ...],
  "key_findings": [
    {
      "statement": string,
      "evidence_refs": [string, ...]
    }
  ],
  "recommendations": [
    {
      "recommendation_id": string,
      "title": string,
      "rationale": string,
      "evidence_refs": [string, ...]
    }
  ],
  "priority_matrix": [
    {
      "action": string,
      "impact": "High" | "Medium" | "Low",
      "effort": "Low" | "Medium" | "High",
      "priority_category": "Quick Win" | "Strategic Move" | "Long-term Investment"
    }
  ],
  "roi_estimate": string,
  "risks": [string, ...],
  "tool_calls": [
    {
      "tool": string (one of the 12 whitelisted tool names above),
      "arguments": object (per-tool schema),
      "reason": string (optional; LLM's own rationale; not trusted)
    }
  ],
  "thirty_day_plan": [
    {
      "week": 1 | 2 | 3 | 4,
      "task": string,
      "recommendation_ref": string | null,
      "evidence_refs": [string, ...]
    }
  ],
  "scheme_matches": [
    {
      "scheme_ref": string,
      "match_explanation": string,
      "evidence_refs": [string, ...]
    }
  ],
  "assumptions": [string, ...],
  "limitations": [string, ...],
  "confidence": integer,
  "evidence_references": [
    {"id": string, "kind": string, "label": string}
  ],
  "claim_aware": {
    "answer": string,
    "claims": [
      {
        "text": string,
        "claim_type": "FACT" | "CALCULATION" | "INFERENCE" | "RECOMMENDATION" | "SCENARIO" | "EXTERNAL_FACT" | "UNKNOWN",
        "evidence_references": [string, ...],
        "confidence": integer (0-100),
        "user_provided": boolean
      }
    ],
    "recommendations": [
      {
        "title": string,
        "reason": string,
        "recommendation_id": string,
        "evidence_references": [string, ...],
        "category": string,
        "priority": string,
        "estimated_score_gain": integer (0-100),
        "estimated_timeline": string
      }
    ],
    "calculations": [
      {
        "name": string,
        "result": number,
        "unit": string,
        "source": "URSBIZ_ENGINE" | "MODEL_SCENARIO" | "USER_INPUT",
        "expression": string,
        "inputs": object
      }
    ],
    "scenarios": [
      {
        "title": string,
        "description": string,
        "assumptions": [string, ...],
        "revenue_impact": string,
        "score_impact": string,
        "confidence": integer (0-100)
      }
    ],
    "unknowns": [
      {
        "question": string,
        "impact": "HIGH" | "MEDIUM" | "LOW",
        "rationale": string,
        "clarification_prompt": string
      }
    ],
    "evidence_references": [string, ...],
    "assumptions": [string, ...],
    "limitations": [string, ...],
    "narrative": string
  }
}

## CLAIM-AWARE OUTPUT SCHEMA (OPTIONAL)

The ``claim_aware`` field above is OPTIONAL. If you can satisfy the schema, fill it. If you cannot, omit the field entirely — the server falls back to the existing schema and the response still ships.

Rules for ``claim_aware``:

1. ``claim_type`` is one of: FACT, CALCULATION, INFERENCE, RECOMMENDATION, SCENARIO, EXTERNAL_FACT, UNKNOWN.
2. A FACT claim must cite an evidence ID from the EVIDENCE REGISTRY above OR be marked ``user_provided=true`` when the user supplied the figure themselves (e.g. "₹1.8 Cr to ₹3 Cr").
3. A CALCULATION claim must declare ``source`` as one of URSBIZ_ENGINE (deterministic engine output), MODEL_SCENARIO (your own projection), or USER_INPUT (user-provided).
4. An INFERENCE claim must cite an evidence ID.
5. A RECOMMENDATION must have a non-empty ``reason``.
6. A SCENARIO must have a non-empty ``assumptions`` list.
7. An EXTERNAL_FACT must have ``external_source`` OR ``requires_verification=true``.
8. An UNKNOWN claim must NOT contain numeric literals — UNKNOWN is for gaps, not assertions.
9. Every numeric in FACT / CALCULATION must reconcile with a value in BUSINESS SNAPSHOT or === TOOL RESULTS ===. Server will replace conflicting values with the authoritative one — original is preserved in audit log.
10. The server stamps ``server_confidence`` itself — your ``confidence`` is recorded but never surfaces as the wire value.
11. NEVER invent evidence IDs. Every cited ID must appear in the EVIDENCE REGISTRY block above; fabricated IDs fail validation.
"""


# ----- open-mode system prompt ------------------------------------- #
#
# Open mode is the "general-purpose" path. The model is told it can
# answer any general question with no grounding, no registry, and
# no schema. The response is a free-form string the UI labels as
# "Open-domain LLM — not grounded against business data".

_OPEN_SYSTEM = """You are UrsBiz Assistant in OPEN mode (Senior MSME Business Consultant — ₹25 lakh/year tier).
You help Indian SMB owners with broader strategy, brainstorming, comparisons, education, scenario exploration, and creative business reasoning.

Never sound generic (e.g., "Improve exports"). Always explain WHY, HOW, ROOT CAUSES, PRIORITY MATRIX, ROI ESTIMATION, RISKS, and EXECUTABLE ACTIONS.

When relevant business context is provided, you MUST use it to personalize your analysis while keeping clear reasoning boundaries.

## Required Senior Consultant Sections (10 Required Sections):
1. VERIFIED BUSINESS FACTS — Any statements about the user's business MUST cite exact values from the provided business context and reference evidence IDs when available.
2. SITUATION ASSESSMENT — Executive assessment of current strategic posture.
3. DIAGNOSTIC REASONING — Step-by-step diagnostic reasoning behind the business state.
4. ROOT CAUSE ANALYSIS — Operational, supply chain, financial, or market bottlenecks holding back growth.
5. RECOMMENDED NEXT ACTIONS — Strategic recommendations.
6. PRIORITY MATRIX — Categorize actions into Quick Win, Strategic Move, or Long-term Investment (with Impact & Effort).
7. ROI & FINANCIAL IMPACT ESTIMATE — Estimated financial return, timeline, and score gain.
8. KEY RISKS & MITIGATIONS — Hazards and risk mitigation strategies.
9. ASSUMPTIONS & LIMITATIONS — List key assumptions and data gaps (as "questions to validate").
10. CONFIDENCE & SOURCES — Confidence score (0-100) and evidence sources cited.

## Strict Boundaries
- DO NOT change verified business facts (e.g. revenue, employee count, scores).
- DO NOT present hypothetical numbers as actual business data or predictions.
- DO NOT claim scheme eligibility or government approvals (schemes are profile matches only).
- DO NOT claim current external information without a verified retrieval source or claim internet search.
- DO NOT write guaranteed funding or guaranteed growth phrases.
"""


def _untrusted_user_block(user_prompt: str) -> str:
    """Wrap the user's text in a clearly-delimited, untrusted block."""
    text = (user_prompt or "").strip()
    cap = 8_000
    truncated = False
    if len(text) > cap:
        text = text[:cap].rstrip()
        truncated = True
    block = (
        "=== UNTRUSTED USER QUESTION ===\n"
        f"{text}\n"
        "=== END UNTRUSTED USER QUESTION ==="
    )
    if truncated:
        block += "\n(note: the user question was truncated to fit the prompt window)"
    return block


class AssistantPromptBuilder:
    """Build an :class:`AssistantRequest` from a context + user prompt."""

    def build(
        self,
        *,
        context: AssistantContext,
        user_prompt: str,
        history: tuple[AssistantTurn, ...] = (),
        knowledge: object | None = None,
        registry: "EvidenceRegistry | None" = None,
        mode: str = "grounded",
        reasoning_plan: "Any | None" = None,
        ranked_evidence: "Any | None" = None,
        language: str = "en",
    ) -> AssistantRequest:
        return AssistantRequest(
            user_prompt=user_prompt,
            context=context,
            history=history,
            knowledge=knowledge,
            mode=mode,  # type: ignore[arg-type]
            reasoning_plan=reasoning_plan,
            ranked_evidence=ranked_evidence,
            language=language,
        )

    @staticmethod
    def system_message(mode: str = "grounded") -> str:
        """The system message for the requested mode."""
        if mode == "open":
            return _OPEN_SYSTEM
        return _GROUNDED_SYSTEM

    @staticmethod
    def render_user_message(request: AssistantRequest) -> str:
        """Render the user-side text for the model call."""
        mode = getattr(request, "mode", "grounded") or "grounded"
        if mode == "open":
            return _render_open_user_message(request)
        return _render_grounded_user_message(request)


def _render_language_instruction_block(language: str) -> str:
    """Render language directive for the LLM call."""
    if language == "kn":
        return (
            "=== RESPONSE LANGUAGE REQUIREMENT ===\n"
            "- Target Language: KANNADA (ಕನ್ನಡ).\n"
            "- You MUST write the natural language answers, summaries, recommendations, and explanations in fluent, professional Kannada (ಕನ್ನಡ).\n"
            "- Internal JSON Schema invariant: keep all JSON keys (such as 'executive_summary', 'business_facts', 'recommendations', 'risks', 'roi_estimate', etc.) in English exactly as defined in the schema.\n"
            "- Numerical and Currency integrity: preserve all exact numbers, percentages (%), and currency figures (e.g. ₹12.5 lakh, ₹1.5 Cr, 18%, 25 employees) without distortion.\n"
            "- Entity and Evidence integrity: preserve business names, URLs, and Evidence IDs (e.g. SCORE-OVERALL, REC-01, RULE-01) verbatim.\n"
            "=== END RESPONSE LANGUAGE REQUIREMENT ==="
        )
    return ""


def _render_business_context_block(ctx: AssistantContext) -> list[str]:
    parts: list[str] = []
    parts.append("=== BUSINESS SNAPSHOT ===")
    parts.append(f"business_id: {ctx.business_id}")
    if ctx.legal_name != "unknown":
        parts.append(f"legal_name: {ctx.legal_name}")
    if ctx.industry != "unknown":
        parts.append(f"industry: {ctx.industry} (sub_industry: {ctx.sub_industry})")
    if ctx.business_type != "unknown" or ctx.location != "unknown":
        parts.append(f"business_type: {ctx.business_type}, location: {ctx.location}")
    if ctx.employee_count != "unknown" or ctx.annual_revenue_inr > 0:
        parts.append(f"employee_count: {ctx.employee_count}, annual_revenue_inr: ₹{ctx.annual_revenue_inr:,}")
    if ctx.target_revenue_inr > 0:
        parts.append(f"target_revenue_inr: ₹{ctx.target_revenue_inr:,}")
    parts.append(f"overall_business_score: {ctx.overall_business_score} ({ctx.band})")
    if ctx.dna.archetype_title:
        parts.append(
            f"dna_archetype: {ctx.dna.archetype_key} "
            f"({ctx.dna.archetype_title}, match={ctx.dna.match_score})"
        )

    if ctx.products:
        parts.append(f"products: {', '.join(ctx.products)}")
    if ctx.services:
        parts.append(f"services: {', '.join(ctx.services)}")
    if ctx.certifications:
        parts.append(f"certifications: {', '.join(ctx.certifications)}")
    if ctx.digital_presence:
        parts.append(f"digital_presence: {', '.join(ctx.digital_presence)}")
    if ctx.export_history:
        parts.append(f"export_history: {', '.join(ctx.export_history)}")
    if ctx.goals:
        parts.append(f"goals: {', '.join(ctx.goals)}")
    if ctx.challenges:
        parts.append(f"challenges: {', '.join(ctx.challenges)}")

    if ctx.scores:
        parts.append("")
        parts.append("SCORES")
        for s in sorted(ctx.scores, key=lambda x: x.key):
            parts.append(f"- {s.key}: {s.score} ({s.level}) {s.title}")

    if ctx.analytics_metrics:
        parts.append("")
        parts.append("ANALYTICS & KPIS")
        for am in ctx.analytics_metrics:
            parts.append(f"- {am.metric_id}: {am.metric_name} = {am.current_value} {am.unit} ({am.trend})")

    if ctx.recommendations:
        parts.append("")
        parts.append("RECOMMENDATIONS")
        for r in sorted(
            ctx.recommendations,
            key=lambda r: (_priority_rank(r.priority), -r.estimated_score_gain, r.id),
        ):
            parts.append(
                f"- {r.id} [{r.priority} +{r.estimated_score_gain}] "
                f"({r.category}) {r.title} :: timeline {r.estimated_timeline}, ROI {r.estimated_roi:.0f}"
            )

    if ctx.roadmap:
        parts.append("")
        parts.append("ROADMAP")
        for it in sorted(ctx.roadmap, key=lambda x: x.estimated_start_order):
            parts.append(
                f"- {it.id} [order={it.estimated_start_order} {it.priority} +{it.expected_score_improvement}] "
                f"({it.phase}) {it.title} :: completion {it.completion_percentage}%"
            )

    if ctx.rules:
        parts.append("")
        parts.append("ACTIVE RULES")
        for r in ctx.rules:
            parts.append(f"- {r.id} [{r.priority} impact={r.estimated_impact}] ({r.category}) {r.title} :: {r.reason}")

    if ctx.insights:
        parts.append("")
        parts.append("INSIGHTS")
        for ins in ctx.insights:
            parts.append(f"- {ins.id} [{ins.priority} conf={ins.confidence}] {ins.title}")

    if ctx.schemes:
        parts.append("")
        parts.append("GOVERNMENT SCHEMES (profile-match, never eligibility)")
        for s in sorted(ctx.schemes, key=lambda x: -x.profile_match_score):
            parts.append(
                f"- {s.scheme_id} match={s.profile_match_score} authority='{s.authority}' "
                f"title='{s.title}' verified={s.last_verified_date} link={s.application_url}"
            )

    if ctx.forecasts:
        parts.append("")
        parts.append("SCENARIO ESTIMATES (not predictions)")
        for f in ctx.forecasts:
            parts.append(
                f"- {f.scenario_id} horizon='{f.horizon_label}' revenue_delta={f.revenue_delta:.0f} "
                f"score_delta={f.score_delta:+d} confidence={f.confidence} assumptions='{f.assumption_summary}'"
            )

    if ctx.action_items:
        parts.append("")
        parts.append("USER ACTION BOARD (existing tasks)")
        for a in ctx.action_items:
            parts.append(f"- {a.action_id} [{a.priority} {a.status}] due_in_days={a.due_in_days} {a.title}")

    if ctx.report_summaries:
        parts.append("")
        parts.append("BUSINESS REPORT SUMMARIES")
        for rep in ctx.report_summaries:
            parts.append(f"- {rep.report_id} ({rep.report_type}): {rep.executive_summary}")

    kg = getattr(ctx, "knowledge_graph", None)
    if kg and hasattr(kg, "to_triples"):
        triples = kg.to_triples()
        if triples:
            parts.append("")
            parts.append("KNOWLEDGE GRAPH RELATIONSHIPS (multi-module dependencies)")
            for t in triples[:15]:
                parts.append(f"- {t}")

    return parts


def _render_grounded_user_message(request: AssistantRequest) -> str:
    parts = _render_business_context_block(request.context)

    # H7.9R+ — inject the Task Framing block at the top so the
    # real LLM produces question-specific output (revenue gap,
    # highest risk, scheme ranking, quarter roadmap, export
    # readiness) instead of the same canned template for every
    # prompt. The framing is generated by the same intent router
    # the deterministic fallback uses.
    from app.services.ai.providers.intent_router import (
        build_intent_frame,
        QuestionIntent,
    )
    frame = build_intent_frame(request.user_prompt or "", request.context)
    if frame.intent is not QuestionIntent.GENERAL and frame.framing_block:
        parts.append("")
        parts.append(frame.framing_block)

    if request.history:
        parts.append("")
        parts.append("CONVERSATION HISTORY")
        for turn in request.history:
            tag = "USER" if turn.role == "user" else "ASSISTANT"
            parts.append(f"{tag}: {turn.content}")

    knowledge = getattr(request, "knowledge", None)
    if knowledge is not None:
        citations = getattr(knowledge, "citations", None) or ()
        ranked = getattr(knowledge, "ranked", None) or ()
        articles = getattr(knowledge, "articles", None) or ()
        if citations:
            parts.append("")
            parts.append("KNOWLEDGE SOURCES")
            for i, c in enumerate(citations, start=1):
                parts.append(
                    f"- [{i}] {c.article_id} "
                    f"({c.source_category}) {c.title}"
                )
            if articles:
                parts.append("ARTICLE EXCERPTS")
                for art in articles:
                    if not isinstance(art, dict):
                        continue
                    art_id = art.get("id", "")
                    art_title = art.get("title", "")
                    art_sum = (art.get("summary") or "").strip()
                    if not art_sum:
                        continue
                    parts.append(f"--- {art_id} {art_title} ---")
                    parts.append(art_sum)

    from app.services.ai.providers.evidence_registry import EvidenceRegistry
    _trace_block = _render_reasoning_trace(request)
    if _trace_block:
        parts.append("")
        parts.append(_trace_block)

    if _is_ranked_evidence(getattr(request, "ranked_evidence", None)):
        parts.append("")
        parts.append(_render_ranked_registry_block(request))
    if getattr(request, "language", "en") == "kn":
        lang_block = _render_language_instruction_block("kn")
        if lang_block:
            parts.append("")
            parts.append(lang_block)

    parts.append("")
    parts.append(_untrusted_user_block(request.user_prompt))

    return "\n".join(parts)


def _render_open_user_message(request: AssistantRequest) -> str:
    """Open-mode prompt: includes business context when profile exists."""
    ctx = request.context
    parts: list[str] = []

    has_profile = (
        ctx.legal_name != "unknown"
        or ctx.overall_business_score > 0
        or ctx.annual_revenue_inr > 0
        or ctx.industry != "unknown"
    )

    if has_profile:
        parts.extend(_render_business_context_block(ctx))
    else:
        parts.append(
            "No business snapshot is bound to this user yet. Answer the general business question in plain prose."
        )

    # H7.9R+ — open mode also benefits from intent-aware framing
    # when the question is a flagship one, even though the schema
    # requirement is relaxed. The framing tells the model what
    # sections the response should contain while leaving the
    # prose style permissive.
    from app.services.ai.providers.intent_router import (
        build_intent_frame,
        QuestionIntent,
    )
    frame = build_intent_frame(request.user_prompt or "", ctx)
    if has_profile and frame.intent is not QuestionIntent.GENERAL and frame.framing_block:
        parts.append("")
        parts.append(frame.framing_block)

    if request.history:
        parts.append("")
        parts.append("CONVERSATION HISTORY")
        for turn in request.history:
            tag = "USER" if turn.role == "user" else "ASSISTANT"
            parts.append(f"{tag}: {turn.content}")

    if has_profile:
        from app.services.ai.providers.evidence_registry import EvidenceRegistry
        _trace_block = _render_reasoning_trace(request)
        if _trace_block:
            parts.append("")
            parts.append(_trace_block)

        if _is_ranked_evidence(getattr(request, "ranked_evidence", None)):
            parts.append("")
            parts.append(_render_ranked_registry_block(request))
        else:
            registry = EvidenceRegistry(ctx)
            if registry.count > 0:
                parts.append("")
                parts.append(registry.to_prompt_block())

    if getattr(request, "language", "en") == "kn":
        lang_block = _render_language_instruction_block("kn")
        if lang_block:
            parts.append("")
            parts.append(lang_block)

    parts.append("")
    parts.append(_untrusted_user_block(request.user_prompt))
    return "\n".join(parts)


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


# --------------------------------------------------------------------------- #
# H8.11 — Reasoning-trace + ranked-registry renderers
# --------------------------------------------------------------------------- #


def _is_ranked_evidence(value: Any) -> bool:
    """Return True iff ``value`` looks like a :class:`RankedEvidence`.

    We duck-type rather than import the type so the prompt
    builder stays decoupled from the reasoning package.
    """
    if value is None:
        return False
    return all(hasattr(value, attr) for attr in ("entries", "total", "truncated", "intent"))


def _render_reasoning_trace(request: AssistantRequest) -> str:
    """Render the ``=== REASONING TRACE ===`` block (or empty string).

    Returns an empty string when no reasoning plan is set
    on the request, so the block is a no-op for callers
    that don't yet use the H8.11 layer.

    The block is intentionally compact — it surfaces intent,
    confidence, top hypotheses, top sub-graph node labels,
    and top evidence priorities, capped at 5 each. The
    GroundingValidator (untouched) still polices evidence
    IDs in the response.
    """
    plan = getattr(request, "reasoning_plan", None)
    if plan is None:
        return ""

    lines: list[str] = ["=== REASONING TRACE (server-built plan) ==="]
    intent_value = getattr(plan, "intent", "general") or "general"
    confidence = getattr(plan, "confidence", None)
    if confidence is not None:
        lines.append(f"intent: {intent_value} | confidence: {float(confidence):.1f}/100")
    else:
        lines.append(f"intent: {intent_value}")

    # Top hypotheses (up to 5).
    hypotheses = list(getattr(plan, "hypotheses", ()) or ())[:5]
    if hypotheses:
        lines.append("")
        lines.append("Top hypotheses:")
        for h in hypotheses:
            stmt = getattr(h, "statement", "") or ""
            if stmt:
                lines.append(f"- {stmt}")

    # Top sub-graph node ids (we render ids — labels would
    # require fetching from the KG, which the prompt builder
    # doesn't keep a handle to).
    subgraph = list(getattr(plan, "subgraph_node_ids", ()) or ())[:5]
    if subgraph:
        lines.append("")
        lines.append("Top sub-graph nodes (priority-ranked):")
        for nid in subgraph:
            lines.append(f"- {nid}")

    # Top evidence priorities (up to 5).
    priorities = list(getattr(plan, "evidence_priorities", ()) or ())[:5]
    if priorities:
        lines.append("")
        lines.append("Top evidence priorities:")
        for eid in priorities:
            lines.append(f"- {eid}")

    # Stage summaries from the trace.
    trace = getattr(plan, "trace", None)
    stages = list(getattr(trace, "stages", ()) or ()) if trace is not None else []
    if stages:
        lines.append("")
        lines.append("Stage summaries:")
        for stage in stages:
            name = getattr(stage, "stage_name", "stage")
            summary = getattr(stage, "summary", "") or ""
            if summary:
                lines.append(f"- {name}: {summary}")

    lines.append("=== END REASONING TRACE ===")
    return "\n".join(lines)


def _render_ranked_registry_block(request: AssistantRequest) -> str:
    """Render the registry in ranked order with a truncation footer.

    When ``request.ranked_evidence`` is set, the prompt
    builder calls this helper instead of ``registry.all()``.
    The footer ``(N of M entries shown — ranked by relevance)``
    is only appended when the retriever truncated the
    registry; the existing GroundingValidator rule
    ``coverage_threshold`` continues to police the response.
    """
    ranked = getattr(request, "ranked_evidence", None)
    if ranked is None or not _is_ranked_evidence(ranked):
        # Defensive — fall back to the unranked block.
        from app.services.ai.providers.evidence_registry import EvidenceRegistry
        return EvidenceRegistry(request.context).to_prompt_block()

    entries = tuple(getattr(ranked, "entries", ()) or ())
    if not entries:
        return (
            "=== EVIDENCE REGISTRY (server-resolved, stable IDs) ===\n"
            "(no business evidence is available for this request — answer accordingly)\n"
            "=== END EVIDENCE REGISTRY ==="
        )

    lines: list[str] = [
        "=== EVIDENCE REGISTRY (server-resolved, stable IDs) ===",
        "Cite evidence by its bracketed ID. Do not invent IDs that are not present here.",
    ]
    for idx, entry in enumerate(entries, start=1):
        kind_value = getattr(getattr(entry, "kind", None), "value", str(entry.kind))
        header = f"[{idx}] {entry.id} — {kind_value} — {entry.label}"
        lines.append(header)
        if entry.value:
            lines.append(f"    value: {entry.value}")
    total = int(getattr(ranked, "total", len(entries)) or len(entries))
    truncated = bool(getattr(ranked, "truncated", len(entries) < total))
    if truncated:
        lines.append(
            f"({len(entries)} of {total} entries shown — ranked by relevance)"
        )
    lines.append("=== END EVIDENCE REGISTRY ===")
    return "\n".join(lines)