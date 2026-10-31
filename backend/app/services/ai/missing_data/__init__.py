"""SPRINT AI-7 — Missing-data intelligence package.

Public surface:

    from app.services.ai.missing_data import (
        MissingDataObject,
        FieldRequirement,
        detect_missing_data,
        detect_missing_data_from_mapping,
        enrich_missing_data_from_prose,
        render_what_i_can_tell,
        to_payload,
        from_payload,
    )

The detector is a **pure function**. The enrichment pass is also
pure. The render helper is pure. No I/O. No side effects. Every
prompt + every AssistantContext snapshot maps deterministically to
the same ``tuple[MissingDataObject, ...]`` — the same property the
H7.9R+ intent_router has.

The proactive path (``detect_missing_data``) runs BEFORE the
provider call (ConversationService step 3.7). The reactive path
(``enrich_missing_data_from_prose``) runs AFTER the provider
returns so the LLM can add rows the proactive detector missed.
The deterministic fallback keeps only the proactive rows — the
LLM was never called, so there is nothing to enrich.

Wire contract:
    {"field": str, "importance": "LOW|MEDIUM|HIGH",
     "reason": str, "affects": list[str],
     "suggested_source": str}

Mirrored on ``chat_message.missing_data`` and the Pydantic
``ChatMessageOut.missing_data`` / ``ChatGenerationMeta.missing_data``
in ``backend/app/schemas/chat.py``.
"""
from __future__ import annotations

from .detector import (
    FieldRequirement,
    MissingDataObject,
    _REQUIRED_BY_INTENT,
    detect_missing_data,
    detect_missing_data_from_mapping,
    from_payload,
    to_payload,
)
from .enrichment import enrich_missing_data_from_prose
from .render import render_what_i_can_tell

__all__ = [
    "FieldRequirement",
    "MissingDataObject",
    "_REQUIRED_BY_INTENT",
    "detect_missing_data",
    "detect_missing_data_from_mapping",
    "enrich_missing_data_from_prose",
    "from_payload",
    "render_what_i_can_tell",
    "to_payload",
]
