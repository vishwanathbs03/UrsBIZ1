"""Provider Circuit Breaker & Resiliency — Sprint H7.9-R.

Manages provider health state to prevent infinite retries or cascade failures
when Gemini or external LLM endpoints experience quota exhaustion (429), auth errors,
or transient outages.

States:
  - CLOSED: Normal operation. Requests execute normally.
  - OPEN: Provider unavailable due to repeated failures. LLM requests are short-circuited.
  - HALF_OPEN: Cooldown expired. Allows a single probe request to test provider recovery.
"""
from __future__ import annotations

import logging
import time
from typing import Callable, Literal, TypeVar

from app.services.ai.providers.base import (
    AIProviderError,
    ProviderAuthError,
    ProviderConfigError,
    ProviderHTTPStatusError,
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

logger = logging.getLogger("atlas.ai.circuit_breaker")

CircuitState = Literal["CLOSED", "OPEN", "HALF_OPEN"]
T = TypeVar("T")


class AICircuitBreaker:
    """In-memory Circuit Breaker for LLM providers."""

    def __init__(
        self,
        name: str = "gemini",
        max_failures: int = 3,
        cooldown_seconds: float = 30.0,
        max_transient_retries: int = 1,
    ) -> None:
        self.name = name
        self.max_failures = max_failures
        self.cooldown_seconds = cooldown_seconds
        self.max_transient_retries = max_transient_retries

        self._state: CircuitState = "CLOSED"
        self._failure_count: int = 0
        self._last_opened_at: float = 0.0

    @property
    def state(self) -> CircuitState:
        if self._state == "OPEN":
            if time.time() - self._last_opened_at >= self.cooldown_seconds:
                self._state = "HALF_OPEN"
                logger.info(f"[circuit_breaker:{self.name}] Cooldown expired. State -> HALF_OPEN (probing)")
        return self._state

    def allow_request(self) -> bool:
        """Returns True if a request should be attempted, False if short-circuited."""
        current_state = self.state
        if current_state == "CLOSED":
            return True
        if current_state == "HALF_OPEN":
            return True
        return False

    def record_success(self) -> None:
        """Record a successful response from the provider."""
        if self._state != "CLOSED":
            logger.info(f"[circuit_breaker:{self.name}] Probe succeeded! State -> CLOSED")
        self._state = "CLOSED"
        self._failure_count = 0

    def record_failure(self, error: Exception) -> None:
        """Record a provider failure."""
        self._failure_count += 1
        logger.warning(
            f"[circuit_breaker:{self.name}] Provider failure #{self._failure_count}: {error}"
        )

        # Immediate OPEN on auth/config or after threshold
        if (
            isinstance(error, (ProviderAuthError, ProviderConfigError, ProviderQuotaError))
            or self._failure_count >= self.max_failures
            or self._state == "HALF_OPEN"
        ):
            self._state = "OPEN"
            self._last_opened_at = time.time()
            logger.error(
                f"[circuit_breaker:{self.name}] Threshold reached. Circuit -> OPEN for {self.cooldown_seconds}s"
            )

    def execute_with_resilience(self, func: Callable[[], T]) -> T:
        """Execute callable with bounded retries and circuit breaker protection."""
        if not self.allow_request():
            raise ProviderUnavailableError(f"Circuit breaker for {self.name} is OPEN")

        retries = 0
        while True:
            try:
                res = func()
                self.record_success()
                return res
            except (ProviderAuthError, ProviderConfigError, ProviderQuotaError) as exc:
                self.record_failure(exc)
                raise
            except (ProviderUnavailableError, ProviderTimeoutError, ProviderHTTPStatusError) as exc:
                if retries < self.max_transient_retries:
                    retries += 1
                    backoff = 0.2 * (2 ** (retries - 1))
                    logger.info(f"[circuit_breaker:{self.name}] Transient error: {exc}. Retrying ({retries}/{self.max_transient_retries}) after {backoff}s...")
                    time.sleep(backoff)
                    continue
                self.record_failure(exc)
                raise
            except Exception as exc:
                self.record_failure(exc)
                raise
