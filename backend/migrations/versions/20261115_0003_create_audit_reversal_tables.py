"""create audit reversal tables (Wave 1 Financial Intelligence)

Revision ID: 20261115_0003
Revises: 20261115_0002
Create Date: 2026-11-15 12:00:00

Creates:
  - audit_signing_secrets: Cryptographic signing keys with 24-hour retirement constraint.
  - business_audit_chains: Genesis anchors and linear Merkle hash chain state per tenant.
  - audit_reversal_nonces: Replay-prevention nonces with 120-second sliding expiration.
  - allocation_reversals: Immutable cryptographic audit trail of payment allocation reversals.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261115_0003"
down_revision: Union[str, None] = "20261115_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create audit_signing_secrets table
    op.create_table(
        "audit_signing_secrets",
        sa.Column("key_id", sa.String(32), primary_key=True),
        sa.Column("secret_bytes", sa.LargeBinary(), nullable=False),
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
            name="chk_signing_secret_status",
        ),
        sa.CheckConstraint(
            "(status != 'RETIRING') OR ("
            "retirement_started_at IS NOT NULL "
            "AND retires_at IS NOT NULL "
            "AND retires_at > retirement_started_at "
            "AND retires_at <= retirement_started_at + INTERVAL '24 hours'"
            ")",
            name="chk_retirement_grace",
        ),
        sa.CheckConstraint(
            "(status != 'REVOKED') OR (revoked_at IS NOT NULL)",
            name="chk_revoked_state",
        ),
    )
    op.create_index("ix_audit_signing_secrets_status", "audit_signing_secrets", ["status"], unique=False)

    # 2. Create business_audit_chains table
    op.create_table(
        "business_audit_chains",
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("chain_head_digest", sa.String(64), nullable=False),
        sa.Column("reversal_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # 3. Create audit_reversal_nonces table
    op.create_table(
        "audit_reversal_nonces",
        sa.Column("nonce", sa.String(64), primary_key=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "used_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_reversal_nonces_business_id", "audit_reversal_nonces", ["business_id"], unique=False)
    op.create_index("ix_audit_reversal_nonces_expires_at", "audit_reversal_nonces", ["expires_at"], unique=False)

    # 4. Create allocation_reversals table
    op.create_table(
        "allocation_reversals",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("original_allocation_id", sa.BigInteger(), nullable=False),
        sa.Column("reversed_amount", sa.Numeric(18, 2), nullable=False),
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
        sa.CheckConstraint("reversed_amount > 0", name="chk_reversal_amount_positive"),
        sa.ForeignKeyConstraint(
            ["original_allocation_id", "business_id"],
            ["ar_payment_allocations.id", "ar_payment_allocations.business_id"],
            name="fk_reversal_alloc_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["business_id", "actor_user_id"],
            ["business_members.business_id", "business_members.user_id"],
            name="fk_reversal_actor_tenant",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_allocation_reversals_business_id", "allocation_reversals", ["business_id"], unique=False)
    op.create_index("ix_allocation_reversals_allocation_id", "allocation_reversals", ["original_allocation_id"], unique=False)
    op.create_index("ix_allocation_reversals_actor_id", "allocation_reversals", ["actor_user_id"], unique=False)
    op.create_index("ix_allocation_reversals_reversed_at", "allocation_reversals", ["reversed_at"], unique=False)


def downgrade() -> None:
    op.drop_table("allocation_reversals")
    op.drop_table("audit_reversal_nonces")
    op.drop_table("business_audit_chains")
    op.drop_table("audit_signing_secrets")
