"""PromptBuilder — turns an AIContext into a prompt.

The builder is a pure function. It does not call any LLM. The
output is a :class:`LLMPrompt` that any provider (mock or real)
can consume.

A real provider will receive ``prompt.system`` and
``prompt.user`` as the model call's messages. The mock provider
ignores them and produces a deterministic answer. Either way,
the prompt format is the contract — the future real provider
swap is a one-line change in the service.
"""

from __future__ import annotations

from app.services.ai.base import AIContext, LLMPrompt


# System message — every model call is the same. A real
# provider may tune this further (style, persona, length cap).
_SYSTEM = (
    "You are UrsBiz, a business analyst for an Indian SMB. "
    "You receive a structured snapshot of a business: archetype, "
    "scores, active rule firings, and matched knowledge articles. "
    "Your job is to explain the situation in plain language, "
    "attributing every claim to a rule id and / or article id. "
    "Never invent a rule id or article id. Never give prescriptive "
    "actions ('email supplier X by Friday') — descriptive only. "
    "Return JSON with the shape: "
    "{summary, archetype_label, overall_health, "
    "top_strengths, top_risks, insights:[{id, title, explanation, "
    "category, priority, confidence, supporting_rule_ids, "
    "supporting_article_ids}]}."
)


class PromptBuilder:
    """Build a :class:`LLMPrompt` from an :class:`AIContext`."""

    def build(self, context: AIContext) -> LLMPrompt:
        return LLMPrompt(
            system=_SYSTEM,
            user=_render_user(context),
            context=context,
        )


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def _render_user(ctx: AIContext) -> str:
    """Render the user message — pure string assembly.

    The shape is stable so the mock provider and any future real
    provider parse the same input.
    """
    lines: list[str] = []
    lines.append("BUSINESS SNAPSHOT")
    lines.append(f"business_id: {ctx.business_id}")
    lines.append(
        f"archetype: {ctx.archetype_key} ({ctx.archetype_title}, "
        f"match={ctx.archetype_match_score})"
    )
    lines.append(f"intelligence_overall: {ctx.intelligence_overall}")
    lines.append("")
    lines.append("SCORES")
    for s in ctx.scores:
        lines.append(f"- {s.key}: {s.score} ({s.level}) — {s.title}")
    lines.append("")
    lines.append("ACTIVE RULES (top by impact)")
    if not ctx.rules:
        lines.append("- (none)")
    for r in ctx.rules:
        lines.append(
            f"- {r.id} [{r.priority} imp={r.estimated_impact}] "
            f"({r.category}) {r.title} :: {r.reason}"
        )
    lines.append("")
    lines.append("MATCHED KNOWLEDGE ARTICLES")
    if not ctx.knowledge:
        lines.append("- (none)")
    for a in ctx.knowledge:
        lines.append(
            f"- {a.id} [rel={a.relevance}] ({a.topic}/{a.category}) "
            f"{a.title} :: {a.summary}"
        )
    return "\n".join(lines)
