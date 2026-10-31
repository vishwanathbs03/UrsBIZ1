"""Application configuration loader.

Centralizes environment-driven settings using pydantic-settings.
Loaded once at startup and shared across the app via get_settings().
"""

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "UrsBiz"
    app_env: str = "development"
    app_debug: bool = True
    app_version: str = "1.0.0"
    
    _resolved_from_version_file: bool = False

    @field_validator("app_version", mode="before")
    @classmethod
    def _read_version_file(cls, v: object) -> object:
        if isinstance(v, str) and v.strip():
            return v
        from pathlib import Path
        here = Path(__file__).resolve()
        for ancestor in [here.parent, *here.parents]:
            candidate = ancestor / "VERSION"
            if candidate.is_file():
                try:
                    return candidate.read_text(encoding="utf-8").strip()
                except OSError:
                    pass
        return "1.0.0"

    app_host: str = "0.0.0.0"
    app_port: int = 8001

    # CORS
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Logging
    log_level: str = "INFO"

    # Database
    database_url: str = "sqlite:///./ursbiz_prod.db"
    database_echo: bool = False

    # AI provider layer
    ai_provider: str = "placeholder"
    ai_api_key: str = ""

    # Ollama-specific
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2:3b"

    # OpenAI-compatible / Gemini provider layer configuration
    ai_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    # H7.9R+ — Gemini model family. Earlier committed defaults
    # (``gemini-3.6-flash`` which is not a real Google model, and
    # ``gemini-1.5-flash`` which is no longer reliably served on
    # the OpenAI-compatible endpoint) caused the factory to mark
    # the upstream as "configured" while every chat call failed
    # with 404. The verified working model on the OpenAI-compatible
    # endpoint is ``gemini-2.0-flash`` (also accepted:
    # ``gemini-2.5-flash`` once the operator verifies it on their
    # key). Change this in ``.env`` (or the deployment's secret
    # manager) for newer models — never in code paths that ship
    # binaries.
    ai_model: str = "gemini-2.0-flash"
    ai_request_timeout_seconds: float = 180.0
    ai_hard_call_timeout_seconds: float = 240.0

    ai_require_schema: bool = True

    # H8.11 — wall-clock cap for a single outbound LLM call.
    # This is the *outer* ceiling enforced by
    # ``AssistantProviderService._call_with_hard_timeout``,
    # above the provider's own per-request httpx timeout
    # (``ai_request_timeout_seconds``). It guarantees that
    # no chat request can ever hold a worker thread for
    # longer than this many seconds regardless of retry
    # behaviour in the circuit breaker. The previous
    # hard-coded 15 s value was sized for a Gemini-class
    # upstream; llama3.2:3b on the 5.9 GB judge host
    # legitimately takes 90 s for a full grounded-mode
    # prompt (cold load + prompt-eval of the 12-section
    # schema + business snapshot + JSON generation, measured
    # empirically on 2026-08-14 with
    # ``scripts/debug/h8_11_measure_real_prompt.py``). The
    # 45 s value raised in the H8.11 plan still fell back on
    # every prompt; the 120 s default left ~30 s headroom
    # but still fired on the longest prompts (measured 163 s
    # on the 5.9 GB judge host during the H8.11 gate run on
    # 2026-08-14). The default is now 200 s to leave ~40 s
    # headroom over the worst observed end-to-end latency.
    # The provider's inner ``AI_REQUEST_TIMEOUT_SECONDS``
    # (also raised to 200 s in production) remains the
    # authoritative cap if the upstream truly hangs.
    ai_hard_call_timeout_seconds: float = 200.0

    # H7.8C — additional AI tunables that were previously hard-coded
    # constants inside the providers/chat layers. All four have safe
    # defaults — leave them alone unless you have a reason to tune.
    # See ``backend/.env.example`` for the full docstrings.
    ai_grounding_threshold: float = 50.0
    ai_default_mode: str = "grounded"
    ai_max_history_turns: int = 8
    knowledge_retrieval_top_k: int = 3
    ursbiz_demo_mode: bool = True
    ai_secondary_provider: str = ""

    # Authentication
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cookie_httponly: bool = True

    # Security hardening knobs
    trusted_proxy_hops: int = 1
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    rate_limit_endpoint_overrides: str = (
        "/api/v1/business/ocr:10,/api/v1/business/ocr/apply:10,"
        "/api/v1/auth/login:10,/api/v1/auth/register:5"
    )

    max_request_body_bytes: int = 1_048_576          # 1 MiB JSON
    max_upload_body_bytes: int = 26_214_400         # 25 MiB multipart

    security_headers_enabled: bool = True
    content_security_policy: str = (
        "default-src 'self'; "
        "img-src 'self' data: blob: https://fastapi.tiangolo.com; "
        "font-src 'self' data:; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    permissions_policy: str = (
        "camera=(), microphone=(), geolocation=(), "
        "payment=(), usb=(), magnetometer=(), gyroscope=(), "
        "accelerometer=(), interest-cohort=()"
    )
    referrer_policy: str = "strict-origin-when-cross-origin"
    x_frame_options: str = "DENY"
    x_content_type_options: str = "nosniff"
    cross_origin_opener_policy: str = "same-origin"
    cross_origin_resource_policy: str = "same-origin"
    strict_transport_security: str = ""
    strict_transport_security_max_age: int = 31_536_000
    strict_transport_security_include_subdomains: bool = True
    strict_transport_security_preload: bool = False

    security_audit_logger: str = "atlas.security"
    security_audit_enabled: bool = True

    cookie_path: str = "/"
    cookie_max_age_seconds: int = 3_600

    # Performance optimization
    gzip_enabled: bool = True
    gzip_minimum_size: int = 1024
    gzip_compress_level: int = 5

    db_pool_size: int = 5
    db_pool_max_overflow: int = 10
    db_pool_pre_ping: bool = True
    db_pool_recycle_seconds: int = 1800
    db_pool_timeout_seconds: int = 30
    db_echo: bool = False

    static_config_cache_ttl_seconds: int = 0
    health_response_cache_control: str = "no-store, max-age=0"

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value):
        if isinstance(value, str):
            if value.startswith("postgres://"):
                return value.replace("postgres://", "postgresql+psycopg2://", 1)
            if value.startswith("postgresql://") and not value.startswith("postgresql+"):
                return value.replace("postgresql://", "postgresql+psycopg2://", 1)
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _normalize_cors(cls, value):
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return ",".join(value)
        return value

    @field_validator("rate_limit_endpoint_overrides", mode="before")
    @classmethod
    def _normalize_endpoint_overrides(cls, value):
        if value is None or value == "":
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return ",".join(str(item) for item in value)
        return value

    @field_validator("cookie_samesite", mode="before")
    @classmethod
    def _validate_samesite(cls, value):
        if value is None:
            return "lax"
        v = str(value).strip().lower()
        if v not in {"lax", "strict", "none"}:
            return "lax"
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def rate_limit_endpoint_overrides_map(self) -> dict[str, int]:
        out: dict[str, int] = {}
        raw = (self.rate_limit_endpoint_overrides or "").strip()
        if not raw:
            return out
        for entry in raw.split(","):
            entry = entry.strip()
            if not entry or ":" not in entry:
                continue
            path, _, limit = entry.partition(":")
            path = path.strip()
            if not path:
                continue
            try:
                out[path] = int(limit)
            except (TypeError, ValueError):
                continue
        return out

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def cookie_name(self) -> str:
        return "atlas_access_token"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


def validate_security_settings(settings: Settings) -> list[str]:
    warnings: list[str] = []

    if settings.is_production:
        if not settings.cookie_secure:
            warnings.append("COOKIE_SECURE=false in production — auth cookie will travel over HTTP")
        if settings.jwt_secret_key in {"", "change-me", "CHANGE_ME"}:
            warnings.append("JWT_SECRET_KEY is unset or a placeholder in production")
        if not settings.security_headers_enabled:
            warnings.append("SECURITY_HEADERS_ENABLED=false in production")
        if not settings.rate_limit_enabled:
            warnings.append("RATE_LIMIT_ENABLED=false in production")
        if settings.app_debug:
            warnings.append("APP_DEBUG=true in production")
        if "*" in settings.cors_origins:
            warnings.append("CORS allows * (wildcard origin)")
        for origin in settings.cors_origins_list:
            if origin.startswith("http://") and not origin.startswith(
                ("http://localhost", "http://127.0.0.1")
            ):
                warnings.append(f"CORS origin uses plaintext http:// — {origin}")

    if settings.cookie_samesite == "none" and not settings.cookie_secure:
        warnings.append("SameSite=None requires Secure=true; cookie would be rejected by browsers")

    if settings.max_upload_body_bytes > 50 * 1024 * 1024:
        warnings.append("MAX_UPLOAD_BODY_BYTES > 50 MiB — risk of memory pressure")

    if settings.rate_limit_requests <= 0 or settings.rate_limit_window_seconds <= 0:
        warnings.append("Rate-limit values are non-positive — limiter is effectively off")

    return warnings