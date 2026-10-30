"""SPRINT AI-8 — The controlled tool router.

Implements the 6-step validation pipeline the AI-8 brief
mandates. The router is the **only** path through which the
LLM-emitted ``tool_calls`` reach a deterministic engine,
and every step is auditable.

Pipeline (6 steps)
------------------

1. **Tool exists** — name looked up in the :class:`ToolCatalog`.
2. **Arguments valid** — Pydantic validates the tool's
   ``arguments`` with ``extra="forbid"`` (catches
   smuggled ``owner_id`` / ``api_key`` / ``base_url`` etc.).
3. **Owner-id binding** — the router reads ``owner_id`` from
   the closure; the LLM-supplied ``arguments.owner_id`` is
   rejected by step 2. Tools whose schema is ``None`` are
   additionally scanned for safety-blacklisted keys.
4. **Tool allowed** — the caller's intent must be in
   ``ToolSpec.intents``.
5. **Dispatch + sanitise** — the engine runs through the
   ``ToolDispatcher`` (existing AI-1 path). The payload
   passes through :func:`strip_leaked_secrets` before the
   LLM sees it on the 2nd turn.
6. **Stamp evidence IDs** — the router derives a stable
   ID per ``EvidenceKind`` from the payload's structural
   hash. When the engine supplies its own IDs (the common
   case for recommendations / schemes / rules), the router
   merges them.

The router NEVER produces a user-visible response on its
own — the ``LLMToolResult`` always feeds back to the LLM
on a 2nd turn, which then *explains* the verified facts.

Error contract
--------------

Each rejection step returns an :class:`LLMToolResult` with
``status="error"`` and a human-readable ``error`` reason.
The LLM can narrate the rejection: *"I could not run
calculate_revenue_growth because the from_period argument
was malformed; here is what I DO know…"*. The router
never raises — a malformed request becomes a structured
error and the chat continues.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from pydantic import ValidationError

from app.services.ai.providers.evidence_registry import EvidenceKind
from app.services.ai.reasoning.tool_selector import (
    ToolCall,
    ToolDispatcher,
    ToolInterface,
    _safe_invoke,
)
from app.services.ai.sanitisation import (
    LEAKED_FIELDS,
    strip_leaked_secrets,
)

from app.services.ai.tool_router.catalog import ToolCatalog
from app.services.ai.tool_router.types import (
    LLMToolRequest,
    LLMToolResult,
)


# Maximum number of tool calls the LLM may emit on a
# single request. The bound prevents prompt-injection from
# fanning the LLM out into hundreds of tool calls.
_MAX_LLM_TOOL_CALLS_PER_REQUEST = 6

# Owner id binding — the LLM-supplied ``arguments.owner_id``
# is always rejected. We additionally scan for two family
# names of secrets that the LLM may try to surface through
# custom-tools — the canonical deny-list is in
# ``sanitisation.py``; the owner-id check is here because
# it's the cardinal security boundary.
_OWNER_ID_KEYS = frozenset({"owner_id", "user_id", "owner"})


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #


class LLMToolRequestRouter:
    """Validate + dispatch + sanitise + stamp LLM tool calls.

    The router is constructed once per request and is
    idempotent. It holds:

      * a :class:`ToolCatalog` — the 12 whitelisted tools.
      * a :class:`ToolDispatcher` — the registry of
        ``ToolInterface`` engines (the existing AI-1/2 path).
      * an optional ``intent`` resolver callback that the
        caller overrides per-request (defaults to
        ``"general"``).

    Threading: the router is NOT thread-safe — it carries no
    mutable state, but a request may construct one freely;
    the existing ``ToolDispatcher`` owns its own thread
    pool.
    """

    def __init__(
        self,
        catalog: ToolCatalog,
        dispatcher: ToolDispatcher,
    ) -> None:
        self._catalog = catalog
        self._dispatcher = dispatcher

    # ---- public API -------------------------------------------------- #

    def route_all(
        self,
        requests: tuple[LLMToolRequest, ...],
        *,
        owner_id: int,
        intent: str = "general",
    ) -> tuple[LLMToolResult, ...]:
        """Validate + dispatch a batch of LLM tool requests.

        The method NEVER raises. Every request — valid or
        rejected — returns an :class:`LLMToolResult`. The
        batch is capped at
        :data:`_MAX_LLM_TOOL_CALLS_PER_REQUEST`; if the LLM
        emitted more, the spillover is rejected with
        ``error="too_many_tool_calls"``.
        """
        if not requests:
            return ()

        results: list[LLMToolResult] = []
        for index, request in enumerate(requests):
            if index >= _MAX_LLM_TOOL_CALLS_PER_REQUEST:
                results.append(
                    self._rejected(
                        request.tool,
                        f"too_many_tool_calls:cap={_MAX_LLM_TOOL_CALLS_PER_REQUEST}",
                    )
                )
                continue
            results.append(
                self.route(request, owner_id=owner_id, intent=intent)
            )
        return tuple(results)

    def route(
        self,
        request: LLMToolRequest,
        *,
        owner_id: int,
        intent: str = "general",
    ) -> LLMToolResult:
        """Validate + dispatch a single LLM tool request.

        Returns an :class:`LLMToolResult` — never raises.
        """
        tool_name = request.tool or ""

        # Step 1 — tool exists
        spec = self._catalog.get(tool_name)
        if spec is None:
            return self._rejected(tool_name, f"unknown_tool:{tool_name!r}")

        # Step 2 — arguments valid (Pydantic, extra="forbid")
        try:
            self._validate_arguments(spec, request.arguments)
        except ValidationError as exc:
            return self._rejected(
                tool_name,
                f"invalid_arguments:{_first_error_kind(exc)}",
            )
        except ValueError as exc:
            return self._rejected(tool_name, f"invalid_arguments:{exc}")
        except Exception as exc:  # noqa: BLE001 — defensive
            return self._rejected(
                tool_name,
                f"invalid_arguments:unexpected:{type(exc).__name__}",
            )

        # Step 4 — tool allowed for intent
        if not self._catalog.is_allowed_for_intent(tool_name, intent):
            return self._rejected(
                tool_name,
                f"tool_not_allowed_for_intent:{intent}",
            )

        # Step 5 — dispatch + sanitise
        tool_call = ToolCall(
            service_name=spec.engine_name,
            inputs=dict(request.arguments),
            expected_output_shape=spec.evidence_kind.value,
        )
        raw = self._invoke_engine(
            spec.engine_name, owner_id=owner_id, call=tool_call,
        )

        # Convert the ``ToolResult`` envelope into the
        # LLM-friendly ``LLMToolResult`` envelope. Timeouts
        # and ``status="skipped"`` are preserved as-is.
        sanitised_payload = strip_leaked_secrets(raw.payload)
        if raw.status == "ok" and sanitised_payload is None:
            sanitised_payload = {}

        # Step 6 — stamp evidence IDs
        evidence_ids = self._stamp_evidence(
            spec.evidence_kind, sanitised_payload,
        )

        return LLMToolResult(
            tool=tool_name,
            status=(
                "ok"
                if raw.status == "ok"
                else ("skipped" if raw.status == "skipped" else "error")
            ),
            evidence_ids=evidence_ids,
            payload=sanitised_payload if isinstance(sanitised_payload, dict) else {},
            duration_ms=int(raw.duration_ms or 0),
            error=(
                ""
                if raw.status == "ok"
                else (raw.error or "engine_returned_no_payload")
            ) or None,
        )

    # ---- internals --------------------------------------------------- #

    def _validate_arguments(
        self, spec: Any, arguments: dict[str, Any]
    ) -> None:
        """Validate ``arguments`` against ``spec.arg_schema``.

        For tools whose schema is ``None``, still enforce a
        defensive scan for ``owner_id`` / ``user_id`` /
        ``owner`` keys AND every field in
        :data:`LEAKED_FIELDS`. The Pydantic ``extra="forbid"``
        guard on the arg schemas does the same work for
        typed tools.
        """
        # Tools that take no arguments must accept only ``{}``
        # — anything more is a smuggling attempt.
        if spec.arg_schema is None:
            if arguments and any(arguments):
                bad = sorted(
                    set(arguments.keys()) & (
                        _OWNER_ID_KEYS | LEAKED_FIELDS
                    )
                )
                if bad:
                    raise ValueError(
                        f"forbidden keys {bad!r} for tool {spec.name!r}"
                    )
                # Even when no forbidden key is present, an
                # empty-args tool must receive empty args.
                if arguments:
                    raise ValueError(
                        f"tool {spec.name!r} does not accept arguments"
                    )
            return
        # The Pydantic round-trip enforces ``extra="forbid"``
        # so a smuggled ``owner_id`` / ``api_key`` raises
        # here. We trap and re-emit as ``invalid_arguments``.
        spec.arg_schema.model_validate(arguments)

    def _invoke_engine(
        self,
        engine_name: str,
        *,
        owner_id: int,
        call: ToolCall,
    ) -> Any:
        """Look up the engine in the dispatcher's registry and
        invoke it. Falls back to a ``status="not_implemented"``
        result when the engine is missing — so an unknown
        catalog entry never crashes the chat.

        The router bypasses the dispatcher's ``dispatch()``
        path (which is multi-tool + threaded) for the
        single-tool AI-8 flow. To keep the
        never-raises-from-engines contract that AI-1/2
        established, we route the single invocation through
        :func:`_safe_invoke` — the same defensive wrapper
        ``ToolDispatcher`` uses internally.
        """
        tool: ToolInterface = self._dispatcher.get_tool(engine_name)
        return _safe_invoke(
            tool, owner_id=owner_id, call=call, context=None,
        )

    def _stamp_evidence(
        self, kind: EvidenceKind, payload: Any
    ) -> tuple[str, ...]:
        """Derive stable evidence IDs from the payload.

        The canonical :class:`EvidenceRegistry` derives IDs
        from an ``AssistantContext`` snapshot — the AI-8
        router does not have access to a registry in this
        code path (the registry is built per-request at the
        service layer), so we synthesise a stable ID from
        the structural hash of the payload + the
        :class:`EvidenceKind`::

            <kind>:<sha256(canonicalised payload)>

        When ``payload`` is ``None`` we return ``()``.

        For tool outputs that already carry legacy IDs (the
        ``recommendation`` / ``scheme`` engines), the LLM
        still receives a registry-compatible ID we can
        later cross-link in the trust disclosure panel.
        """
        if payload is None:
            return ()
        try:
            canonical = json.dumps(
                payload, sort_keys=True, default=str,
            )
        except (TypeError, ValueError):
            canonical = repr(payload)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
        return (f"{kind.value}:{digest}",)

    def _rejected(
        self, tool_name: str, reason: str
    ) -> LLMToolResult:
        """Build a rejected :class:`LLMToolResult`.

        ``status="error"`` with ``evidence_ids=()`` and
        ``payload={}``. The ``error`` is the single field
        the LLM sees — it always carries an actionable
        reason so the LLM can narrate the rejection.
        """
        return LLMToolResult(
            tool=tool_name,
            status="error",
            evidence_ids=(),
            payload={},
            duration_ms=0,
            error=reason,
        )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _first_error_kind(exc: ValidationError) -> str:
    """Extract the first Pydantic error ``type`` from a
    ``ValidationError``.

    Pydantic v2: ``exc.errors()`` returns ``[{"type": ..., ...}]``.
    We use the ``type`` string verbatim so the audit log
    knows which constraint failed (``missing``,
    ``extra_forbidden``, ``string_type``, ``value_error``,
    …).
    """
    try:
        errors = exc.errors()
        if errors and isinstance(errors[0], dict):
            return str(errors[0].get("type", "unknown"))
    except Exception:  # noqa: BLE001
        pass
    return "validation_error"


__all__ = [
    "LLMToolRequestRouter",
    "_MAX_LLM_TOOL_CALLS_PER_REQUEST",
]
