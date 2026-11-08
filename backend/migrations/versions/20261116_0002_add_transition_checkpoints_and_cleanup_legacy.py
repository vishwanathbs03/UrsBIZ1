"""add transition checkpoints and cleanup legacy procedure (Wave 1.1.2 Remediation)

Revision ID: 20261116_0002
Revises: 20261116_0001
Create Date: 2026-11-16 14:00:00

Remediates Wave 1.1 Security Closure Audit findings:
  1. Creates audit_transition_checkpoints table storing cryptographically signed HMAC-to-Ed25519
     epoch transition checkpoints on the sequential hash chain.
  2. Permanently drops the obsolete, unexecutable legacy stored procedure
     record_allocation_reversal(integer, bigint, numeric, varchar, integer, varchar, varchar, timestamptz, varchar)
     after confirming zero dependencies.
  3. Preserves all historical tables, audit records, and non-secret audit metadata.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261116_0002"
down_revision: Union[str, None] = "20261116_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create audit_transition_checkpoints table
    op.create_table(
        "audit_transition_checkpoints",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("transition_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("legacy_algorithm", sa.String(32), nullable=False, server_default="HMAC-SHA256"),
        sa.Column(
            "legacy_trust_status",
            sa.String(64),
            nullable=False,
            server_default="LEGACY_NON_REPUDIATION_DOWNGRADED",
        ),
        sa.Column("legacy_chain_head_digest", sa.String(64), nullable=False),
        sa.Column("legacy_reversal_count", sa.Integer(), nullable=False),
        sa.Column(
            "transition_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("new_algorithm", sa.String(32), nullable=False, server_default="ED25519"),
        sa.Column(
            "new_signing_key_id",
            sa.String(32),
            sa.ForeignKey("audit_signing_public_keys.key_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("canonical_version", sa.String(32), nullable=False, server_default="URSBIZ_TRANS_V1"),
        sa.Column("checkpoint_signature_hex", sa.String(128), nullable=False),
        sa.Column("checkpoint_digest_sha256", sa.String(64), nullable=False),
        sa.Column("previous_chain_head_digest", sa.String(64), nullable=False),
        sa.CheckConstraint("legacy_reversal_count >= 0", name="chk_trans_legacy_rev_count_nonneg"),
        sa.CheckConstraint("length(checkpoint_signature_hex) = 128", name="chk_trans_sig_len"),
        sa.CheckConstraint("length(checkpoint_digest_sha256) = 64", name="chk_trans_digest_len"),
        sa.CheckConstraint("length(previous_chain_head_digest) = 64", name="chk_trans_prev_digest_len"),
    )
    op.create_index(
        "ix_audit_transition_checkpoints_biz_ts",
        "audit_transition_checkpoints",
        ["business_id", "transition_timestamp"],
        unique=False,
    )

    # 2. Drop obsolete legacy HMAC procedure in PostgreSQL
    # Signature: record_allocation_reversal(integer, bigint, numeric, varchar, integer, varchar, varchar, timestamptz, varchar)
    op.execute(
        "DROP FUNCTION IF EXISTS public.record_allocation_reversal("
        "INTEGER, BIGINT, NUMERIC, VARCHAR, INTEGER, VARCHAR, VARCHAR, TIMESTAMP WITH TIME ZONE, VARCHAR"
        ");"
    )

    # 3. Ownership and permission hardening for PostgreSQL
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ursbiz_audit_admin') THEN
                ALTER TABLE public.audit_transition_checkpoints OWNER TO ursbiz_audit_admin;
                GRANT USAGE, SELECT ON SEQUENCE public.audit_transition_checkpoints_id_seq TO ursbiz_audit_admin;
            END IF;

            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ursbiz_app') THEN
                REVOKE ALL ON public.audit_transition_checkpoints FROM PUBLIC, ursbiz_app;
                GRANT SELECT ON public.audit_transition_checkpoints TO ursbiz_app;
            END IF;

            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ursbiz_kms_worker') THEN
                REVOKE ALL ON public.audit_transition_checkpoints FROM ursbiz_kms_worker;
                GRANT SELECT, INSERT ON public.audit_transition_checkpoints TO ursbiz_kms_worker;
                GRANT USAGE, SELECT ON SEQUENCE public.audit_transition_checkpoints_id_seq TO ursbiz_kms_worker;
                GRANT SELECT ON public.business_members TO ursbiz_kms_worker;
                GRANT SELECT, INSERT, UPDATE ON public.business_audit_chains TO ursbiz_kms_worker;
                GRANT SELECT ON public.ar_allocation_reversals TO ursbiz_kms_worker;
                GRANT SELECT ON public.vendor_allocation_reversals TO ursbiz_kms_worker;
                GRANT SELECT ON public.audit_signing_public_keys TO ursbiz_kms_worker;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # 1. Immutability Guard: Refuse destructive downgrade if authoritative records exist
    bind = op.get_bind()
    count_res = bind.execute(sa.text("SELECT COUNT(*) FROM public.audit_transition_checkpoints"))
    count = count_res.scalar()
    if count and count > 0:
        raise RuntimeError(
            f"REFUSING DESTRUCTIVE DOWNGRADE: public.audit_transition_checkpoints contains {count} "
            "authoritative non-repudiation records. Automated deletion of financial audit evidence "
            "is prohibited. Rollback aborted to protect audit immutability."
        )

    # 2. Drop audit_transition_checkpoints table only when empty
    op.drop_table("audit_transition_checkpoints")

    # Note: We do NOT restore the insecure legacy record_allocation_reversal function on downgrade.
