"""Sanitisation guard — promoted from `conversation_service.py` (H7.8C).

The H7.8C leak guard was originally a private constant on
``ConversationService``. SPRINT AI-8 promotes it to a
shared module so both the chat service AND the new
``LLMToolRequestRouter`` (AI-8) can sanitise tool outputs
through the same source of truth — every deterministic
engine payload has to pass through this filter before the
LLM sees it.

Backwards compatibility
------------------------

``app.services.chat.conversation_service`` re-exports the
two public helpers (``_LEAKED_FIELDS`` and
``_assert_no_leaked_secrets``) verbatim so existing imports
keep working. The new code (AI-8 router, etc.) imports
from this module directly.

The brief is explicit: the assistant response NEVER exposes
API keys, authorization headers, base URLs, or upstream
URLs. The original guard raised on any leak (intentional —
the boundary check should crash, not silently drop). AI-8
adds a separate ``_strip_leaked_secrets`` helper for the
TOOL-OUTPUT path — there, dropping a key (rather than
crashing the chat) is the right behaviour because the
deterministic engine may legitimately have these fields
in its internal config dict, and we just don't want them
fed back into the LLM's context window.
"""
from __future__ import annotations

from typing import Any


# --------------------------------------------------------------------------- #
# Fields that MUST NEVER appear in a wire payload
# --------------------------------------------------------------------------- #


# AI-8 — promote the H7.8C deny-list from
# ``conversation_service`` so the router (which has no
# other reason to import the chat service) can use the
# same source of truth. Adding a new sensitive key here
# is a non-breaking change (it just adds another field to
# the leak guard). Removing a key is a breaking change
# for the audit trail.
LEAKED_FIELDS: frozenset[str] = frozenset(
    {
        "api_key",
        "authorization",
        "auth_header",
        "base_url",
        "upstream_url",
        "secret",
        "bearer",
        "access_token",
    }
)


# --------------------------------------------------------------------------- #
# H7.8C leak guard — RAISE on any leak (wire-path invariant)
# --------------------------------------------------------------------------- #


def assert_no_leaked_secrets(payload: dict | None, *, where: str) -> None:
    """Raise ``ValueError`` if ``payload`` contains any key in
    :data:`LEAKED_FIELDS`.

    H7.8C — the brief mandates that the assistant response
    NEVER exposes API keys, authorization headers, or base
    URLs. The audit-fixed provider layer never includes these
    fields, but a future refactor could accidentally paste a
    config dict into the payload. This guard catches that
    regression at the projection boundary, in the same place
    that fixes the brief, so any future change is forced to
    think about the leak surface.

    Parameters
    ----------
    payload:
        The dict the serializer is about to emit (either the
        ``generation`` envelope or the top-level message
        payload). ``None`` is a no-op.
    where:
        Short label used in the error message so the audit
        log knows which surface leaked.
    """
    if not payload:
        return
    leaked = set(payload.keys()) & LEAKED_FIELDS
    if leaked:
        raise ValueError(
            f"H7.8C leak guard tripped at {where}: "
            f"refusing to serialise payload containing "
            f"secrets: {sorted(leaked)!r}"
        )


# --------------------------------------------------------------------------- #
# AI-8 tool-output sanitiser — STRIP leaked keys (LLM-feedback path)
# --------------------------------------------------------------------------- #


def strip_leaked_secrets(payload: Any) -> Any:
    """Return a shallow copy of ``payload`` with every key in
    :data:`LEAKED_FIELDS` removed.

    The H7.8C guard *raises* on a leak — appropriate at the
    wire-projection boundary, where a leak means a code bug.
    AI-8 introduces a *softer* path: when a deterministic
    engine returns internal config alongside its public data
    (e.g. ``{"upstream_url": "...", "schemes": [...]}``), the
    router must NOT raise (the chat would crash on every
    request) — it must DROP the secret field before feeding
    the payload back to the LLM as a 2nd-turn tool message.

    The function walks dicts, lists, and tuples recursively so
    a leaked field nested anywhere in the payload is dropped.
    Strings, numbers, ``None``, and other scalars pass through
    unchanged.

    Parameters
    ----------
    payload:
        Arbitrary structured value (typically a dict from
        a ``ToolResult.payload``). ``None`` returns ``None``.

    Returns
    -------
    A JSON-safe copy with every ``LEAKED_FIELDS`` key
    removed at every depth.
    """
    if payload is None:
        return None
    if isinstance(payload, dict):
        out: dict = {}
        for key, value in payload.items():
            if key in LEAKED_FIELDS:
                continue
            out[key] = strip_leaked_secrets(value)
        return out
    if isinstance(payload, list):
        return [strip_leaked_secrets(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(strip_leaked_secrets(item) for item in payload)
    return payload


__all__ = [
    "LEAKED_FIELDS",
    "assert_no_leaked_secrets",
    "strip_leaked_secrets",
]
