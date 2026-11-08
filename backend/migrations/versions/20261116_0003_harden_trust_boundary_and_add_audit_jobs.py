"""harden trust boundary, add transition procedure, and create audit jobs table (Wave 1.1.3 Remediation)

Revision ID: 20261116_0003
Revises: 20261116_0002
Create Date: 2026-11-16 18:00:00

Remediates Wave 1.1.3 architecture findings:
  1. Revokes direct INSERT, UPDATE, DELETE on audit_transition_checkpoints and business_audit_chains
     from ursbiz_kms_worker.
  2. Creates SECURITY DEFINER stored procedure public.record_transition_checkpoint(...) with locked
     search_path = pg_catalog, extensions, public, enforcing row-level locking, exact sequential chain
     continuity, idempotency, and atomicity.
  3. Creates public.audit_worker_jobs transactional queue table for decoupled FastAPI-to-worker dispatch
     with envelope-encrypted auth context and SKIP LOCKED worker claiming.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261116_0003"
down_revision: Union[str, None] = "20261116_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create audit_worker_jobs transactional queue table
    op.create_table(
        "audit_worker_jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("job_type", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("encrypted_auth_context", sa.Text(), nullable=False),
        sa.Column("encryption_key_id", sa.String(32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="PENDING"),
        sa.Column("lease_owner", sa.String(64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'CLAIMED', 'COMPLETED', 'FAILED')",
            name="chk_job_status",
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND attempts <= max_attempts",
            name="chk_job_attempts",
        ),
    )
    op.create_index(
        "ix_audit_worker_jobs_claim",
        "audit_worker_jobs",
        ["status", "created_at"],
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    op.create_index(
        "ix_audit_worker_jobs_lease",
        "audit_worker_jobs",
        ["status", "lease_expires_at"],
        postgresql_where=sa.text("status = 'CLAIMED'"),
    )
    op.create_index(
        "ix_audit_worker_jobs_biz_type",
        "audit_worker_jobs",
        ["business_id", "job_type"],
    )

    # 2. Create PostgreSQL SECURITY DEFINER procedure public.record_transition_checkpoint
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.record_transition_checkpoint(
            p_business_id INTEGER,
            p_transition_id VARCHAR(64),
            p_legacy_algorithm VARCHAR(32),
            p_legacy_trust_status VARCHAR(64),
            p_legacy_chain_head VARCHAR(64),
            p_legacy_reversal_count INTEGER,
            p_new_algorithm VARCHAR(32),
            p_new_key_id VARCHAR(32),
            p_canonical_version VARCHAR(32),
            p_checkpoint_sig VARCHAR(128),
            p_checkpoint_digest VARCHAR(64),
            p_prev_chain_head VARCHAR(64),
            p_transition_timestamp TIMESTAMP WITH TIME ZONE
        )
        RETURNS BIGINT
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, extensions, public
        AS $$
        DECLARE
            v_current_head VARCHAR(64);
            v_current_count INTEGER;
            v_next_head VARCHAR(64);
            v_existing_id BIGINT;
            v_existing_digest VARCHAR(64);
            v_key_status VARCHAR(16);
            v_checkpoint_id BIGINT;
        BEGIN
            -- 1. Database Role Authorization Check
            IF session_user NOT IN ('ursbiz_kms_worker', 'postgres') AND current_user NOT IN ('ursbiz_kms_worker', 'postgres', 'ursbiz_audit_admin') THEN
                RAISE EXCEPTION 'PERMISSION DENIED: caller % is not authorized to execute record_transition_checkpoint', session_user;
            END IF;

            -- 2. Input Parameter Structural & Format Validation
            IF p_business_id IS NULL OR p_business_id <= 0 THEN
                RAISE EXCEPTION 'INVALID_ARGUMENT: business_id must be a positive integer';
            END IF;

            IF p_transition_id IS NULL OR length(trim(p_transition_id)) = 0 OR length(p_transition_id) > 64 THEN
                RAISE EXCEPTION 'INVALID_ARGUMENT: transition_id must be between 1 and 64 characters';
            END IF;

            IF p_canonical_version != 'URSBIZ_TRANS_V1' THEN
                RAISE EXCEPTION 'INVALID_ARGUMENT: unsupported canonical_version %, expected URSBIZ_TRANS_V1', p_canonical_version;
            END IF;

            IF length(p_checkpoint_sig) != 128 THEN
                RAISE EXCEPTION 'INVALID_ARGUMENT: checkpoint_signature_hex must be exactly 128 hex characters';
            END IF;

            IF length(p_checkpoint_digest) != 64 THEN
                RAISE EXCEPTION 'INVALID_ARGUMENT: checkpoint_digest_sha256 must be exactly 64 hex characters';
            END IF;

            IF length(p_prev_chain_head) != 64 THEN
                RAISE EXCEPTION 'INVALID_ARGUMENT: previous_chain_head_digest must be exactly 64 hex characters';
            END IF;

            IF p_legacy_reversal_count < 0 THEN
                RAISE EXCEPTION 'INVALID_ARGUMENT: legacy_reversal_count cannot be negative';
            END IF;

            -- 3. Verify Signing Key Lifecycle in audit_signing_public_keys
            SELECT status INTO v_key_status
            FROM public.audit_signing_public_keys
            WHERE key_id = p_new_key_id;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'INVALID_KEY: key_id % does not exist in audit_signing_public_keys', p_new_key_id;
            END IF;

            IF v_key_status NOT IN ('ACTIVE', 'RETIRING') THEN
                RAISE EXCEPTION 'INVALID_KEY_STATUS: key_id % is in % status; requires ACTIVE or RETIRING', p_new_key_id, v_key_status;
            END IF;

            -- 4. Row Lock business_audit_chains FOR UPDATE
            -- Initialize Genesis Anchor if business has no audit chain record (concurrency-safe via ON CONFLICT)
            INSERT INTO public.business_audit_chains (business_id, chain_head_digest, reversal_count, updated_at)
            VALUES (
                p_business_id,
                encode(extensions.digest(convert_to('URSBIZ_GENESIS_' || CAST(p_business_id AS TEXT), 'UTF8'), 'sha256'), 'hex'),
                0,
                p_transition_timestamp
            )
            ON CONFLICT (business_id) DO NOTHING;

            SELECT chain_head_digest, reversal_count
            INTO v_current_head, v_current_count
            FROM public.business_audit_chains
            WHERE business_id = p_business_id
            FOR UPDATE;

            -- 5. Idempotency Check on existing transition_id
            SELECT id, checkpoint_digest_sha256 INTO v_existing_id, v_existing_digest
            FROM public.audit_transition_checkpoints
            WHERE transition_id = p_transition_id;

            IF FOUND THEN
                IF v_existing_digest != p_checkpoint_digest THEN
                    RAISE EXCEPTION 'IDEMPOTENCY CONFLICT: transition_id % already exists with conflicting digest %', p_transition_id, v_existing_digest;
                END IF;
                -- Same transition_id and identical digest: return existing checkpoint id safely
                RETURN v_existing_id;
            END IF;

            -- 6. Sequential Chain Continuity Check
            IF v_current_head != p_prev_chain_head THEN
                RAISE EXCEPTION 'CHAIN CONTINUITY VIOLATION: expected previous head %, but current chain head is %', p_prev_chain_head, v_current_head;
            END IF;

            -- 7. Advance Sequential Hash Chain Head: SHA256(current_head + checkpoint_digest)
            v_next_head := encode(extensions.digest(convert_to(v_current_head || p_checkpoint_digest, 'UTF8'), 'sha256'), 'hex');

            -- 8. Insert Checkpoint Record
            INSERT INTO public.audit_transition_checkpoints (
                business_id, transition_id, legacy_algorithm, legacy_trust_status,
                legacy_chain_head_digest, legacy_reversal_count, transition_timestamp,
                new_algorithm, new_signing_key_id, canonical_version,
                checkpoint_signature_hex, checkpoint_digest_sha256, previous_chain_head_digest
            ) VALUES (
                p_business_id, p_transition_id, p_legacy_algorithm, p_legacy_trust_status,
                p_legacy_chain_head, p_legacy_reversal_count, p_transition_timestamp,
                p_new_algorithm, p_new_key_id, p_canonical_version,
                p_checkpoint_sig, p_checkpoint_digest, p_prev_chain_head
            ) RETURNING id INTO v_checkpoint_id;

            -- 9. Atomically Update Chain Head
            UPDATE public.business_audit_chains
            SET chain_head_digest = v_next_head,
                updated_at = p_transition_timestamp
            WHERE business_id = p_business_id;

            RETURN v_checkpoint_id;
        END;
        $$;
        """
    )

    # 3. Ownership, Permissions, and Direct Table DML Revocation
    op.execute(
        """
        DO $$
        BEGIN
            -- Stored Procedure Ownership & Access
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ursbiz_audit_admin') THEN
                ALTER FUNCTION public.record_transition_checkpoint(
                    INTEGER, VARCHAR, VARCHAR, VARCHAR, VARCHAR, INTEGER, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, TIMESTAMP WITH TIME ZONE
                ) OWNER TO ursbiz_audit_admin;

                ALTER TABLE public.audit_worker_jobs OWNER TO ursbiz_audit_admin;
                GRANT USAGE, SELECT ON SEQUENCE public.audit_worker_jobs_id_seq TO ursbiz_audit_admin;
            END IF;

            REVOKE EXECUTE ON FUNCTION public.record_transition_checkpoint(
                INTEGER, VARCHAR, VARCHAR, VARCHAR, VARCHAR, INTEGER, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, TIMESTAMP WITH TIME ZONE
            ) FROM PUBLIC;

            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ursbiz_app') THEN
                REVOKE EXECUTE ON FUNCTION public.record_transition_checkpoint(
                    INTEGER, VARCHAR, VARCHAR, VARCHAR, VARCHAR, INTEGER, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, TIMESTAMP WITH TIME ZONE
                ) FROM ursbiz_app;

                REVOKE ALL ON public.audit_worker_jobs FROM PUBLIC, ursbiz_app;
                GRANT SELECT, INSERT ON public.audit_worker_jobs TO ursbiz_app;
                GRANT USAGE, SELECT ON SEQUENCE public.audit_worker_jobs_id_seq TO ursbiz_app;
            END IF;

            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ursbiz_kms_worker') THEN
                -- GRANT EXECUTE on approved procedure
                GRANT EXECUTE ON FUNCTION public.record_transition_checkpoint(
                    INTEGER, VARCHAR, VARCHAR, VARCHAR, VARCHAR, INTEGER, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, TIMESTAMP WITH TIME ZONE
                ) TO ursbiz_kms_worker;

                -- STRICT REVOCATION of direct table writes
                REVOKE INSERT, UPDATE, DELETE ON public.audit_transition_checkpoints FROM ursbiz_kms_worker;
                REVOKE INSERT, UPDATE, DELETE ON public.business_audit_chains FROM ursbiz_kms_worker;

                -- GRANT job queue claim & update
                GRANT SELECT, UPDATE ON public.audit_worker_jobs TO ursbiz_kms_worker;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # 1. Immutability & Audit Queue Preservation Guard:
    # Use an efficient existence check rather than counting every row.
    # Refuse destructive downgrade if audit_worker_jobs contains ANY records
    # (PENDING, CLAIMED, COMPLETED, FAILED, or historical execution results).
    bind = op.get_bind()
    has_jobs = bind.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM public.audit_worker_jobs)")
    ).scalar()
    if has_jobs:
        raise RuntimeError(
            "REFUSING DESTRUCTIVE DOWNGRADE: public.audit_worker_jobs contains job records. "
            "Automated deletion of job execution history and audit queue evidence is prohibited. "
            "Rollback aborted to protect audit immutability."
        )

    # 2. Drop procedure only when audit queue is completely empty
    op.execute(
        """
        DROP FUNCTION IF EXISTS public.record_transition_checkpoint(
            INTEGER, VARCHAR, VARCHAR, VARCHAR, VARCHAR, INTEGER, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, TIMESTAMP WITH TIME ZONE
        );
        """
    )

    # 3. Drop audit_worker_jobs table only when empty
    op.drop_table("audit_worker_jobs")
