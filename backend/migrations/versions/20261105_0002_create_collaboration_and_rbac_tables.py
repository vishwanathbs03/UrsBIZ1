"""create collaboration and rbac tables (Prompt 6.26)

Revision ID: 20261105_0002
Revises: 20261105_0001
Create Date: 2026-11-05 23:15:00

Creates:
  - business_members: maps collaborators to businesses with roles (Owner, Administrator, Manager, Analyst, Viewer).
  - business_invitations: cryptographic invitation tokens for onboarding members.
  - business_approval_requests: multi-user workflow review requests for financial and strategic actions.
  - business_approval_audits: append-only audit trail with database-level immutability triggers.
  - Adds user_id tracking to recommendation_lifecycle and chat_messages.
  - Adds business_id association to chat_sessions.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261105_0002"
down_revision: Union[str, None] = "20261105_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create business_members table
    op.create_table(
        "business_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "invited_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
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
        sa.UniqueConstraint("business_id", "user_id", name="uq_business_member_user"),
    )
    op.create_index("ix_business_members_business_id", "business_members", ["business_id"], unique=False)
    op.create_index("ix_business_members_user_id", "business_members", ["user_id"], unique=False)
    op.create_index("ix_business_members_role", "business_members", ["role"], unique=False)
    op.create_index("ix_business_members_status", "business_members", ["status"], unique=False)

    # 2. Create business_invitations table
    op.create_table(
        "business_invitations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("token", sa.String(128), nullable=False),
        sa.Column(
            "invited_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
    )
    op.create_index("ix_business_invitations_token", "business_invitations", ["token"], unique=True)
    op.create_index("ix_business_invitations_business_id", "business_invitations", ["business_id"], unique=False)
    op.create_index("ix_business_invitations_email", "business_invitations", ["email"], unique=False)
    op.create_index("ix_business_invitations_status", "business_invitations", ["status"], unique=False)

    # 3. Create business_approval_requests table
    op.create_table(
        "business_approval_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requester_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("financial_impact_amount", sa.Float(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column(
            "approver_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index("ix_business_approval_requests_business_id", "business_approval_requests", ["business_id"], unique=False)
    op.create_index("ix_business_approval_requests_status", "business_approval_requests", ["status"], unique=False)
    op.create_index("ix_business_approval_requests_requester_user_id", "business_approval_requests", ["requester_user_id"], unique=False)
    op.create_index("ix_business_approval_requests_approver_user_id", "business_approval_requests", ["approver_user_id"], unique=False)

    # 4. Create business_approval_audits table (with ondelete="RESTRICT" on business_id)
    op.create_table(
        "business_approval_audits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "approval_request_id",
            sa.Integer(),
            sa.ForeignKey("business_approval_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("previous_status", sa.String(32), nullable=True),
        sa.Column("new_status", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_business_approval_audits_business_id", "business_approval_audits", ["business_id"], unique=False)
    op.create_index("ix_business_approval_audits_approval_request_id", "business_approval_audits", ["approval_request_id"], unique=False)
    op.create_index("ix_business_approval_audits_user_id", "business_approval_audits", ["user_id"], unique=False)
    op.create_index("ix_business_approval_audits_created_at", "business_approval_audits", ["created_at"], unique=False)

    # 5. Database-level immutability triggers for business_approval_audits
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        op.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_prevent_business_approval_audits_update
        BEFORE UPDATE ON business_approval_audits
        BEGIN
            SELECT RAISE(ABORT, 'ApprovalAudit records are append-only and cannot be updated.');
        END;
        """)
        op.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_prevent_business_approval_audits_delete
        BEFORE DELETE ON business_approval_audits
        BEGIN
            SELECT RAISE(ABORT, 'ApprovalAudit records are append-only and cannot be deleted.');
        END;
        """)
    elif dialect == "postgresql":
        op.execute("""
        CREATE OR REPLACE FUNCTION trg_prevent_business_approval_audits_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'ApprovalAudit records are append-only and cannot be modified or deleted.';
        END;
        $$ LANGUAGE plpgsql;
        """)
        op.execute("""
        CREATE TRIGGER trg_no_update_business_approval_audits
        BEFORE UPDATE ON business_approval_audits
        FOR EACH ROW EXECUTE FUNCTION trg_prevent_business_approval_audits_modification();
        """)
        op.execute("""
        CREATE TRIGGER trg_no_delete_business_approval_audits
        BEFORE DELETE ON business_approval_audits
        FOR EACH ROW EXECUTE FUNCTION trg_prevent_business_approval_audits_modification();
        """)

    # 6. Add user_id to recommendation_lifecycle
    with op.batch_alter_table("recommendation_lifecycle") as batch_op:
        batch_op.add_column(
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.create_index("ix_recommendation_lifecycle_user_id", ["user_id"], unique=False)

    # 7. Add business_id to chat_sessions
    with op.batch_alter_table("chat_sessions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "business_id",
                sa.Integer(),
                sa.ForeignKey("businesses.id", ondelete="CASCADE"),
                nullable=True,
            )
        )
        batch_op.create_index("ix_chat_sessions_business_id", ["business_id"], unique=False)

    # 8. Add user_id to chat_messages
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.add_column(
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.create_index("ix_chat_messages_user_id", ["user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.drop_index("ix_chat_messages_user_id")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("chat_sessions") as batch_op:
        batch_op.drop_index("ix_chat_sessions_business_id")
        batch_op.drop_column("business_id")

    with op.batch_alter_table("recommendation_lifecycle") as batch_op:
        batch_op.drop_index("ix_recommendation_lifecycle_user_id")
        batch_op.drop_column("user_id")

    if dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_business_approval_audits_update;")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_business_approval_audits_delete;")
    elif dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_no_update_business_approval_audits ON business_approval_audits;")
        op.execute("DROP TRIGGER IF EXISTS trg_no_delete_business_approval_audits ON business_approval_audits;")
        op.execute("DROP FUNCTION IF EXISTS trg_prevent_business_approval_audits_modification();")

    op.drop_table("business_approval_audits")
    op.drop_table("business_approval_requests")
    op.drop_table("business_invitations")
    op.drop_table("business_members")
