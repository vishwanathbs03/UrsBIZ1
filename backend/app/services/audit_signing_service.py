"""Asymmetric Ed25519 Cryptographic Signing, Verification, and Canonicalization Service.

Part of Wave 1.1 Remediation (Financial Intelligence Architecture):
  - Pillar 1: Asymmetric Ed25519 signing abstraction (private key kept in external KMS/volatile memory).
  - Pillar 4: Canonical payload construction using unambiguous UTF-8 length-prefixing and paise minor units.
"""

from __future__ import annotations

import abc
import hashlib
import re
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

if TYPE_CHECKING:
    from app.config.settings import Settings


# ---------------------------------------------------------------------------
# CRC32C Castagnoli Implementation (RFC 3720 / Google Cloud KMS Specification)
# Polynomial: 0x82F63B78 (reflected) / 0x1EDC6F41
# ---------------------------------------------------------------------------

def _make_crc32c_table() -> list[int]:
    poly = 0x82F63B78
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ poly
            else:
                crc = crc >> 1
        table.append(crc)
    return table

_CRC32C_TABLE = _make_crc32c_table()


def compute_crc32c(data: bytes) -> int:
    """Computes Castagnoli CRC32C checksum conforming to RFC 3720 and Google Cloud KMS."""
    crc = 0xFFFFFFFF
    for b in data:
        crc = _CRC32C_TABLE[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF


class KMSIntegrityError(Exception):
    """Raised when Google Cloud KMS response fails integrity checks (CRC32C, name, or protection level)."""


class SecurityConfigurationError(Exception):
    """Raised when an insecure or invalid KMS provider configuration is detected."""


class KMSProvider(Protocol):
    """Abstract Key Management Service provider protocol for Ed25519 signing."""

    @property
    def key_id(self) -> str:
        """Returns the identifier of the managed key."""
        ...

    def get_public_key_hex(self) -> str:
        """Returns the 64-character lowercase hex representation of the public key."""
        ...

    def sign(self, payload_bytes: bytes) -> str:
        """Signs the canonical payload bytes and returns the 128-char hex signature."""
        ...


class VolatileMemoryKMSProvider:
    """Ephemeral in-memory KMS provider for development, staging, and automated test suites.

    Key Custody Boundary:
      - Private key bytes reside strictly in volatile process RAM.
      - Private keys are NEVER written to disk, database tables, or application logs.
      - Strictly prohibited in production and staging environments.
    """

    def __init__(self, key_id: str, private_key_hex: str | None = None) -> None:
        self._key_id = key_id.strip()
        if private_key_hex:
            priv_bytes = bytes.fromhex(private_key_hex.strip())
            self._private_key = ed25519.Ed25519PrivateKey.from_private_bytes(priv_bytes)
        else:
            self._private_key = ed25519.Ed25519PrivateKey.generate()

        self._public_key = self._private_key.public_key()

    @property
    def key_id(self) -> str:
        return self._key_id

    def get_public_key_hex(self) -> str:
        pub_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return pub_bytes.hex()

    def sign(self, payload_bytes: bytes) -> str:
        signature = self._private_key.sign(payload_bytes)
        return signature.hex()


class GoogleCloudKMSProvider:
    """Production Cloud KMS Provider using asymmetric Ed25519 signing.

    Algorithm & Protection Level:
      - Algorithm: EC_SIGN_ED25519 (PureEdDSA over Curve25519, RFC 8032)
      - Protection Level: SOFTWARE (Google Cloud KMS does NOT support Ed25519 on HSM)
      - Note: Do NOT claim HSM protection for this key.

    Integrity & Custody Guarantees:
      - Sends raw canonical payload through `data` field (not pre-hashed digest).
      - Computes and verifies RFC 3720 CRC32C checksums for both request and response.
      - Verifies key-version resource name and protection level.
      - Performs client-side signature verification against registered public key before returning.
      - Private key never leaves Google Cloud KMS and never enters PostgreSQL or application memory.
    """

    ALGORITHM = "EC_SIGN_ED25519"
    PROTECTION_LEVEL = "SOFTWARE"

    def __init__(
        self,
        project_id: str,
        location_id: str,
        key_ring_id: str,
        crypto_key_id: str,
        version_id: str,
    ) -> None:
        self.project_id = project_id
        self.location_id = location_id
        self.key_ring_id = key_ring_id
        self.crypto_key_id = crypto_key_id
        self.version_id = version_id
        self._cached_public_key_hex: str | None = None

    @property
    def key_id(self) -> str:
        return f"{self.crypto_key_id}-v{self.version_id}"

    @property
    def key_version_resource_name(self) -> str:
        return (
            f"projects/{self.project_id}/locations/{self.location_id}/"
            f"keyRings/{self.key_ring_id}/cryptoKeys/{self.crypto_key_id}/"
            f"cryptoKeyVersions/{self.version_id}"
        )

    def get_public_key_hex(self) -> str:
        """Fetches the public key from Cloud KMS, validates its format, and caches its raw hex."""
        if self._cached_public_key_hex is None:
            try:
                from google.cloud import kms
                client = kms.KeyManagementServiceClient()
                pub_key_resp = client.get_public_key(request={"name": self.key_version_resource_name})

                # Validate algorithm from Cloud KMS response if available
                if hasattr(pub_key_resp, "algorithm"):
                    alg_name = getattr(pub_key_resp.algorithm, "name", str(pub_key_resp.algorithm))
                    if alg_name not in ("EC_SIGN_ED25519", "CryptoKeyVersionAlgorithm.EC_SIGN_ED25519"):
                        raise KMSIntegrityError(f"Expected EC_SIGN_ED25519 key, got {alg_name}")

                from cryptography.hazmat.primitives.serialization import load_pem_public_key
                loaded_key = load_pem_public_key(pub_key_resp.pem.encode("utf-8"))
                if not isinstance(loaded_key, ed25519.Ed25519PublicKey):
                    raise TypeError(f"Expected Ed25519 public key from Cloud KMS, got {type(loaded_key)}")
                raw_bytes = loaded_key.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
                self._cached_public_key_hex = raw_bytes.hex()
            except ImportError:
                raise RuntimeError("google-cloud-kms library is required for GoogleCloudKMSProvider")
        return self._cached_public_key_hex

    def sign(self, payload_bytes: bytes) -> str:
        """Invokes Cloud KMS asymmetricSign API with CRC32C integrity validation."""
        try:
            from google.cloud import kms
            client = kms.KeyManagementServiceClient()
            expected_name = self.key_version_resource_name
            payload_crc = compute_crc32c(payload_bytes)

            request = {
                "name": expected_name,
                "data": payload_bytes,
                "data_crc32c": payload_crc,
            }
            response = client.asymmetric_sign(request=request)

            # 1. Require verified_data_crc32c == True
            if not getattr(response, "verified_data_crc32c", False):
                raise KMSIntegrityError("Cloud KMS reported that request data_crc32c was not verified")

            # 2. Validate resource name match
            resp_name = getattr(response, "name", "")
            if resp_name and resp_name != expected_name:
                raise KMSIntegrityError(
                    f"Cloud KMS response key-version mismatch: expected {expected_name}, got {resp_name}"
                )

            # 3. Check response signature CRC32C
            signature_bytes = response.signature
            computed_sig_crc = compute_crc32c(signature_bytes)
            resp_sig_crc = getattr(response, "signature_crc32c", None)
            if resp_sig_crc is None:
                raise KMSIntegrityError("Cloud KMS response missing signature_crc32c")
            if computed_sig_crc != resp_sig_crc:
                raise KMSIntegrityError(
                    f"Cloud KMS signature CRC32C mismatch: computed {computed_sig_crc}, got {resp_sig_crc}"
                )

            # 4. Confirm protection level is SOFTWARE (never claim HSM for Ed25519)
            prot_level = getattr(response, "protection_level", None)
            if prot_level is not None:
                prot_str = getattr(prot_level, "name", str(prot_level)).upper()
                if "SOFTWARE" not in prot_str:
                    raise KMSIntegrityError(
                        f"Expected SOFTWARE protection level for Ed25519, got {prot_str}"
                    )

            # 5. Client-side signature verification against registered public key before returning
            sig_hex = signature_bytes.hex()
            pub_hex = self.get_public_key_hex()
            if not AuditSigningService.verify_signature(pub_hex, sig_hex, payload_bytes):
                raise KMSIntegrityError("Signature failed client-side verification against public key")

            return sig_hex
        except ImportError:
            raise RuntimeError("google-cloud-kms library is required for GoogleCloudKMSProvider")


class KMSProviderFactory:
    """Factory creating authorized KMS providers with strict production guardrails."""

    @staticmethod
    def get_provider(settings: Settings | None = None) -> KMSProvider:
        """Instantiates KMS provider, enforcing environment safety boundaries.

        Raises SecurityConfigurationError if:
          - 'memory' provider is attempted in staging or production.
          - Missing or invalid provider configuration in production.
        """
        if settings is None:
            from app.config.settings import get_settings
            settings = get_settings()

        env_name = getattr(settings, "app_env", "development").lower()
        is_prod_or_staging = env_name in ("production", "staging") or getattr(settings, "is_production", False)

        provider_type = getattr(settings, "kms_provider_type", "memory").lower().strip()

        if is_prod_or_staging:
            if provider_type == "memory":
                raise SecurityConfigurationError(
                    f"VolatileMemoryKMSProvider (kms_provider_type='memory') is strictly prohibited in {env_name}"
                )
            if provider_type != "gcp_kms":
                raise SecurityConfigurationError(
                    f"Unsupported KMS provider '{provider_type}' in {env_name}. Only 'gcp_kms' is authorized"
                )

            # Require Google Cloud KMS configuration
            if not (
                settings.kms_project_id
                and settings.kms_location_id
                and settings.kms_key_ring_id
                and settings.kms_crypto_key_id
                and settings.kms_key_version_id
            ):
                raise SecurityConfigurationError(
                    f"Incomplete Google Cloud KMS configuration in {env_name}: all key parameters must be set"
                )

            return GoogleCloudKMSProvider(
                project_id=settings.kms_project_id,
                location_id=settings.kms_location_id,
                key_ring_id=settings.kms_key_ring_id,
                crypto_key_id=settings.kms_crypto_key_id,
                version_id=settings.kms_key_version_id,
            )

        # Development / Test Environment
        if provider_type == "gcp_kms":
            return GoogleCloudKMSProvider(
                project_id=settings.kms_project_id,
                location_id=settings.kms_location_id,
                key_ring_id=settings.kms_key_ring_id,
                crypto_key_id=settings.kms_crypto_key_id,
                version_id=settings.kms_key_version_id,
            )
        return VolatileMemoryKMSProvider(key_id=getattr(settings, "kms_crypto_key_id", "dev_key_01") or "dev_key_01")


class AuditSigningService:
    """Cryptographic signing provider and canonical event serializer."""

    PROTOCOL_VERSION = "URSBIZ_REV_AUTH_V2"
    DEFAULT_ALGORITHM = "ED25519"
    DEFAULT_CURRENCY = "INR"

    @staticmethod
    def decimal_to_paise(amount: Decimal | float | str) -> int:
        """Converts a monetary amount to integer paise minor units.

        Rejects fractional paise and non-positive values to prevent rounding ambiguities.
        """
        if isinstance(amount, float):
            # Convert float to exact string representation without scientific notation
            amt_dec = Decimal(str(amount))
        elif isinstance(amount, str):
            amt_dec = Decimal(amount.strip())
        elif isinstance(amount, Decimal):
            amt_dec = amount
        else:
            raise TypeError(f"Unsupported amount type: {type(amount).__name__}")

        if amt_dec <= Decimal("0.00"):
            raise ValueError(f"Reversal amount must be strictly positive, got {amt_dec}")

        paise_dec = amt_dec * Decimal("100")
        if paise_dec != paise_dec.to_integral_value():
            raise ValueError(
                f"Fractional paise not permitted: {amt_dec} contains fractions beyond 2 decimal places"
            )

        return int(paise_dec)

    @classmethod
    def build_canonical_payload(
        cls,
        business_id: int,
        actor_user_id: int,
        allocation_type: Literal["AR", "AP"],
        allocation_id: int,
        amount_paise: int,
        currency: str,
        nonce: str,
        key_id: str,
        algorithm: str,
        reason: str,
        timestamp_iso: str,
    ) -> bytes:
        """Constructs an unambiguous, length-prefixed UTF-8 canonical payload for Ed25519 signing.

        Format:
          Each field is encoded as octet_length:value.
          Fields:
            1. Protocol Version (URSBIZ_REV_AUTH_V2)
            2. Business ID
            3. Actor User ID
            4. Allocation Type (AR or AP)
            5. Allocation ID
            6. Amount in Minor Units (Paise)
            7. Currency Code (e.g. INR)
            8. Nonce (lowercase hex)
            9. Key ID
            10. Signature Algorithm (e.g. ED25519)
            11. Normalized Reason
            12. Timestamp ISO (Whole-second UTC, YYYY-MM-DDTHH:MM:SSZ)
        """
        if business_id <= 0:
            raise ValueError(f"Invalid business_id: must be positive, got {business_id}")
        if actor_user_id <= 0:
            raise ValueError(f"Invalid actor_user_id: must be positive, got {actor_user_id}")
        if allocation_type not in ("AR", "AP"):
            raise ValueError(f"Invalid allocation_type: must be 'AR' or 'AP', got {allocation_type}")
        if allocation_id <= 0:
            raise ValueError(f"Invalid allocation_id: must be positive, got {allocation_id}")
        if amount_paise <= 0:
            raise ValueError(f"Invalid amount_paise: must be positive integer, got {amount_paise}")

        norm_currency = currency.strip().upper()
        if not re.match(r"^[A-Z]{3}$", norm_currency):
            raise ValueError(f"Invalid currency code: must be 3 uppercase letters, got {currency!r}")

        norm_nonce = nonce.strip().lower()
        if not re.match(r"^[a-f0-9]{32,64}$", norm_nonce):
            raise ValueError(f"Invalid nonce: must be 32-64 hex characters, got {nonce!r}")

        norm_key_id = key_id.strip()
        if not re.match(r"^[a-zA-Z0-9_-]{1,32}$", norm_key_id):
            raise ValueError(f"Invalid key_id: must be 1-32 alphanumeric/dash/underscore, got {key_id!r}")

        norm_alg = algorithm.strip().upper()
        if norm_alg != cls.DEFAULT_ALGORITHM:
            raise ValueError(f"Unsupported algorithm: expected {cls.DEFAULT_ALGORITHM}, got {algorithm!r}")

        norm_reason = reason.strip(" \t\r\n")
        if not norm_reason or len(norm_reason) > 500:
            raise ValueError("Reason must be between 1 and 500 characters after whitespace trimming")

        norm_ts = timestamp_iso.strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", norm_ts):
            raise ValueError(
                f"Invalid timestamp_iso: must match YYYY-MM-DDTHH:MM:SSZ, got {timestamp_iso!r}"
            )

        fields = [
            cls.PROTOCOL_VERSION,
            str(business_id),
            str(actor_user_id),
            allocation_type,
            str(allocation_id),
            str(amount_paise),
            norm_currency,
            norm_nonce,
            norm_key_id,
            norm_alg,
            norm_reason,
            norm_ts,
        ]

        def chunk(val: str) -> bytes:
            b = val.encode("utf-8")
            return f"{len(b)}:".encode("ascii") + b

        return b"".join(chunk(f) for f in fields)

    TRANSITION_PROTOCOL_VERSION = "URSBIZ_TRANS_V1"

    @classmethod
    def build_transition_checkpoint_payload(
        cls,
        business_id: int,
        transition_id: str,
        legacy_algorithm: str,
        legacy_chain_head_digest: str,
        legacy_reversal_count: int,
        new_algorithm: str,
        new_key_id: str,
        timestamp_iso: str,
    ) -> bytes:
        """Constructs unambiguous length-prefixed canonical payload for epoch transition checkpoints."""
        if business_id <= 0:
            raise ValueError(f"Invalid business_id: must be positive, got {business_id}")
        if not transition_id or not re.match(r"^[a-zA-Z0-9_-]{1,64}$", transition_id.strip()):
            raise ValueError(f"Invalid transition_id: must be 1-64 alphanumeric, got {transition_id!r}")
        if legacy_reversal_count < 0:
            raise ValueError(f"Invalid legacy_reversal_count: must be non-negative, got {legacy_reversal_count}")

        norm_from_alg = legacy_algorithm.strip().upper()
        norm_to_alg = new_algorithm.strip().upper()
        norm_head = legacy_chain_head_digest.strip().lower()
        if not re.match(r"^[a-f0-9]{64}$", norm_head):
            raise ValueError(f"Invalid legacy_chain_head_digest: must be 64-char hex, got {legacy_chain_head_digest!r}")

        norm_key_id = new_key_id.strip()
        if not re.match(r"^[a-zA-Z0-9_-]{1,32}$", norm_key_id):
            raise ValueError(f"Invalid new_key_id: must be 1-32 chars, got {new_key_id!r}")

        norm_ts = timestamp_iso.strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", norm_ts):
            raise ValueError(f"Invalid timestamp_iso: must match YYYY-MM-DDTHH:MM:SSZ, got {timestamp_iso!r}")

        fields = [
            cls.TRANSITION_PROTOCOL_VERSION,
            str(business_id),
            transition_id.strip(),
            norm_from_alg,
            norm_head,
            str(legacy_reversal_count),
            norm_to_alg,
            norm_key_id,
            norm_ts,
        ]

        def chunk(val: str) -> bytes:
            b = val.encode("utf-8")
            return f"{len(b)}:".encode("ascii") + b

        return b"".join(chunk(f) for f in fields)

    @staticmethod
    def generate_keypair() -> tuple[str, str]:
        """Generates a new Ed25519 keypair.

        Returns:
            tuple of (private_key_hex_64, public_key_hex_64)
        """
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        from cryptography.hazmat.primitives import serialization

        priv_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        return priv_bytes.hex(), pub_bytes.hex()

    @staticmethod
    def sign_payload(private_key_hex: str, payload_bytes: bytes) -> str:
        """Signs canonical payload bytes using an Ed25519 private key.

        Returns:
            128-character lowercase hexadecimal signature string (64 raw bytes).
        """
        priv_bytes = bytes.fromhex(private_key_hex.strip())
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(priv_bytes)
        signature = private_key.sign(payload_bytes)
        return signature.hex()

    @staticmethod
    def verify_signature(public_key_hex: str, signature_hex: str, payload_bytes: bytes) -> bool:
        """Verifies an Ed25519 signature against canonical payload bytes.

        Returns:
            True if signature is valid; False otherwise.
        """
        try:
            pub_bytes = bytes.fromhex(public_key_hex.strip())
            sig_bytes = bytes.fromhex(signature_hex.strip())
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            public_key.verify(sig_bytes, payload_bytes)
            return True
        except (ValueError, InvalidSignature):
            return False
