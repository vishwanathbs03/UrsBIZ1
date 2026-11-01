"""Resilient Gemini API Client (Phase 5 Platform Resilience).

Provides bounded retries with exponential backoff and jitter, strict request timeouts,
circuit breaker fail-fast protection, and structured JSON response validation.
Never presents incomplete, malformed, or fabricated responses as successful results.
"""

from __future__ import annotations

import json
import logging
import random
import time
from typing import Any, Callable, Optional
import httpx

from app.config.settings import get_settings
from app.core.errors import (
    AIRateLimitError,
    AIServiceUnavailableError,
    AITimeoutError,
)
from app.services.ai.providers.circuit_breaker import AICircuitBreaker

logger = logging.getLogger("atlas.ai.resilience")

# Process-level circuit breaker singleton for Gemini API calls
_GEMINI_CIRCUIT_BREAKER = AICircuitBreaker(
    name="gemini_api",
    max_failures=3,
    cooldown_seconds=30.0,
    max_transient_retries=2,
)


def get_gemini_circuit_breaker() -> AICircuitBreaker:
    """Return the global Gemini circuit breaker instance."""
    return _GEMINI_CIRCUIT_BREAKER


class ResilientGeminiClient:
    """Outbound Gemini caller with backoff, jitter, timeouts, and circuit breaker."""

    def __init__(
        self,
        base_delay_seconds: float = 0.5,
        max_delay_seconds: float = 4.0,
        max_retries: int = 2,
        timeout_seconds: float = 8.0,
        circuit_breaker: Optional[AICircuitBreaker] = None,
        settings: Optional[Any] = None,
    ) -> None:
        self.base_delay = base_delay_seconds
        self.max_delay = max_delay_seconds
        self.max_retries = max_retries
        self.timeout = timeout_seconds
        self.cb = circuit_breaker or _GEMINI_CIRCUIT_BREAKER
        self._settings = settings

    def calculate_backoff(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """Calculate exponential backoff with random jitter."""
        if retry_after is not None and retry_after > 0:
            return min(self.max_delay, retry_after)
        delay = self.base_delay * (2 ** attempt)
        jitter = random.uniform(0, 0.25 * self.base_delay)
        return min(self.max_delay, delay + jitter)

    def execute_chat_completion(
        self,
        system_prompt: str,
        user_content: str,
        max_tokens: int = 400,
        temperature: float = 0.2,
        require_json: bool = False,
    ) -> Optional[str]:
        """Execute a chat completion with retries, backoff, and circuit breaker.

        Returns string content on success, or None if provider is unavailable / failed.
        """
        settings = self._settings or get_settings()

        # If not configured or placeholder, skip outbound call immediately
        if not settings.ai_api_key or settings.ai_provider == "placeholder":
            return None

        # Check circuit breaker before opening connection
        if not self.cb.allow_request():
            logger.warning("[gemini_resilience] Circuit breaker OPEN. Skipping call, switching to fallback.")
            return None

        headers = {
            "Authorization": f"Bearer {settings.ai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.ai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        url = f"{settings.ai_base_url.rstrip('/')}/chat/completions"

        attempts = 0
        total_attempts = self.max_retries + 1

        while attempts < total_attempts:
            attempts += 1
            try:
                with httpx.Client(timeout=httpx.Timeout(self.timeout, connect=3.0)) as client:
                    resp = client.post(url, headers=headers, json=payload)

                    if resp.status_code == 200:
                        data = resp.json()
                        choices = data.get("choices", [])
                        if not choices:
                            raise ValueError("Gemini response missing choices.")

                        content = choices[0].get("message", {}).get("content", "").strip()

                        if require_json:
                            # Validate JSON structure
                            parsed = self.extract_and_validate_json(content)
                            if parsed is None:
                                logger.warning("[gemini_resilience] Malformed JSON received from Gemini.")
                                raise ValueError("Malformed JSON in LLM response.")

                        self.cb.record_success()
                        return content

                    elif resp.status_code == 429:
                        # Rate limit
                        retry_after_hdr = resp.headers.get("Retry-After")
                        retry_after_val = float(retry_after_hdr) if retry_after_hdr and retry_after_hdr.isdigit() else None
                        logger.warning(
                            f"[gemini_resilience] Rate limit 429 on attempt {attempts}/{total_attempts}. "
                            f"Retry-After: {retry_after_val}s"
                        )
                        if attempts < total_attempts:
                            sleep_time = self.calculate_backoff(attempts - 1, retry_after_val)
                            time.sleep(sleep_time)
                            continue
                        else:
                            self.cb.record_failure(AIRateLimitError())
                            return None

                    elif resp.status_code in {500, 502, 503, 504}:
                        # Transient server error
                        logger.warning(
                            f"[gemini_resilience] Transient status {resp.status_code} on attempt {attempts}/{total_attempts}."
                        )
                        if attempts < total_attempts:
                            sleep_time = self.calculate_backoff(attempts - 1)
                            time.sleep(sleep_time)
                            continue
                        else:
                            self.cb.record_failure(AIServiceUnavailableError())
                            return None

                    elif resp.status_code in {401, 403}:
                        # Auth failure — do not retry
                        logger.error(f"[gemini_resilience] Auth error {resp.status_code}. Halting retries.")
                        self.cb.record_failure(ValueError(f"Auth failure: {resp.status_code}"))
                        return None

                    else:
                        logger.warning(f"[gemini_resilience] Non-retryable status {resp.status_code}: {resp.text}")
                        self.cb.record_failure(ValueError(f"HTTP {resp.status_code}"))
                        return None

            except (httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                logger.warning(f"[gemini_resilience] Timeout on attempt {attempts}/{total_attempts}: {exc}")
                if attempts < total_attempts:
                    sleep_time = self.calculate_backoff(attempts - 1)
                    time.sleep(sleep_time)
                    continue
                else:
                    self.cb.record_failure(AITimeoutError())
                    return None

            except Exception as exc:
                logger.warning(f"[gemini_resilience] Outbound call error on attempt {attempts}/{total_attempts}: {exc}")
                if attempts < total_attempts:
                    sleep_time = self.calculate_backoff(attempts - 1)
                    time.sleep(sleep_time)
                    continue
                else:
                    self.cb.record_failure(exc)
                    return None

        return None

    @staticmethod
    def extract_and_validate_json(raw_text: str) -> Optional[dict[str, Any]]:
        """Safely extract and parse JSON from raw text, removing markdown fences if present."""
        clean = raw_text.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()

        try:
            val = json.loads(clean)
            if isinstance(val, dict):
                return val
            return None
        except Exception:
            return None
