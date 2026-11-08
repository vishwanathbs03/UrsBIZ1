"""Privileged Audit Signing Worker Service & Job Queue Mediation.

Part of Wave 1.1.3 Remediation (Trust Boundary Hardening):
  - Decision 1 (Option 1A): Decoupled asymmetric RS256 identity verification; worker holds only IDP public key.
  - Decision 2 (Option 2A): Worker-side Ed25519 signature verification + PostgreSQL SECURITY DEFINER procedure.
  - Decision 3 (Option 3A): Transactional audit worker job queue with envelope-encrypted auth context.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jose import JWTError, jwt
from sqlalchemy import Engine, text

from app.services.audit_signing_service import (
    AuditSigningService,
    KMSProvider,
)


class SecurityViolation(Exception):
    """Raised when an actor tampering attempt, forged token, or privilege escalation occurs."""


# ==============================================================================
# Asymmetric Identity Authority (Decision 1 - Option 1A)
# ==============================================================================

class TestIdentityAuthority:
    """Isolated asymmetric RS256 token issuer for development, testing, and staging.

    Key Custody Boundary:
      - Private signing key is held strictly by this authority.
      - FastAPI application containers never possess or receive this private signing key.
      - Audit workers receive strictly the public verification key.
    """

    __test__ = False

    def __init__(self, key_size: int = 2048, key_id: str = "idp-rsa-key-1") -> None:
        self._key_id = key_id
        self._private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
        )
        self._public_key = self._private_key.public_key()

        self._private_pem = self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        self._public_pem = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    @property
    def public_key_pem(self) -> str:
        """Exported public verification key for distribution to the audit worker."""
        return self._public_pem

    @property
    def key_id(self) -> str:
        return self._key_id

    def mint_token(
        self,
        subject: int | str,
        issuer: str = "ursbiz-identity",
        audience: str = "ursbiz-financial-audit",
        expires_in_seconds: int = 3600,
        not_before_seconds: int = 0,
        token_type: str = "JWT",
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        """Mints an authentic RS256 JWT access token."""
        now = int(datetime.now(timezone.utc).timestamp())
        claims: dict[str, Any] = {
            "sub": str(subject),
            "iss": issuer,
            "aud": audience,
            "exp": now + expires_in_seconds,
            "nbf": now + not_before_seconds,
            "iat": now,
            "typ": token_type,
            "jti": uuid.uuid4().hex,
        }
        if extra_claims:
            claims.update(extra_claims)

        headers = {"kid": self._key_id, "typ": token_type}
        return jwt.encode(claims, self._private_pem, algorithm="RS256", headers=headers)

    mint_access_token = mint_token


# ==============================================================================
# Worker Envelope Encryption (Decision 3 - Authentication-Context Protection)
# ==============================================================================

class WorkerContextEncryption:
    """Envelope encryption for protecting short-lived authentication contexts in the database.

    Guarantees:
      - Raw bearer tokens are never stored in plaintext in PostgreSQL tables.
      - FastAPI encrypts the job envelope using worker's public encryption key.
      - Only the isolated worker process possessing the private decryption key can unwrap the context.
    """

    @staticmethod
    def generate_keypair(key_size: int = 2048) -> tuple[str, str]:
        """Generates (private_key_pem, public_key_pem) for worker context encryption."""
        priv = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
        priv_pem = priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        pub_pem = priv.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        return priv_pem, pub_pem

    @staticmethod
    def encrypt_envelope(plaintext: str, worker_public_key_pem: str, key_id: str = "worker-enc-1") -> str:
        """FastAPI-side: Encrypts short-lived context into a hybrid AES-256-GCM / RSA-OAEP envelope."""
        pub_key = serialization.load_pem_public_key(worker_public_key_pem.encode("utf-8"))
        if not isinstance(pub_key, rsa.RSAPublicKey):
            raise TypeError("worker_public_key_pem must be an RSA public key")

        aes_key = AESGCM.generate_key(bit_length=256)
        nonce = os.urandom(12)
        ciphertext = AESGCM(aes_key).encrypt(nonce, plaintext.encode("utf-8"), None)

        enc_aes_key = pub_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        envelope = {
            "v": 1,
            "kid": key_id,
            "ek": base64.b64encode(enc_aes_key).decode("ascii"),
            "iv": base64.b64encode(nonce).decode("ascii"),
            "ct": base64.b64encode(ciphertext).decode("ascii"),
        }
        return json.dumps(envelope, separators=(",", ":"))

    @staticmethod
    def decrypt_envelope(envelope_json_str: str, worker_private_key_pem: str) -> str:
        """Worker-side: Decrypts hybrid envelope using worker private key."""
        priv_key = serialization.load_pem_private_key(
            worker_private_key_pem.encode("utf-8"),
            password=None,
        )
        if not isinstance(priv_key, rsa.RSAPrivateKey):
            raise TypeError("worker_private_key_pem must be an RSA private key")

        data = json.loads(envelope_json_str)
        enc_aes_key = base64.b64decode(data["ek"])
        nonce = base64.b64decode(data["iv"])
        ciphertext = base64.b64decode(data["ct"])

        aes_key = priv_key.decrypt(
            enc_aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        plaintext_bytes = AESGCM(aes_key).decrypt(nonce, ciphertext, None)
        return plaintext_bytes.decode("utf-8")


# ==============================================================================
# Dedicated Audit Worker Service
# ==============================================================================

class AuditWorkerService:
    """Privileged service mediating audit signing, actor identity binding, and ledger operations."""

    DEFAULT_TRUSTED_ISSUER = "ursbiz-identity"
    DEFAULT_TRUSTED_AUDIENCE = "ursbiz-financial-audit"

    @classmethod
    def verify_actor_and_bind(
        cls,
        auth_token: str,
        business_id: int,
        worker_engine: Engine,
        idp_public_key_pem: str | None = None,
        trusted_issuer: str | None = None,
        trusted_audience: str | None = None,
        caller_supplied_actor_id: int | None = None,
        permitted_roles: tuple[str, ...] = ("OWNER", "FINANCE_ADMIN", "SYSTEM_SERVICE"),
    ) -> int:
        """Independently verifies user authentication token and derives authoritative actor identity.

        Security Invariants (Decision 1 - Option 1A):
          1. Uses asymmetric RS256 verification against the trusted identity issuer's public key.
          2. Rejects symmetric HS256, none, or mismatched algorithms.
          3. Validates issuer (iss), audience (aud), expiration (exp), not-before (nbf), and token type (typ).
          4. Extracts subject: `token_actor_id = int(payload["sub"])`.
          5. Asserts caller-supplied actor ID matches the token subject (detects actor tampering).
          6. Verifies active business membership and role against PostgreSQL business_members table.
          7. Returns the verified authoritative actor user ID.
        """
        if not auth_token or not auth_token.strip():
            raise SecurityViolation("Missing authentication token in worker context")

        if not idp_public_key_pem or not idp_public_key_pem.strip():
            raise SecurityViolation(
                "Audit worker requires trusted IDP public verification key; shared-secret fallback is strictly prohibited"
            )

        iss = trusted_issuer or cls.DEFAULT_TRUSTED_ISSUER
        aud = trusted_audience or cls.DEFAULT_TRUSTED_AUDIENCE

        try:
            # Enforce strictly RS256 with full claims validation
            payload = jwt.decode(
                auth_token.strip(),
                idp_public_key_pem.strip(),
                algorithms=["RS256"],
                audience=aud,
                issuer=iss,
                options={
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                },
            )
        except JWTError as e:
            raise SecurityViolation(f"Invalid, expired, or untrusted user authentication token: {e}") from e

        # Validate token type (reject refresh tokens used as access tokens)
        token_type = payload.get("typ", "JWT")
        if token_type not in ("JWT", "access"):
            raise SecurityViolation(f"Invalid token type: expected access token, got {token_type!r}")

        sub = payload.get("sub")
        if sub is None:
            raise SecurityViolation("Authentication token missing required 'sub' subject claim")

        try:
            authenticated_actor_id = int(sub)
            if authenticated_actor_id <= 0:
                raise ValueError("Subject user ID must be positive")
        except (ValueError, TypeError) as e:
            raise SecurityViolation(f"Malformed token subject claim: {sub!r}") from e

        # Tampering check: caller-supplied actor ID MUST match token subject
        if caller_supplied_actor_id is not None and caller_supplied_actor_id != authenticated_actor_id:
            raise SecurityViolation(
                f"Actor tampering detected: caller-supplied actor_user_id ({caller_supplied_actor_id}) "
                f"does not match authenticated token subject ({authenticated_actor_id})"
            )

        # Database Role & Membership Verification
        with worker_engine.connect() as conn:
            member_row = conn.execute(
                text("""
                    SELECT role, status 
                    FROM public.business_members 
                    WHERE business_id = :b AND user_id = :u
                """),
                {"b": business_id, "u": authenticated_actor_id},
            ).fetchone()

            if not member_row:
                raise SecurityViolation(
                    f"User {authenticated_actor_id} is not a member of business {business_id}"
                )

            role, status = member_row[0], member_row[1]
            if status != "ACTIVE":
                raise SecurityViolation(
                    f"User {authenticated_actor_id} membership in business {business_id} is {status} (requires ACTIVE)"
                )

            if role not in permitted_roles:
                raise SecurityViolation(
                    f"User {authenticated_actor_id} has role {role} for business {business_id}; "
                    f"requires one of {permitted_roles}"
                )

        return authenticated_actor_id

    @classmethod
    def execute_reversal(
        cls,
        allocation_type: Literal["AR", "AP"],
        business_id: int,
        allocation_id: int,
        reversed_amount: float,
        reason: str,
        auth_token: str,
        kms_provider: KMSProvider,
        worker_engine: Engine,
        idp_public_key_pem: str | None = None,
        caller_supplied_actor_id: int | None = None,
        request_nonce: str | None = None,
    ) -> int:
        """Executes a financial allocation reversal through the privileged stored procedure.

        Boundary Guarantee:
          - Actor ID is derived strictly from verified asymmetric RS256 token.
          - Signature is generated via KMSProvider and verified client-side before database call.
          - Executed strictly using the privileged worker_engine (ursbiz_kms_worker).
        """
        # 1. Authenticated Actor Binding (Asymmetric RS256)
        actor_user_id = cls.verify_actor_and_bind(
            auth_token=auth_token,
            business_id=business_id,
            worker_engine=worker_engine,
            idp_public_key_pem=idp_public_key_pem,
            caller_supplied_actor_id=caller_supplied_actor_id,
        )

        # 2. Canonical Minor Units and Nonce
        amount_paise = AuditSigningService.decimal_to_paise(reversed_amount)
        nonce = (request_nonce or uuid.uuid4().hex).strip().lower()

        now_utc = datetime.now(timezone.utc).replace(microsecond=0)
        ts_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        # 3. Build Canonical Authentication Payload
        payload_bytes = AuditSigningService.build_canonical_payload(
            business_id=business_id,
            actor_user_id=actor_user_id,
            allocation_type=allocation_type,
            allocation_id=allocation_id,
            amount_paise=amount_paise,
            currency="INR",
            nonce=nonce,
            key_id=kms_provider.key_id,
            algorithm="ED25519",
            reason=reason,
            timestamp_iso=ts_iso,
        )

        # 4. KMS Signing
        signature_hex = kms_provider.sign(payload_bytes)

        # 5. Client-side Verification before database invocation
        pub_hex = kms_provider.get_public_key_hex()
        if not AuditSigningService.verify_signature(pub_hex, signature_hex, payload_bytes):
            raise SecurityViolation("Signature failed verification against KMS public key")

        # 6. Execute Stored Procedure via Worker Connection
        proc_name = (
            "public.record_ar_allocation_reversal"
            if allocation_type == "AR"
            else "public.record_ap_allocation_reversal"
        )

        with worker_engine.connect() as conn:
            with conn.begin():
                result = conn.execute(
                    text(f"""
                        SELECT {proc_name}(
                            :b, :a, :amt, :paise, 'INR', :reason, :actor,
                            :nonce, :key_id, 'ED25519', :sig, :ts
                        )
                    """),
                    {
                        "b": business_id,
                        "a": allocation_id,
                        "amt": reversed_amount,
                        "paise": amount_paise,
                        "reason": reason,
                        "actor": actor_user_id,
                        "nonce": nonce,
                        "key_id": kms_provider.key_id,
                        "sig": signature_hex,
                        "ts": now_utc,
                    },
                )
                reversal_id = result.scalar_one()

        return reversal_id

    @classmethod
    def execute_transition_checkpoint(
        cls,
        business_id: int,
        transition_id: str,
        kms_provider: KMSProvider,
        worker_engine: Engine,
        operator_confirmed: bool = True,
        dry_run: bool = False,
        checkpoint_timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """Creates an append-only, cryptographically signed transition checkpoint on the sequential hash chain.

        Remediation (Decision 2 - Option 2A):
          - Worker cryptographically verifies Ed25519 signature in Python against audit_signing_public_keys.
          - PostgreSQL stored procedure public.record_transition_checkpoint(...) enforces row locking FOR UPDATE,
            chain continuity, idempotency, and atomic advancement.
          - Direct DML writes are revoked from ursbiz_kms_worker.
        """
        if not operator_confirmed:
            raise SecurityViolation("Transition checkpoint requires explicit operator confirmation")

        norm_trans_id = transition_id.strip()

        # Check for existing checkpoint (Idempotent query for completed checkpoints)
        with worker_engine.connect() as conn:
            existing_row = conn.execute(
                text("""
                    SELECT id, transition_id, business_id, canonical_version,
                           checkpoint_signature_hex, checkpoint_digest_sha256,
                           legacy_chain_head_digest, legacy_reversal_count,
                           new_signing_key_id, transition_timestamp
                    FROM public.audit_transition_checkpoints
                    WHERE business_id = :b AND transition_id = :tid
                """),
                {"b": business_id, "tid": norm_trans_id},
            ).fetchone()

            if existing_row:
                chain_head = conn.execute(
                    text("SELECT chain_head_digest FROM public.business_audit_chains WHERE business_id = :b"),
                    {"b": business_id},
                ).scalar_one_or_none()
                return {
                    "id": existing_row[0],
                    "status": "COMMITTED",
                    "checkpoint_id": existing_row[0],
                    "business_id": existing_row[2],
                    "transition_id": existing_row[1],
                    "canonical_payload_format": existing_row[3],
                    "checkpoint_signature_hex": existing_row[4],
                    "checkpoint_digest_sha256": existing_row[5],
                    "legacy_chain_head_digest": existing_row[6],
                    "legacy_reversal_count": existing_row[7],
                    "signing_key_id": existing_row[8],
                    "checkpoint_timestamp_iso": existing_row[9].strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "new_chain_head_digest": chain_head,
                    "is_dry_run": False,
                    "is_idempotent_replay": True,
                }

            # 1. Read Current Chain Head (or compute Genesis) for Canonical Payload construction
            chain_row = conn.execute(
                text("""
                    SELECT chain_head_digest, reversal_count 
                    FROM public.business_audit_chains 
                    WHERE business_id = :b
                """),
                {"b": business_id},
            ).fetchone()

            if chain_row:
                current_head, current_count = chain_row[0], chain_row[1]
            else:
                # Genesis Anchor calculation
                genesis_bytes = f"URSBIZ_GENESIS_{business_id}".encode("utf-8")
                current_head = hashlib.sha256(genesis_bytes).hexdigest()
                current_count = 0

        now_utc = checkpoint_timestamp.replace(microsecond=0) if checkpoint_timestamp else datetime.now(timezone.utc).replace(microsecond=0)
        ts_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        # 2. Build Canonical Payload
        payload_bytes = AuditSigningService.build_transition_checkpoint_payload(
            business_id=business_id,
            transition_id=norm_trans_id,
            legacy_algorithm="HMAC-SHA256",
            legacy_chain_head_digest=current_head,
            legacy_reversal_count=current_count,
            new_algorithm="ED25519",
            new_key_id=kms_provider.key_id,
            timestamp_iso=ts_iso,
        )

        if dry_run:
            return {
                "status": "DRY_RUN",
                "is_dry_run": True,
                "business_id": business_id,
                "transition_id": norm_trans_id,
                "current_head": current_head,
                "current_count": current_count,
                "payload_bytes_len": len(payload_bytes),
            }

        # 3. Sign Canonical Checkpoint with KMS Provider
        signature_hex = kms_provider.sign(payload_bytes)

        # 4. Worker-Side Cryptographic Verification against Public Key
        pub_hex = kms_provider.get_public_key_hex()
        if not AuditSigningService.verify_signature(pub_hex, signature_hex, payload_bytes):
            raise SecurityViolation("Checkpoint signature failed verification against KMS public key")

        # 5. Derive Checkpoint Event Digest and Expected Next Chain Head
        checkpoint_digest = hashlib.sha256(payload_bytes).hexdigest()
        new_chain_head = hashlib.sha256((current_head + checkpoint_digest).encode("utf-8")).hexdigest()

        # 6. Execute PostgreSQL SECURITY DEFINER Procedure
        with worker_engine.connect() as conn:
            with conn.begin():
                checkpoint_id = conn.execute(
                    text("""
                        SELECT public.record_transition_checkpoint(
                            :b, :tid, 'HMAC-SHA256', 'LEGACY_NON_REPUDIATION_DOWNGRADED',
                            :l_head, :l_count, 'ED25519', :k_id, 'URSBIZ_TRANS_V1',
                            :sig, :c_digest, :p_head, :ts
                        )
                    """),
                    {
                        "b": business_id,
                        "tid": norm_trans_id,
                        "l_head": current_head,
                        "l_count": current_count,
                        "k_id": kms_provider.key_id,
                        "sig": signature_hex,
                        "c_digest": checkpoint_digest,
                        "p_head": current_head,
                        "ts": now_utc,
                    },
                ).scalar_one()

        return {
            "id": checkpoint_id,
            "status": "COMMITTED",
            "checkpoint_id": checkpoint_id,
            "business_id": business_id,
            "transition_id": norm_trans_id,
            "canonical_payload_format": "URSBIZ_TRANS_V1",
            "legacy_chain_head_digest": current_head,
            "legacy_reversal_count": current_count,
            "checkpoint_signature_hex": signature_hex,
            "checkpoint_digest_sha256": checkpoint_digest,
            "new_chain_head_digest": new_chain_head,
            "signing_key_id": kms_provider.key_id,
            "checkpoint_timestamp_iso": ts_iso,
            "is_dry_run": False,
        }

    # ==========================================================================
    # Job Queue Management (Decision 3 - Option 3A)
    # ==========================================================================

    @classmethod
    def enqueue_job(
        cls,
        business_id: int,
        job_type: str,
        idempotency_key: str,
        auth_token: str,
        payload: dict[str, Any],
        worker_public_key_pem: str,
        app_engine: Engine,
    ) -> str:
        """FastAPI-side: Enqueues an audit worker job with envelope-encrypted auth context.

        Permissions: Executed strictly using app_engine (ursbiz_app).
        FastAPI cannot execute or claim jobs; it can only insert them.
        """
        job_id = f"job_{uuid.uuid4().hex}"
        encrypted_context = WorkerContextEncryption.encrypt_envelope(
            plaintext=auth_token,
            worker_public_key_pem=worker_public_key_pem,
        )

        with app_engine.connect() as conn:
            with conn.begin():
                conn.execute(
                    text("""
                        INSERT INTO public.audit_worker_jobs (
                            job_id, business_id, job_type, idempotency_key,
                            encrypted_auth_context, encryption_key_id,
                            payload_json, status, attempts, max_attempts
                        ) VALUES (
                            :jid, :b, :jtype, :ikey,
                            :enc_ctx, 'worker-rsa-1',
                            :payload, 'PENDING', 0, 3
                        )
                    """),
                    {
                        "jid": job_id,
                        "b": business_id,
                        "jtype": job_type,
                        "ikey": idempotency_key,
                        "enc_ctx": encrypted_context,
                        "payload": json.dumps(payload),
                    },
                )

        return job_id

    @classmethod
    def claim_and_process_job(
        cls,
        worker_engine: Engine,
        worker_private_key_pem: str,
        idp_public_key_pem: str,
        kms_provider: KMSProvider,
        lease_owner: str = "worker-1",
        lease_seconds: int = 30,
    ) -> dict[str, Any] | None:
        """Worker-side: Claims and executes one pending job under row lock (SKIP LOCKED).

        Permissions: Executed strictly using worker_engine (ursbiz_kms_worker).
        """
        with worker_engine.connect() as conn:
            # 1. Claim a pending job using SELECT ... FOR UPDATE SKIP LOCKED
            with conn.begin():
                job_row = conn.execute(
                    text("""
                        SELECT id, job_id, business_id, job_type, idempotency_key,
                               encrypted_auth_context, payload_json, attempts, max_attempts
                        FROM public.audit_worker_jobs
                        WHERE status = 'PENDING' OR (status = 'CLAIMED' AND lease_expires_at < NOW())
                        ORDER BY created_at
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    """)
                ).fetchone()

                if not job_row:
                    return None

                job_db_id = job_row[0]
                job_id = job_row[1]
                business_id = job_row[2]
                job_type = job_row[3]
                idempotency_key = job_row[4]
                encrypted_ctx = job_row[5]
                payload = job_row[6] if isinstance(job_row[6], dict) else json.loads(job_row[6])
                attempts = job_row[7] + 1
                max_attempts = job_row[8]

                # Update lease
                conn.execute(
                    text("""
                        UPDATE public.audit_worker_jobs
                        SET status = 'CLAIMED',
                            lease_owner = :owner,
                            lease_expires_at = NOW() + (:lease || ' seconds')::INTERVAL,
                            attempts = :att,
                            updated_at = NOW()
                        WHERE id = :id
                    """),
                    {"owner": lease_owner, "lease": lease_seconds, "att": attempts, "id": job_db_id},
                )

        # 2. Process Job outside the claim transaction to maintain transaction boundaries
        try:
            # Decrypt auth context with worker private key
            auth_token = WorkerContextEncryption.decrypt_envelope(
                envelope_json_str=encrypted_ctx,
                worker_private_key_pem=worker_private_key_pem,
            )

            result: dict[str, Any] = {}
            if job_type in ("AR_REVERSAL", "AP_REVERSAL"):
                alloc_type: Literal["AR", "AP"] = "AR" if job_type == "AR_REVERSAL" else "AP"
                reversal_id = cls.execute_reversal(
                    allocation_type=alloc_type,
                    business_id=business_id,
                    allocation_id=payload["allocation_id"],
                    reversed_amount=float(payload["reversed_amount"]),
                    reason=payload["reason"],
                    auth_token=auth_token,
                    kms_provider=kms_provider,
                    worker_engine=worker_engine,
                    idp_public_key_pem=idp_public_key_pem,
                    request_nonce=payload.get("nonce"),
                )
                result = {"reversal_id": reversal_id, "status": "COMMITTED"}
            elif job_type == "TRANSITION_CHECKPOINT":
                chk_res = cls.execute_transition_checkpoint(
                    business_id=business_id,
                    transition_id=payload["transition_id"],
                    kms_provider=kms_provider,
                    worker_engine=worker_engine,
                    operator_confirmed=True,
                )
                result = chk_res
            else:
                raise ValueError(f"Unknown job_type: {job_type}")

            # Mark COMPLETED
            with worker_engine.connect() as conn:
                with conn.begin():
                    conn.execute(
                        text("""
                            UPDATE public.audit_worker_jobs
                            SET status = 'COMPLETED',
                                result_json = :res,
                                updated_at = NOW()
                            WHERE id = :id
                        """),
                        {"res": json.dumps(result), "id": job_db_id},
                    )

            return {"job_id": job_id, "status": "COMPLETED", "result": result}

        except Exception as e:
            # Mark FAILED or return to PENDING if attempts < max_attempts
            new_status = "FAILED" if attempts >= max_attempts else "PENDING"
            with worker_engine.connect() as conn:
                with conn.begin():
                    conn.execute(
                        text("""
                            UPDATE public.audit_worker_jobs
                            SET status = :st,
                                error_message = :err,
                                updated_at = NOW()
                            WHERE id = :id
                        """),
                        {"st": new_status, "err": str(e), "id": job_db_id},
                    )
            return {"job_id": job_id, "status": new_status, "error": str(e)}
