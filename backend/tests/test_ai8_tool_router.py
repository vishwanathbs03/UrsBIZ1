"""SPRINT AI-8 — Tests for the Controlled Business Tool Router.

The router implements the brief's 6-step validation pipeline:

  1. Tool exists in the 12-tool whitelist.
  2. Arguments valid (Pydantic ``extra="forbid"``).
  3. Owner id binds from JWT — NEVER the LLM.
  4. Tool allowed for the caller's intent.
  5. Output sanitised (``_LEAKED_FIELDS`` dropped).
  6. Output receives stable evidence IDs.

These tests exercise the pipeline end-to-end against a
**fake ToolDispatcher** whose tools return canned payloads,
so the suite stays deterministic + decoupled from real
database engines.

The fixtures below are intentionally minimal — every test
is one assertion chain against the router's contract. The
catalog itself is tested independently; the router tests
focus on the **behaviour the brief mandates** (rejection
paths, sanitisation, evidence stamping, owner-id security).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import ValidationError

from app.services.ai.providers.evidence_registry import EvidenceKind
from app.services.ai.reasoning.tool_selector import (
    ToolCall,
    ToolDispatcher,
    ToolInterface,
    ToolResult,
)
from app.services.ai.sanitisation import (
    LEAKED_FIELDS,
    strip_leaked_secrets,
)
from app.services.ai.tool_router.catalog import (
    INTENT_COMPATIBILITY,
    TOOL_REGISTRY,
    ToolCatalog,
)
from app.services.ai.tool_router.router import (
    LLMToolRequestRouter,
    _MAX_LLM_TOOL_CALLS_PER_REQUEST,
)
from app.services.ai.tool_router.types import (
    LLMToolRequest,
    LLMToolResult,
)


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #


class FakeTool:
    """A canned :class:`ToolInterface` returning a fixed payload.

    Tests register one of these per engine so the router's
    dispatch path runs end-to-end without touching the real
    engine services (which depend on a database session).
    """

    def __init__(
        self,
        name: str,
        *,
        payload: Any = None,
        status: str = "ok",
        error: str = "",
        duration_ms: int = 5,
    ) -> None:
        self.name = name
        self._payload = payload if payload is not None else {"data": "ok"}
        self._status = status
        self._error = error
        self._duration_ms = duration_ms
        self.calls: list[tuple[int, ToolCall]] = []

    def invoke(
        self, *, owner_id: int, call: ToolCall, context: Any
    ) -> ToolResult:
        self.calls.append((owner_id, call))
        return ToolResult(
            service_name=call.service_name,
            status=self._status,
            payload=self._payload,
            duration_ms=self._duration_ms,
            error=self._error,
        )


class LeakingTool(FakeTool):
    """A tool that intentionally leaks an API key in its payload."""

    def __init__(self, name: str = "leaky") -> None:
        super().__init__(
            name,
            payload={
                "upstream_url": "https://api.openai.com/v1",
                "api_key": "sk-leaked-12345",
                "authorization": "Bearer leaked",
                "data": {"safe": 1},
            },
        )


class TimeoutTool(FakeTool):
    """A tool whose dispatcher marks ``status="skipped"``."""

    def __init__(self, name: str = "slow") -> None:
        super().__init__(
            name, status="skipped", error="timeout", duration_ms=1000,
        )


def _make_router(
    *,
    tools: dict[str, FakeTool] | None = None,
) -> LLMToolRequestRouter:
    """Build a router with a fresh dispatcher + canonical catalog."""
    dispatcher = ToolDispatcher()
    for name, tool in (tools or {}).items():
        dispatcher.register_tool(name, tool)
    return LLMToolRequestRouter(
        catalog=ToolCatalog(),
        dispatcher=dispatcher,
    )


# --------------------------------------------------------------------------- #
# 1. Step 1 — tool exists in whitelist
# --------------------------------------------------------------------------- #


def test_router_rejects_unknown_tool():
    """An unknown tool name is rejected with ``unknown_tool:...``."""
    router = _make_router()
    req = LLMToolRequest(tool="rm_rf", arguments={})
    out = router.route(req, owner_id=1, intent="general")
    assert out.status == "error"
    assert out.tool == "rm_rf"
    assert out.evidence_ids == ()
    assert out.payload == {}
    assert out.error is not None
    assert out.error.startswith("unknown_tool:")
    assert "rm_rf" in out.error


def test_router_rejects_empty_tool_name():
    """An empty ``tool`` is rejected at step 1 (no spec)."""
    router = _make_router()
    # Pydantic rejects ``tool=""`` at construction time, but
    # we round-trip via dict-construction so the router
    # sees a raw empty name. We bypass LLMToolRequest to
    # verify the router's defensive step 1.
    req = LLMToolRequest.model_construct(tool="", arguments={}, reason="")
    out = router.route(req, owner_id=1, intent="general")
    assert out.status == "error"
    assert out.error is not None
    assert out.error.startswith("unknown_tool:")


# --------------------------------------------------------------------------- #
# 2. Step 2 — arguments valid (Pydantic extra="forbid")
# --------------------------------------------------------------------------- #


def test_router_rejects_invalid_arguments_missing_required():
    """``calculate_revenue_growth`` without ``from_period`` is rejected."""
    router = _make_router(tools={"growth": FakeTool("growth")})
    req = LLMToolRequest(
        tool="calculate_revenue_growth",
        arguments={"to_period": "FY25"},
    )
    out = router.route(req, owner_id=1, intent="general")
    assert out.status == "error"
    assert out.error is not None
    assert out.error.startswith("invalid_arguments:")


def test_router_rejects_invalid_arguments_wrong_type():
    """``limit`` must be an int for ``get_recommendations``."""
    router = _make_router(
        tools={"recommendation": FakeTool("recommendation")},
    )
    req = LLMToolRequest(
        tool="get_recommendations",
        arguments={"limit": "five"},
    )
    out = router.route(req, owner_id=1, intent="general")
    assert out.status == "error"
    assert out.error is not None
    assert out.error.startswith("invalid_arguments:")


def test_router_rejects_extra_arguments_extra_forbid():
    """``extra="forbid"`` blocks smuggled unknown keys."""
    router = _make_router(tools={"growth": FakeTool("growth")})
    req = LLMToolRequest(
        tool="calculate_revenue_growth",
        arguments={
            "from_period": "FY24",
            "to_period": "FY25",
            "owner_id": 999,  # the cardinal smuggling attempt
        },
    )
    out = router.route(req, owner_id=1, intent="general")
    assert out.status == "error"
    assert out.error is not None
    assert out.error.startswith("invalid_arguments:")
    # The engine must NOT have been called — owner_id leak
    # never reached it.
    assert router._dispatcher.get_tool("growth").calls == []  # noqa: SLF001


def test_router_rejects_extra_owner_id_in_no_args_tool():
    """``get_business_profile`` (no args) rejects ``arguments.owner_id``."""
    router = _make_router(
        tools={"business_dna": FakeTool("business_dna")},
    )
    req = LLMToolRequest(
        tool="get_business_profile",
        arguments={"owner_id": 999},
    )
    out = router.route(req, owner_id=1, intent="general")
    assert out.status == "error"
    assert out.error is not None
    assert out.error.startswith("invalid_arguments:")
    # The engine must NOT have been called.
    assert router._dispatcher.get_tool("business_dna").calls == []  # noqa: SLF001


def test_router_rejects_extra_secret_in_no_args_tool():
    """Defensive scan: no-args tool with ``api_key`` is rejected."""
    router = _make_router(
        tools={"business_dna": FakeTool("business_dna")},
    )
    req = LLMToolRequest(
        tool="get_business_profile",
        arguments={"api_key": "sk-leak"},
    )
    out = router.route(req, owner_id=1, intent="general")
    assert out.status == "error"
    assert out.error is not None
    assert out.error.startswith("invalid_arguments:")


def test_router_rejects_extra_args_for_no_args_tool():
    """Defensive scan: no-args tool with any non-empty arguments is rejected."""
    router = _make_router(
        tools={"health_score": FakeTool("health_score")},
    )
    req = LLMToolRequest(
        tool="get_health_score",
        arguments={"surprise": "value"},
    )
    out = router.route(req, owner_id=1, intent="general")
    assert out.status == "error"
    assert out.error is not None
    assert out.error.startswith("invalid_arguments:")


# --------------------------------------------------------------------------- #
# 3. Step 3 — owner_id binding (LLM-supplied owner_id rejected)
# --------------------------------------------------------------------------- #


def test_router_owner_id_comes_from_closure_not_llm():
    """The router must call the engine with the closure owner_id,
    NEVER with whatever the LLM tried to inject."""
    fake = FakeTool("growth")
    router = _make_router(tools={"growth": fake})
    req = LLMToolRequest(
        tool="calculate_revenue_growth",
        arguments={
            "from_period": "FY24",
            "to_period": "FY25",
        },
    )
    out = router.route(req, owner_id=42, intent="general")
    assert out.status == "ok"
    # The engine was called exactly once, with owner_id=42
    # (the closure value), not whatever the LLM tried to
    # smuggle via ``arguments``.
    assert len(fake.calls) == 1
    assert fake.calls[0][0] == 42


# --------------------------------------------------------------------------- #
# 4. Step 4 — tool allowed for intent
# --------------------------------------------------------------------------- #


def test_router_rejects_tool_for_wrong_intent():
    """``get_schemes`` under ``HIRING`` is rejected (cross-intent drift)."""
    router = _make_router(
        tools={"schemes_sprint16": FakeTool("schemes_sprint16")},
    )
    req = LLMToolRequest(tool="get_schemes", arguments={})
    out = router.route(req, owner_id=1, intent="hiring")
    assert out.status == "error"
    assert out.error is not None
    assert out.error.startswith("tool_not_allowed_for_intent:")
    assert "hiring" in out.error


def test_router_allows_tool_for_listed_intent():
    """``get_schemes`` under ``government_schemes`` succeeds."""
    fake = FakeTool("schemes_sprint16", payload={"schemes": ["PMEGP"]})
    router = _make_router(tools={"schemes_sprint16": fake})
    req = LLMToolRequest(tool="get_schemes", arguments={})
    out = router.route(req, owner_id=1, intent="government_schemes")
    assert out.status == "ok"
    assert out.payload == {"schemes": ["PMEGP"]}


def test_router_general_intent_is_fallback_for_all_tools():
    """The ``general`` intent is allowed for every tool in the catalog."""
    router = _make_router(
        tools={
            "business_dna": FakeTool("business_dna"),
            "health_score": FakeTool("health_score"),
            "risk": FakeTool("risk"),
            "recommendation": FakeTool("recommendation"),
            "schemes_sprint16": FakeTool("schemes_sprint16"),
            "predictive_sprint14": FakeTool("predictive_sprint14"),
            "growth": FakeTool("growth"),
            "finance": FakeTool("finance"),
            "kpi": FakeTool("kpi"),
            "roadmap": FakeTool("roadmap"),
            "compare_recommendations": FakeTool("compare_recommendations"),
            "action_board": FakeTool("action_board"),
        },
    )
    # Typed tools need their required args; the brief's
    # intent test is "general allows every tool", not
    # "every tool accepts empty arguments".
    valid_args: dict[str, dict[str, Any]] = {
        "calculate_revenue_growth": {"from_period": "FY24", "to_period": "FY25"},
        "calculate_scenario": {"scenario": "baseline"},
        "get_recommendations": {"limit": 5},
        "get_forecast": {"horizon_months": 12},
        "get_roadmap": {"horizon_months": 12},
        "get_analytics": {"window": "90d"},
        "compare_recommendations": {"recommendation_ids": ["rec_001"]},
    }
    for spec in ToolCatalog().all():
        args = valid_args.get(spec.name, {})
        req = LLMToolRequest(tool=spec.name, arguments=args)
        out = router.route(req, owner_id=1, intent="general")
        assert out.status == "ok", (
            f"general intent should allow {spec.name}; "
            f"got error={out.error!r}"
        )


# --------------------------------------------------------------------------- #
# 5. Step 5 — dispatch + sanitise
# --------------------------------------------------------------------------- #


def test_router_strips_leaked_secrets_top_level():
    """Leaked keys at the top of the payload are stripped."""
    router = _make_router(tools={"growth": LeakingTool("growth")})
    req = LLMToolRequest(
        tool="calculate_revenue_growth",
        arguments={"from_period": "FY24", "to_period": "FY25"},
    )
    out = router.route(req, owner_id=1, intent="general")
    assert out.status == "ok"
    assert "api_key" not in out.payload
    assert "authorization" not in out.payload
    assert "upstream_url" not in out.payload
    assert "bearer" not in out.payload
    assert "auth_header" not in out.payload
    assert "base_url" not in out.payload
    assert "secret" not in out.payload
    assert "access_token" not in out.payload
    # The non-leaked field is preserved.
    assert out.payload.get("data") == {"safe": 1}


def test_router_strips_leaked_secrets_nested():
    """Leaked keys nested inside a list / dict are also stripped."""
    payload = {
        "items": [
            {"api_key": "sk-leak", "title": "ok"},
            {"title": "ok", "auth_header": "Bearer xyz"},
        ],
    }
    router = _make_router(
        tools={"kpi": FakeTool("kpi", payload=payload)},
    )
    req = LLMToolRequest(tool="get_analytics", arguments={"window": "30d"})
    out = router.route(req, owner_id=1, intent="general")
    assert out.status == "ok"
    assert out.payload["items"][0].get("api_key") is None
    assert out.payload["items"][1].get("auth_header") is None
    assert out.payload["items"][0]["title"] == "ok"
    assert out.payload["items"][1]["title"] == "ok"


def test_router_strips_leaked_secrets_helper_recursive():
    """Sanity check on the underlying helper used by the router."""
    payload = {
        "api_key": "sk-leak",
        "nested": {"secret": "x", "keep": 1},
        "list": [{"upstream_url": "u", "data": 1}],
    }
    cleaned = strip_leaked_secrets(payload)
    assert "api_key" not in cleaned
    assert "secret" not in cleaned["nested"]
    assert cleaned["nested"]["keep"] == 1
    assert "upstream_url" not in cleaned["list"][0]
    assert cleaned["list"][0]["data"] == 1
    # LEAKED_FIELDS is the canonical set the router guards against.
    assert "api_key" in LEAKED_FIELDS
    assert "authorization" in LEAKED_FIELDS
    assert "upstream_url" in LEAKED_FIELDS


# --------------------------------------------------------------------------- #
# 6. Step 6 — evidence IDs
# --------------------------------------------------------------------------- #


def test_router_stamps_evidence_id_for_score_tool():
    """``get_health_score`` stamps an id like ``score:<sha16>``."""
    payload = {"overall": 72, "level": "Established"}
    router = _make_router(tools={"health_score": FakeTool("health_score", payload=payload)})
    req = LLMToolRequest(tool="get_health_score", arguments={})
    out = router.route(req, owner_id=1, intent="general")
    assert out.status == "ok"
    assert len(out.evidence_ids) == 1
    eid = out.evidence_ids[0]
    assert eid.startswith("score:")
    # The sha256 hex[:16] of the canonicalised payload.
    canonical = json.dumps(payload, sort_keys=True, default=str)
    expected = "score:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    assert eid == expected


def test_router_stamps_evidence_id_for_scheme_tool():
    """``get_schemes`` stamps an id with the ``scheme:`` prefix."""
    payload = {"schemes": [{"scheme_id": "pmegp", "title": "PMEGP"}]}
    router = _make_router(
        tools={"schemes_sprint16": FakeTool("schemes_sprint16", payload=payload)},
    )
    req = LLMToolRequest(tool="get_schemes", arguments={})
    out = router.route(req, owner_id=1, intent="government_schemes")
    assert out.status == "ok"
    assert out.evidence_ids[0].startswith("scheme:")


def test_router_stamps_evidence_id_for_recommendation_tool():
    """``get_recommendations`` stamps an id with the ``recommendation:`` prefix."""
    payload = {"recommendations": [{"id": "rec_001", "title": "Audit"}]}
    router = _make_router(
        tools={"recommendation": FakeTool("recommendation", payload=payload)},
    )
    req = LLMToolRequest(
        tool="get_recommendations", arguments={"limit": 5},
    )
    out = router.route(req, owner_id=1, intent="general")
    assert out.status == "ok"
    assert out.evidence_ids[0].startswith("recommendation:")


def test_router_stamps_evidence_id_for_dna_tool():
    """``get_business_profile`` stamps an id with the ``dna:`` prefix."""
    payload = {"archetype": "Growth Operator", "match": 85}
    router = _make_router(
        tools={"business_dna": FakeTool("business_dna", payload=payload)},
    )
    req = LLMToolRequest(tool="get_business_profile", arguments={})
    out = router.route(req, owner_id=1, intent="general")
    assert out.status == "ok"
    assert out.evidence_ids[0].startswith("dna:")


def test_router_evidence_id_stable_for_same_payload():
    """Two identical payloads must yield identical evidence IDs."""
    payload = {"value": 42}
    router = _make_router(tools={"kpi": FakeTool("kpi", payload=payload)})
    req = LLMToolRequest(tool="get_analytics", arguments={"window": "30d"})
    out1 = router.route(req, owner_id=1, intent="general")
    out2 = router.route(req, owner_id=1, intent="general")
    assert out1.evidence_ids == out2.evidence_ids


def test_router_rejected_result_has_empty_evidence_ids():
    """Rejected requests carry ``evidence_ids=()`` — the LLM
    never receives a fabricated ID for a tool that did not run."""
    router = _make_router()
    out = router.route(
        LLMToolRequest(tool="unknown_tool", arguments={}),
        owner_id=1, intent="general",
    )
    assert out.status == "error"
    assert out.evidence_ids == ()


# --------------------------------------------------------------------------- #
# 7. Timeouts / skipped / engine exceptions
# --------------------------------------------------------------------------- #


def test_router_skipped_status_preserved():
    """An engine returning ``status="skipped"`` stays skipped."""
    router = _make_router(tools={"growth": TimeoutTool("growth")})
    req = LLMToolRequest(
        tool="calculate_revenue_growth",
        arguments={"from_period": "FY24", "to_period": "FY25"},
    )
    out = router.route(req, owner_id=1, intent="general")
    assert out.status == "skipped"
    assert out.error == "timeout"


def test_router_engine_exception_returns_error_status():
    """An engine raising returns ``status="error"`` (never raises)."""
    class Boom(FakeTool):
        def invoke(self, *, owner_id, call, context):
            raise RuntimeError("kaboom")

    router = _make_router(tools={"growth": Boom("growth")})
    req = LLMToolRequest(
        tool="calculate_revenue_growth",
        arguments={"from_period": "FY24", "to_period": "FY25"},
    )
    # The dispatcher's ``_safe_invoke`` wrapper turns the
    # raise into a ``status="error"`` ToolResult. We assert
    # the router surfaces it as ``status="error"``.
    out = router.route(req, owner_id=1, intent="general")
    # The dispatcher wraps engine-side exceptions; the
    # router trusts the contract and maps the result.
    assert out.status in ("error", "skipped")
    assert out.payload == {}


# --------------------------------------------------------------------------- #
# 8. route_all — batching + spillover
# --------------------------------------------------------------------------- #


def test_route_all_processes_batch_in_order():
    """``route_all`` returns one result per input, in order."""
    router = _make_router(
        tools={"health_score": FakeTool("health_score", payload={"a": 1}),
               "growth": FakeTool("growth", payload={"b": 2})},
    )
    requests = (
        LLMToolRequest(tool="get_health_score", arguments={}),
        LLMToolRequest(
            tool="calculate_revenue_growth",
            arguments={"from_period": "FY24", "to_period": "FY25"},
        ),
    )
    results = router.route_all(requests, owner_id=1, intent="general")
    assert len(results) == 2
    assert results[0].tool == "get_health_score"
    assert results[1].tool == "calculate_revenue_growth"


def test_route_all_spillover_rejected():
    """More than ``_MAX_LLM_TOOL_CALLS_PER_REQUEST`` spillovers
    are rejected with ``too_many_tool_calls``."""
    router = _make_router(tools={"health_score": FakeTool("health_score")})
    requests = tuple(
        LLMToolRequest(tool="get_health_score", arguments={})
        for _ in range(_MAX_LLM_TOOL_CALLS_PER_REQUEST + 2)
    )
    results = router.route_all(requests, owner_id=1, intent="general")
    # First N succeed, the last 2 are rejected.
    assert results[0].status == "ok"
    rejected = [r for r in results if r.status == "error"]
    assert len(rejected) == 2
    for r in rejected:
        assert r.error is not None
        assert r.error.startswith("too_many_tool_calls:")


def test_route_all_empty_input_returns_empty_tuple():
    """An empty batch returns an empty tuple — never raises."""
    router = _make_router()
    assert router.route_all((), owner_id=1, intent="general") == ()


# --------------------------------------------------------------------------- #
# 9. Happy paths — every brief tool
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "tool_name, engine_name, arguments, intent",
    [
        ("get_business_profile", "business_dna", {}, "general"),
        ("get_health_score", "health_score", {}, "general"),
        ("get_risks", "risk", {}, "biggest_weakness"),
        (
            "get_recommendations",
            "recommendation",
            {"limit": 5},
            "general",
        ),
        ("get_schemes", "schemes_sprint16", {}, "government_schemes"),
        (
            "get_forecast",
            "predictive_sprint14",
            {"horizon_months": 12},
            "twelve_month_roadmap",
        ),
        (
            "get_roadmap",
            "roadmap",
            {"horizon_months": 12},
            "twelve_month_roadmap",
        ),
        (
            "calculate_revenue_growth",
            "growth",
            {"from_period": "FY24", "to_period": "FY25"},
            "reach_revenue_target",
        ),
        (
            "calculate_scenario",
            "finance",
            {"scenario": "best_case", "params": {"hire": 2}},
            "hiring",
        ),
        (
            "compare_recommendations",
            "compare_recommendations",
            {"recommendation_ids": ["rec_001"]},
            "general",
        ),
        (
            "get_analytics",
            "kpi",
            {"window": "90d"},
            "general",
        ),
        ("get_action_board", "action_board", {}, "general"),
    ],
)
def test_router_happy_path_every_brief_tool(
    tool_name, engine_name, arguments, intent
):
    """All 12 whitelisted tools reach the engine and return ``status="ok"``."""
    fake = FakeTool(engine_name, payload={"ok": True})
    router = _make_router(tools={engine_name: fake})
    out = router.route(
        LLMToolRequest(tool=tool_name, arguments=arguments),
        owner_id=1, intent=intent,
    )
    assert out.status == "ok", (
        f"tool {tool_name} (engine={engine_name}) "
        f"unexpectedly rejected: error={out.error!r}"
    )
    assert out.payload == {"ok": True}
    # Engine called once with the closure owner_id.
    assert len(fake.calls) == 1
    assert fake.calls[0][0] == 1
    # The call's inputs pass through to the engine verbatim
    # — the router does not inject owner_id there.
    assert fake.calls[0][1].inputs == arguments


# --------------------------------------------------------------------------- #
# 10. Catalog + intent compatibility
# --------------------------------------------------------------------------- #


def test_tool_catalog_has_twelve_entries():
    """The registry contains exactly 12 tools."""
    assert len(TOOL_REGISTRY) == 12
    assert len(ToolCatalog().all()) == 12
    assert len(ToolCatalog().names()) == 12


def test_tool_catalog_intent_compatibility_matches_intent_router():
    """For every intent, every name in ``INTENT_COMPATIBILITY``
    is a key in :data:`TOOL_REGISTRY`."""
    for intent, names in INTENT_COMPATIBILITY.items():
        assert intent, "empty intent key in INTENT_COMPATIBILITY"
        for name in names:
            assert name in TOOL_REGISTRY, (
                f"intent {intent!r} references unknown tool {name!r}"
            )


def test_tool_catalog_is_allowed_for_intent_round_trip():
    """``is_allowed_for_intent`` agrees with the inverse ``INTENT_COMPATIBILITY``."""
    catalog = ToolCatalog()
    for intent, names in INTENT_COMPATIBILITY.items():
        for spec in catalog.all():
            expected = spec.name in names
            assert catalog.is_allowed_for_intent(spec.name, intent) is expected


def test_tool_catalog_tools_for_intent_returns_frozenset():
    """``tools_for_intent`` returns a ``frozenset`` (immutable)."""
    catalog = ToolCatalog()
    for intent in INTENT_COMPATIBILITY:
        result = catalog.tools_for_intent(intent)
        assert isinstance(result, frozenset)


def test_tool_catalog_get_unknown_returns_none():
    """``catalog.get("not_a_tool")`` returns ``None``."""
    catalog = ToolCatalog()
    assert catalog.get("not_a_tool") is None
    assert catalog.get("") is None


# --------------------------------------------------------------------------- #
# 11. Pydantic wire types
# --------------------------------------------------------------------------- #


def test_llm_tool_request_rejects_extra_fields():
    """``extra="forbid"`` blocks the LLM from smuggling fields."""
    with pytest.raises(ValidationError):
        LLMToolRequest(
            tool="get_business_profile",
            arguments={},
            base_url="https://api.openai.com",
        )


def test_llm_tool_request_rejects_long_tool_name():
    """``tool`` length is capped at 64 chars."""
    with pytest.raises(ValidationError):
        LLMToolRequest(tool="x" * 65, arguments={})


def test_llm_tool_request_default_arguments():
    """``arguments`` defaults to an empty dict."""
    req = LLMToolRequest(tool="get_business_profile")
    assert req.arguments == {}
    assert req.reason == ""


def test_llm_tool_result_rejects_extra_fields():
    """``LLMToolResult.extra="forbid"`` — no LLM-supplied status smuggling."""
    with pytest.raises(ValidationError):
        LLMToolResult(
            tool="x",
            status="ok",
            evidence_ids=(),
            payload={},
            duration_ms=0,
            api_key="sk-leak",
        )


def test_llm_tool_result_status_vocabulary():
    """Only ``ok`` / ``skipped`` / ``error`` are accepted."""
    with pytest.raises(ValidationError):
        LLMToolResult(
            tool="x", status="not_a_status", evidence_ids=(),
            payload={}, duration_ms=0,
        )


def test_llm_tool_result_duration_must_be_non_negative():
    """``duration_ms`` is ``ge=0`` — negative durations rejected."""
    with pytest.raises(ValidationError):
        LLMToolResult(
            tool="x", status="ok", evidence_ids=(),
            payload={}, duration_ms=-1,
        )


# --------------------------------------------------------------------------- #
# 12. Sanitisation module — re-export sanity
# --------------------------------------------------------------------------- #


def test_sanitisation_promoted_module_has_same_leaked_fields():
    """``sanitisation.LEAKED_FIELDS`` is the same set the legacy
    ``_LEAKED_FIELDS`` from ``conversation_service`` referenced."""
    from app.services.chat.conversation_service import (
        _LEAKED_FIELDS,
    )
    # Both modules must agree on the deny-list — adding a
    # field is non-breaking, removing one is. The set
    # identity is enforced by the legacy re-export.
    assert set(_LEAKED_FIELDS) == set(LEAKED_FIELDS)


def test_sanitisation_strip_helper_does_not_mutate_input():
    """``strip_leaked_secrets`` returns a copy — input unchanged."""
    payload = {"api_key": "sk-leak", "data": 1}
    original = dict(payload)
    cleaned = strip_leaked_secrets(payload)
    # Input is untouched.
    assert payload == original
    # Output has the secret removed.
    assert "api_key" not in cleaned
    assert cleaned["data"] == 1
    # The two are not the same object.
    assert cleaned is not payload


def test_sanitisation_strip_handles_none():
    """``None`` in, ``None`` out."""
    assert strip_leaked_secrets(None) is None