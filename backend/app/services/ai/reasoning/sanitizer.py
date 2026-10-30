"""ConclusionSanitizer — Sprint H8.3 Clean conclusions & thinking isolation."""

from __future__ import annotations

import re


class ConclusionSanitizer:
    """Sanitizes model and fallback outputs to ensure unexposed reasoning and clean conclusions."""

    # Matches thinking fences or reasoning artifacts that must never leak to UI
    _THINK_FENCE_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
    _REASONING_BLOCK_RE = re.compile(r"\[REASONING\].*?\[/REASONING\]", re.DOTALL | re.IGNORECASE)
    _EXPLICIT_STEP_RE = re.compile(r"^(?:Step \d+:|Hypothesis \d+:|Internal trace:).*$", re.MULTILINE | re.IGNORECASE)

    def sanitize(self, text: str) -> str:
        """Sanitize text to expose conclusions only and collapse extraneous whitespace."""
        if not text or not text.strip():
            return ""

        cleaned = text
        # 1. Strip think tags and internal reasoning blocks
        cleaned = self._THINK_FENCE_RE.sub("", cleaned)
        cleaned = self._REASONING_BLOCK_RE.sub("", cleaned)
        cleaned = self._EXPLICIT_STEP_RE.sub("", cleaned)

        # 2. Collapse multi-line whitespace (max 2 consecutive newlines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        # 3. Strip trailing whitespace from each line
        lines = [line.rstrip() for line in cleaned.splitlines()]
        cleaned = "\n".join(lines).strip()

        return cleaned
