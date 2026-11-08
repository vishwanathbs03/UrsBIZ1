"""remediate audit security and add ap reversals (Wave 1.1 Remediation)

Revision ID: 20261116_0001
Revises: 20261115_0004
Create Date: 2026-11-16 10:00:00

Remediates Wave 1 security and architecture findings:
  1. Creates audit_signing_public_keys table storing Ed25519 public verification keys and lifecycle metadata.
  2. Deprecates/revokes plaintext HMAC keys in audit_signing_secrets without deleting historical rows.
  3. Renames allocation_reversals to ar_allocation_reversals and adds signature_algorithm/key_id/paise metadata.
  4. Creates vendor_allocation_reversals table for Accounts Payable payment allocation reversals with
     composite tenant isolation foreign key to vendor_payment_allocations(id, business_id) and actor membership
     foreign key to business_members(business_id, user_id).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261116_0001"
down_revision: Union[str, None] = "20261115_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create audit_signing_public_keys table
    op.create_table(
        "audit_signing_public_keys",
        sa.Column("key_id", sa.String(32), primary_key=True),
        sa.Column("public_key", sa.String(128), nullable=False),
        sa.Column("algorithm", sa.String(32), nullable=False, server_default="ED25519"),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("retirement_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(255), nullable=True),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'RETIRING', 'EXPIRED', 'REVOKED')",
            name="chk_pubkey_status",
        ),
        sa.CheckConstraint(
            "(status != 'RETIRING') OR ("
            "retirement_started_at IS NOT NULL "
            "AND retires_at IS NOT NULL "
            "AND retires_at > retirement_started_at "
            "AND retires_at <= retirement_started_at + INTERVAL '24 hours'"
            ")",
            name="chk_pubkey_retirement_grace",
        ),
        sa.CheckConstraint(
            "(status != 'REVOKED') OR (revoked_at IS NOT NULL)",
            name="chk_pubkey_revoked_state",
        ),
    )
    op.create_index(
        "ix_audit_signing_public_keys_status",
        "audit_signing_public_keys",
        ["status"],
        unique=False,
    )

    # 2. Rename allocation_reversals -> ar_allocation_reversals
    op.rename_table("allocation_reversals", "ar_allocation_reversals")

    # Add metadata columns to ar_allocation_reversals
    op.add_column(
        "ar_allocation_reversals",
        sa.Column("amount_paise", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "ar_allocation_reversals",
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
    )
    op.add_column(
        "ar_allocation_reversals",
        sa.Column("signature_algorithm", sa.String(32), nullable=False, server_default="HMAC-SHA256"),
    )
    op.add_column(
        "ar_allocation_reversals",
        sa.Column("signing_key_id", sa.String(32), nullable=True),
    )
    op.add_column(
        "ar_allocation_reversals",
        sa.Column("signature_hex", sa.String(128), nullable=True),
    )

    # 3. Create vendor_allocation_reversals table for AP
    op.create_table(
        "vendor_allocation_reversals",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("vendor_allocation_id", sa.BigInteger(), nullable=False),
        sa.Column("reversed_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "reversed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("previous_digest_sha256", sa.String(64), nullable=False),
        sa.Column("audit_digest_sha256", sa.String(64), nullable=False),
        sa.Column("signature_algorithm", sa.String(32), nullable=False, server_default="ED25519"),
        sa.Column("signing_key_id", sa.String(32), nullable=False),
        sa.Column("signature_hex", sa.String(128), nullable=False),
        sa.CheckConstraint("reversed_amount > 0", name="chk_vendor_reversal_amount_positive"),
        sa.CheckConstraint("amount_paise > 0", name="chk_vendor_reversal_paise_positive"),
        sa.ForeignKeyConstraint(
            ["vendor_allocation_id", "business_id"],
            ["vendor_payment_allocations.id", "vendor_payment_allocations.business_id"],
            name="fk_ap_reversal_alloc_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["business_id", "actor_user_id"],
            ["business_members.business_id", "business_members.user_id"],
            name="fk_ap_reversal_actor_tenant",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_vendor_allocation_reversals_business_id",
        "vendor_allocation_reversals",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        "ix_vendor_allocation_reversals_alloc_id",
        "vendor_allocation_reversals",
        ["vendor_allocation_id"],
        unique=False,
    )
    op.create_index(
        "ix_vendor_allocation_reversals_reversed_at",
        "vendor_allocation_reversals",
        ["reversed_at"],
        unique=False,
    )

    # 4. Revoke and Zeroize legacy HMAC keys in audit_signing_secrets
    # Overwrites secret_bytes with 32 zero bytes to completely erase plaintext key material
    # while preserving historical key IDs, audit timestamps, and revocation metadata.
    op.execute(
        "UPDATE audit_signing_secrets "
        "SET status = 'REVOKED', "
        "    secret_bytes = decode(repeat('00', 32), 'hex'), "
        "    revoked_at = COALESCE(revoked_at, NOW()), "
        "    revocation_reason = 'DEPRECATED_HMAC_TRANSITION_TO_ED25519_SECRET_ZEROIZED' "
        "WHERE status != 'REVOKED' OR secret_bytes != decode(repeat('00', 32), 'hex');"
    )


def downgrade() -> None:
    # 1. Immutability & Cryptographic/Financial Evidence Preservation Guards:
    # Perform all checks BEFORE any destructive DDL (dropping tables or columns).
    bind = op.get_bind()

    # Guard A: Protect Accounts Payable vendor allocation reversal audit evidence
    has_vendor_reversals = bind.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM public.vendor_allocation_reversals)")
    ).scalar()
    if has_vendor_reversals:
        raise RuntimeError(
            "REFUSING DESTRUCTIVE DOWNGRADE: public.vendor_allocation_reversals contains "
            "authoritative Accounts Payable allocation reversal audit evidence. "
            "Automated deletion of financial reversal records is prohibited. "
            "Rollback aborted to protect audit immutability."
        )

    # Guard B: Protect Ed25519 public signing keys required for independent signature verification
    has_signing_keys = bind.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM public.audit_signing_public_keys)")
    ).scalar()
    if has_signing_keys:
        raise RuntimeError(
            "REFUSING DESTRUCTIVE DOWNGRADE: public.audit_signing_public_keys contains "
            "public verification keys and lifecycle metadata. Existing cryptographic audit "
            "signatures depend on these keys for non-repudiation. "
            "Rollback aborted to protect audit immutability."
        )

    # Guard C: Protect Accounts Receivable reversal financial and cryptographic metadata
    has_ar_evidence = bind.execute(
        sa.text(
            "SELECT EXISTS ("
            "    SELECT 1 FROM public.ar_allocation_reversals "
            "    WHERE signature_hex IS NOT NULL "
            "       OR signing_key_id IS NOT NULL "
            "       OR signature_algorithm IS NOT NULL "
            "       OR currency IS NOT NULL "
            "       OR amount_paise IS NOT NULL"
            ")"
        )
    ).scalar()
    if has_ar_evidence:
        raise RuntimeError(
            "REFUSING DESTRUCTIVE DOWNGRADE: public.ar_allocation_reversals contains "
            "authoritative financial and cryptographic metadata (signature_hex, signing_key_id, "
            "signature_algorithm, currency, or amount_paise). Dropping these columns would "
            "destroy financial audit evidence. Rollback aborted to protect audit immutability."
        )

    # 2. Drop vendor_allocation_reversals only when completely empty
    op.drop_table("vendor_allocation_reversals")

    # 3. Revert ar_allocation_reversals to allocation_reversals only when free of migration evidence
    op.drop_column("ar_allocation_reversals", "signature_hex")
    op.drop_column("ar_allocation_reversals", "signing_key_id")
    op.drop_column("ar_allocation_reversals", "signature_algorithm")
    op.drop_column("ar_allocation_reversals", "currency")
    op.drop_column("ar_allocation_reversals", "amount_paise")
    op.rename_table("ar_allocation_reversals", "allocation_reversals")

    # 4. Drop audit_signing_public_keys only when completely empty
    op.drop_table("audit_signing_public_keys")
