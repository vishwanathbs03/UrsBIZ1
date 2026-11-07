"""Business Continuity & Graceful Degradation Service (Phase 6.30).

Provides centralized monitoring and coordination for platform resiliency:
1. LLM provider circuit breaker state tracking (Gemini 2.0 Flash / external providers).
2. Transparent failover to DeterministicFallbackProvider upon timeouts, rate limits, or 5xx.
3. Graceful degradation for database and downstream service outages (preserving read-only dashboard access).
4. Status signaling for user interfaces in both English and Kannada.
"""

from __future__ import annotations

import logging
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.monitoring.health import _probe_database, _probe_knowledge
from app.services.ai.resilient_client import get_gemini_circuit_breaker

logger = logging.getLogger("atlas.continuity")

ContinuityMode = Literal["OPERATIONAL", "RULE_ENGINE_FALLBACK", "DEGRADED_READONLY", "OFFLINE"]


class DatabaseContinuityStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok", "degraded"]
    mode: Literal["read_write", "read_only"]
    detail: str


class AISubsystemContinuityStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["operational", "degraded", "offline"]
    provider: str
    circuit_breaker: Literal["CLOSED", "OPEN", "HALF_OPEN"]
    fallback_active: bool
    metrics: dict[str, Any]


class KnowledgeContinuityStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok", "degraded"]
    detail: str


class SystemContinuityStatus(BaseModel):
    """Complete platform continuity and operational degradation snapshot."""

    model_config = ConfigDict(extra="forbid")

    system_mode: ContinuityMode
    database: DatabaseContinuityStatus
    ai_subsystem: AISubsystemContinuityStatus
    knowledge: KnowledgeContinuityStatus
    active_safeguards: list[str]
    notice_en: str
    notice_kn: str
    can_read: bool
    can_write: bool


class ContinuitySimulationRequest(BaseModel):
    """Request schema for resilience & disaster drill simulations."""

    model_config = ConfigDict(extra="forbid")
    action: Literal["trip_ai_circuit", "reset_ai_circuit", "simulate_db_degraded", "reset_all"]


class ContinuityService:
    """Evaluates and manages multi-subsystem resilience and continuity."""

    _SIMULATED_DB_DEGRADED: bool = False

    @classmethod
    def get_status(cls) -> SystemContinuityStatus:
        """Inspect all subsystems and compute the overall continuity posture."""
        # 1. Database Subsystem
        if cls._SIMULATED_DB_DEGRADED:
            db_ok = False
            db_detail = "Simulated database degradation active for continuity drill."
        else:
            db_ok, db_detail = _probe_database()

        db_status = DatabaseContinuityStatus(
            status="ok" if db_ok else "degraded",
            mode="read_write" if db_ok else "read_only",
            detail=db_detail,
        )

        # 2. AI Subsystem & Circuit Breaker
        cb = get_gemini_circuit_breaker()
        cb_metrics = cb.get_metrics()
        cb_state = cb_metrics["state"]
        ai_fallback_active = cb_state != "CLOSED"

        ai_status = AISubsystemContinuityStatus(
            status="operational" if cb_state == "CLOSED" else "degraded",
            provider="gemini",
            circuit_breaker=cb_state,
            fallback_active=ai_fallback_active,
            metrics=cb_metrics,
        )

        # 3. Knowledge Subsystem
        know_ok, know_detail = _probe_knowledge()
        know_status = KnowledgeContinuityStatus(
            status="ok" if know_ok else "degraded",
            detail=know_detail,
        )

        # 4. Compute holistic system mode & safeguards
        safeguards: list[str] = []
        if not db_ok:
            safeguards.append("STALE_SNAPSHOT_DASHBOARD_FALLBACK")
            safeguards.append("READ_ONLY_TRANSACTION_LOCK")
        if ai_fallback_active:
            safeguards.append("LLM_CIRCUIT_BREAKER_ACTIVE")
            safeguards.append("DETERMINISTIC_RULES_ENGAGED")
            safeguards.append("ZERO_HALLUCINATION_GUARANTEE")

        if not db_ok and ai_fallback_active:
            system_mode: ContinuityMode = "DEGRADED_READONLY"
            notice_en = "Operating in resilient read-only and rule-engine fallback mode during infrastructure degradation."
            notice_kn = "ಮೂಲಸೌಕರ್ಯ ವ್ಯತ್ಯಯದ ಸಮಯದಲ್ಲಿ ಸಿಸ್ಟಮ್ ಓದಲು-ಮಾತ್ರ ಮತ್ತು ನಿಯಮ ಎಂಜಿನ್ ಫಾಲ್‌ಬ್ಯಾಕ್ ಮೋಡ್‌ನಲ್ಲಿ ಕಾರ್ಯನಿರ್ವಹಿಸುತ್ತಿದೆ."
        elif not db_ok:
            system_mode = "DEGRADED_READONLY"
            notice_en = "Database is degraded. Serving cached historical metrics in read-only mode."
            notice_kn = "ಡೇಟಾಬೇಸ್ ವ್ಯತ್ಯಯವಾಗಿದೆ. ಇತಿಹಾಸದ ದತ್ತಾಂಶವನ್ನು ಓದಲು-ಮಾತ್ರ ಮೋಡ್‌ನಲ್ಲಿ ಪ್ರದರ್ಶಿಸಲಾಗುತ್ತಿದೆ."
        elif ai_fallback_active:
            system_mode = "RULE_ENGINE_FALLBACK"
            notice_en = "Rule Engine Mode: External Gemini provider in cooldown. Operating on verified deterministic mathematical formulas with zero hallucination."
            notice_kn = "ನಿಯಮ ಎಂಜಿನ್ ಮೋಡ್: ಬಾಹ್ಯ AI ಒದಗಿಸುವವರಲ್ಲಿ ತಾತ್ಕಾಲಿಕ ವ್ಯತ್ಯಯ. ದೃಢೀಕರಿಸಿದ ಗಣಿತೀಯ ಸೂತ್ರಗಳ ಮೂಲಕ ವಿಶ್ಲೇಷಣೆ ನೀಡಲಾಗುತ್ತಿದೆ (ಶೂನ್ಯ ಕಲ್ಪನೆ)."
        else:
            system_mode = "OPERATIONAL"
            notice_en = "All platform subsystems operational."
            notice_kn = "ಎಲ್ಲಾ ಸಿಸ್ಟಮ್ ಉಪವ್ಯವಸ್ಥೆಗಳು ಸುಸ್ಥಿತಿಯಲ್ಲಿ ಕಾರ್ಯನಿರ್ವಹಿಸುತ್ತಿವೆ."

        return SystemContinuityStatus(
            system_mode=system_mode,
            database=db_status,
            ai_subsystem=ai_status,
            knowledge=know_status,
            active_safeguards=safeguards,
            notice_en=notice_en,
            notice_kn=notice_kn,
            can_read=True,
            can_write=db_ok,
        )

    @classmethod
    def simulate_action(cls, action: str) -> SystemContinuityStatus:
        """Execute a resilience drill simulation action."""
        cb = get_gemini_circuit_breaker()
        if action == "trip_ai_circuit":
            cb.trip(reason="Drill simulation: Gemini quota exhausted (429)")
        elif action == "reset_ai_circuit":
            cb.reset()
        elif action == "simulate_db_degraded":
            cls._SIMULATED_DB_DEGRADED = True
        elif action == "reset_all":
            cb.reset()
            cls._SIMULATED_DB_DEGRADED = False
        else:
            raise ValueError(f"Unknown simulation action: {action}")

        return cls.get_status()
