"""SQLAlchemy ORM models for Cryptographic Audit Chains, Public Keys, and Allocation Reversals.

Part of Wave 1.1 Remediation (Financial Intelligence Architecture):
  - AuditSigningPublicKey: Asymmetric Ed25519 public key store with enforced 24h retirement.
  - AuditSigningSecret: Legacy HMAC key vault (deprecated; preserved for historical records).
  - BusinessAuditChain: Tenant-level genesis anchors and linear hash chain heads.
  - AuditReversalNonce: Atomic replay prevention table with expiration.
  - ARAllocationReversal: Immutable cryptographic audit trail of AR payment allocation reversals.
  - VendorAllocationReversal: Symmetrical cryptographic audit trail of AP vendor allocation reversals.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.database import Base


@compiles(CheckConstraint, "sqlite")
def _compile_check_constraint_sqlite(element, compiler, **kw):
    """Skip PostgreSQL-specific INTERVAL syntax when compiling for SQLite (e.g. in-memory test suites)."""
    sqltext = getattr(element, "sqltext", None)
    text_val = getattr(sqltext, "text", str(sqltext)) if sqltext is not None else ""
    if "INTERVAL" in text_val:
        return None
    return compiler.visit_check_constraint(element, **kw)


if TYPE_CHECKING:
    from app.models.accounts_payable import VendorPaymentAllocation
    from app.models.accounts_receivable import ARPaymentAllocation
    from app.models.business import Business
    from app.models.user import User


class AuditSigningPublicKey(Base):
    """Asymmetric Ed25519 public verification keys for reversal assertion validation."""

    __tablename__ = "audit_signing_public_keys"

    key_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    public_key: Mapped[str] = mapped_column(String(128), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(32), nullable=False, default="ED25519", server_default="ED25519")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE", server_default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    retirement_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'RETIRING', 'EXPIRED', 'REVOKED')",
            name="chk_pubkey_status",
        ),
        CheckConstraint(
            "(status != 'RETIRING') OR ("
            "retirement_started_at IS NOT NULL "
            "AND retires_at IS NOT NULL "
            "AND retires_at > retirement_started_at "
            "AND retires_at <= retirement_started_at + INTERVAL '24 hours'"
            ")",
            name="chk_pubkey_retirement_grace",
        ),
        CheckConstraint(
            "(status != 'REVOKED') OR (revoked_at IS NOT NULL)",
            name="chk_pubkey_revoked_state",
        ),
    )


class AuditSigningSecret(Base):
    """Legacy symmetric HMAC signing secret store (Deprecated: preserved for historical audit logs)."""

    __tablename__ = "audit_signing_secrets"

    key_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    secret_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE", server_default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    retirement_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'RETIRING', 'EXPIRED', 'REVOKED')",
            name="chk_signing_secret_status",
        ),
        CheckConstraint(
            "(status != 'RETIRING') OR ("
            "retirement_started_at IS NOT NULL "
            "AND retires_at IS NOT NULL "
            "AND retires_at > retirement_started_at "
            "AND retires_at <= retirement_started_at + INTERVAL '24 hours'"
            ")",
            name="chk_retirement_grace",
        ),
        CheckConstraint(
            "(status != 'REVOKED') OR (revoked_at IS NOT NULL)",
            name="chk_revoked_state",
        ),
    )


class BusinessAuditChain(Base):
    """Tenant-level audit anchor tracking linear sequential hash chain heads."""

    __tablename__ = "business_audit_chains"

    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    chain_head_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    reversal_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    business: Mapped[Business] = relationship(foreign_keys=[business_id])


class AuditReversalNonce(Base):
    """Replay prevention store for authenticated reversal requests."""

    __tablename__ = "audit_reversal_nonces"

    nonce: Mapped[str] = mapped_column(String(64), primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    business: Mapped[Business] = relationship(foreign_keys=[business_id])


class ARAllocationReversal(Base):
    """Immutable audit trail row recording an Accounts Receivable payment allocation reversal."""

    __tablename__ = "ar_allocation_reversals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    original_allocation_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    reversed_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    amount_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR", server_default="INR")
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reversed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    previous_digest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_digest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    signature_algorithm: Mapped[str] = mapped_column(String(32), nullable=False, default="HMAC-SHA256", server_default="HMAC-SHA256")
    signing_key_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    signature_hex: Mapped[str | None] = mapped_column(String(128), nullable=True)

    business: Mapped[Business] = relationship(foreign_keys=[business_id])
    actor: Mapped[User] = relationship(foreign_keys=[actor_user_id])
    original_allocation: Mapped[ARPaymentAllocation] = relationship(
        foreign_keys=[original_allocation_id],
    )

    __table_args__ = (
        CheckConstraint("reversed_amount > 0", name="chk_reversal_amount_positive"),
        ForeignKeyConstraint(
            ["original_allocation_id", "business_id"],
            ["ar_payment_allocations.id", "ar_payment_allocations.business_id"],
            name="fk_reversal_alloc_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["business_id", "actor_user_id"],
            ["business_members.business_id", "business_members.user_id"],
            name="fk_reversal_actor_tenant",
            ondelete="RESTRICT",
        ),
    )


# Backward-compatible alias
AllocationReversal = ARAllocationReversal


class VendorAllocationReversal(Base):
    """Immutable audit trail row recording an Accounts Payable vendor payment allocation reversal."""

    __tablename__ = "vendor_allocation_reversals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    vendor_allocation_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    reversed_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR", server_default="INR")
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reversed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    previous_digest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_digest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    signature_algorithm: Mapped[str] = mapped_column(String(32), nullable=False, default="ED25519", server_default="ED25519")
    signing_key_id: Mapped[str] = mapped_column(String(32), nullable=False)
    signature_hex: Mapped[str] = mapped_column(String(128), nullable=False)

    business: Mapped[Business] = relationship(foreign_keys=[business_id])
    actor: Mapped[User] = relationship(foreign_keys=[actor_user_id])
    vendor_allocation: Mapped[VendorPaymentAllocation] = relationship(
        foreign_keys=[vendor_allocation_id],
    )

    __table_args__ = (
        CheckConstraint("reversed_amount > 0", name="chk_vendor_reversal_amount_positive"),
        CheckConstraint("amount_paise > 0", name="chk_vendor_reversal_paise_positive"),
        ForeignKeyConstraint(
            ["vendor_allocation_id", "business_id"],
            ["vendor_payment_allocations.id", "vendor_payment_allocations.business_id"],
            name="fk_ap_reversal_alloc_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["business_id", "actor_user_id"],
            ["business_members.business_id", "business_members.user_id"],
            name="fk_ap_reversal_actor_tenant",
            ondelete="RESTRICT",
        ),
    )


class AuditTransitionCheckpoint(Base):
    """Immutable transition checkpoint sealing the boundary between legacy HMAC and asymmetric Ed25519 epochs."""

    __tablename__ = "audit_transition_checkpoints"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    transition_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    legacy_algorithm: Mapped[str] = mapped_column(String(32), nullable=False, default="HMAC-SHA256", server_default="HMAC-SHA256")
    legacy_trust_status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="LEGACY_NON_REPUDIATION_DOWNGRADED",
        server_default="LEGACY_NON_REPUDIATION_DOWNGRADED",
    )
    legacy_chain_head_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    legacy_reversal_count: Mapped[int] = mapped_column(Integer, nullable=False)
    transition_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    new_algorithm: Mapped[str] = mapped_column(String(32), nullable=False, default="ED25519", server_default="ED25519")
    new_signing_key_id: Mapped[str] = mapped_column(
        ForeignKey("audit_signing_public_keys.key_id", ondelete="RESTRICT"),
        nullable=False,
    )
    canonical_version: Mapped[str] = mapped_column(String(32), nullable=False, default="URSBIZ_TRANS_V1", server_default="URSBIZ_TRANS_V1")
    checkpoint_signature_hex: Mapped[str] = mapped_column(String(128), nullable=False)
    checkpoint_digest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_chain_head_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    business: Mapped[Business] = relationship(foreign_keys=[business_id])
    signing_key: Mapped[AuditSigningPublicKey] = relationship(foreign_keys=[new_signing_key_id])

    __table_args__ = (
        CheckConstraint("legacy_reversal_count >= 0", name="chk_trans_legacy_rev_count_nonneg"),
        CheckConstraint("length(checkpoint_signature_hex) = 128", name="chk_trans_sig_len"),
        CheckConstraint("length(checkpoint_digest_sha256) = 64", name="chk_trans_digest_len"),
        CheckConstraint("length(previous_chain_head_digest) = 64", name="chk_trans_prev_digest_len"),
    )


class AuditWorkerJob(Base):
    """Transactional job queue record for decoupled audit worker tasks."""

    __tablename__ = "audit_worker_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    encrypted_auth_context: Mapped[str] = mapped_column(Text, nullable=False)
    encryption_key_id: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING", server_default="PENDING")
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    business: Mapped[Business] = relationship(foreign_keys=[business_id])

    __table_args__ = (
        CheckConstraint("status IN ('PENDING', 'CLAIMED', 'COMPLETED', 'FAILED')", name="chk_job_status"),
        CheckConstraint("attempts >= 0 AND attempts <= max_attempts", name="chk_job_attempts"),
    )
