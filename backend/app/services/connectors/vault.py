"""Connector Credential Vault (Phase 6.27).

Provides:
  - Authenticated encryption at rest for external integration credentials
    (Fernet specification: 128-bit AES in CBC mode with PKCS7 padding + 128-bit HMAC-SHA256).
  - External key derivation with tenant-scoped isolation.
  - Dedicated CONNECTOR_ENCRYPTION_KEY decoupled from JWT authentication secrets.
  - Secure credential masking for safe UI display (e.g. ••••••••abcd).
  - Deep secret redaction for logging, exception traces, and audit trails.
  - Deterministic credential fingerprinting for rotation verification.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
from typing import Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config.settings import get_settings

logger = logging.getLogger("atlas.connectors.vault")

SECRET_KEY_PATTERNS = re.compile(
    r"(secret|password|token|key|credential|authorization|auth|bearer|passphrase)",
    re.IGNORECASE,
)


class ConnectorCredentialVault:
    """Manages encryption, decryption, masking, and redaction of integration credentials."""

    def __init__(self, master_key: str | None = None) -> None:
        self._master_key = master_key
        self._fernet = self._init_fernet(master_key)

    @staticmethod
    def _init_fernet(master_key: str | None = None) -> Fernet:
        """Initialize Fernet instance using a dedicated connector encryption key decoupled from JWT secrets.

        Fernet uses 128-bit AES in CBC mode with PKCS7 padding and 128-bit HMAC-SHA256 authentication.
        """
        settings = get_settings()
        key_candidate = (
            master_key
            or getattr(settings, "connector_encryption_key", "")
            or os.environ.get("CONNECTOR_ENCRYPTION_KEY")
        )

        if key_candidate:
            raw_bytes = key_candidate.encode("utf-8") if isinstance(key_candidate, str) else key_candidate
            try:
                # Test if it's already a valid 32-byte urlsafe-base64 Fernet key
                return Fernet(raw_bytes)
            except Exception:
                # If key_candidate is a passphrase, derive a 32-byte Fernet key via HKDF
                hkdf = HKDF(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b"ursbiz-connector-vault-v1",
                    info=b"ursbiz-credential-vault-encryption",
                )
                derived_key = base64.urlsafe_b64encode(hkdf.derive(raw_bytes))
                return Fernet(derived_key)

        if not key_candidate:
            if settings.is_production:
                raise RuntimeError(
                    "CRITICAL SECURITY ERROR: CONNECTOR_ENCRYPTION_KEY must be configured in production. "
                    "Refusing to initialize ConnectorCredentialVault with a predictable fallback key."
                )

        # Standalone, isolated fallback key generation (development/test mode only)
        logger.warning(
            "CONNECTOR_ENCRYPTION_KEY is unset. Using independent default key for development/test only. "
            "Set CONNECTOR_ENCRYPTION_KEY in production to ensure isolated credential encryption."
        )
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"ursbiz-connector-vault-v1",
            info=b"ursbiz-credential-vault-encryption",
        )
        fallback_source = b"ursbiz-dedicated-connector-vault-fallback-dev-seed"
        derived_key = base64.urlsafe_b64encode(hkdf.derive(fallback_source))
        return Fernet(derived_key)

    def encrypt_credentials(self, business_id: int, credentials: dict[str, Any]) -> str:
        """Encrypt credentials dictionary into an authenticated ciphertext string."""
        if not credentials:
            return ""
        settings = get_settings()
        has_key = bool(
            self._master_key
            or getattr(settings, "connector_encryption_key", "")
            or os.environ.get("CONNECTOR_ENCRYPTION_KEY")
        )
        if settings.is_production and not has_key:
            raise RuntimeError("Production requires CONNECTOR_ENCRYPTION_KEY. Credential encryption refused.")
        payload = {
            "business_id": business_id,
            "credentials": credentials,
        }
        json_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        return self._fernet.encrypt(json_bytes).decode("utf-8")

    def decrypt_credentials(self, business_id: int, encrypted_str: str) -> dict[str, Any]:
        """Decrypt ciphertext and enforce tenant ownership validation."""
        if not encrypted_str:
            return {}
        settings = get_settings()
        has_key = bool(
            self._master_key
            or getattr(settings, "connector_encryption_key", "")
            or os.environ.get("CONNECTOR_ENCRYPTION_KEY")
        )
        if settings.is_production and not has_key:
            raise RuntimeError("Production requires CONNECTOR_ENCRYPTION_KEY. Credential decryption refused.")
        try:
            raw_bytes = self._fernet.decrypt(encrypted_str.encode("utf-8"))
            payload = json.loads(raw_bytes.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Failed to decrypt credentials: {e}") from e

        # Ensure encrypted payload belongs to the requesting business
        payload_biz_id = payload.get("business_id")
        if payload_biz_id != business_id:
            raise PermissionError(
                f"Tenant isolation breach detected: Credential belongs to business {payload_biz_id}, "
                f"not requesting business {business_id}."
            )

        return payload.get("credentials", {})

    @staticmethod
    def mask_credentials(credentials: dict[str, Any]) -> dict[str, str]:
        """Produce safe display representations of credentials, masking secrets."""
        masked: dict[str, str] = {}
        for k, v in credentials.items():
            if v is None:
                masked[k] = ""
                continue
            str_val = str(v)
            if not str_val:
                masked[k] = ""
            elif len(str_val) <= 4:
                masked[k] = "••••••••"
            else:
                masked[k] = "••••••••" + str_val[-4:]
        return masked

    @classmethod
    def redact_secrets_from_dict(cls, data: Any) -> Any:
        """Deeply redact secret keys from dictionaries or lists for safe logging & audit trails."""
        if isinstance(data, dict):
            clean: dict[str, Any] = {}
            for k, v in data.items():
                if SECRET_KEY_PATTERNS.search(k):
                    clean[k] = "[REDACTED]"
                else:
                    clean[k] = cls.redact_secrets_from_dict(v)
            return clean
        elif isinstance(data, list):
            return [cls.redact_secrets_from_dict(item) for item in data]
        return data

    @staticmethod
    def compute_credential_fingerprint(credentials: dict[str, Any]) -> str:
        """Deterministic SHA-256 fingerprint of credentials to detect rotation."""
        if not credentials:
            return ""
        norm_str = json.dumps(credentials, sort_keys=True)
        return hashlib.sha256(norm_str.encode("utf-8")).hexdigest()
